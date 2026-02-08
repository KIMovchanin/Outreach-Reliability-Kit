from __future__ import annotations

import logging
import smtplib
import socket
import ssl
import time
from dataclasses import dataclass

from .models import SMTPCheckResult


@dataclass(slots=True)
class SMTPCheckerConfig:
    timeout: float
    max_mx_tries: int
    mail_from: str
    helo_host: str
    retry_attempts: int = 2
    retry_delay_sec: float = 0.35
    try_starttls: bool = True
    host_failure_cooldown_sec: float = 300.0


class SMTPHandshakeChecker:
    def __init__(self, config: SMTPCheckerConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self._host_unavailable_until: dict[str, float] = {}
        self._host_unavailable_reason: dict[str, str] = {}

    def verify(self, target_email: str, mx_hosts: list[str]) -> SMTPCheckResult:
        if not mx_hosts:
            return SMTPCheckResult(status="unknown", detail="нет MX-хостов для SMTP проверки")

        self.logger.debug("SMTP verify start email=%s mx_hosts=%s", target_email, mx_hosts)
        errors: list[str] = []
        host_candidates = mx_hosts[: max(1, self.config.max_mx_tries)]

        for host in host_candidates:
            cooldown_note = self._cooldown_note(host)
            if cooldown_note:
                self.logger.debug("SMTP host skipped by cooldown email=%s host=%s note=%s", target_email, host, cooldown_note)
                errors.append(cooldown_note)
                continue

            for attempt in range(1, self.config.retry_attempts + 1):
                self.logger.debug("SMTP attempt start email=%s host=%s attempt=%s", target_email, host, attempt)
                result = self._verify_with_host(host, target_email)
                if result is not None:
                    self.logger.debug(
                        "SMTP attempt success email=%s host=%s attempt=%s status=%s code=%s",
                        target_email,
                        host,
                        attempt,
                        result.status,
                        result.code,
                    )
                    return result

                errors.append(f"{host}: попытка {attempt} не удалась")
                if attempt < self.config.retry_attempts:
                    time.sleep(self.config.retry_delay_sec)

        if not errors:
            return SMTPCheckResult(status="unknown", detail="не удалось проверить")

        suffix = (
            " Вероятно, исходящие SMTP-подключения на 25 порт блокируются сетью/провайдером."
            if any("timeout" in err or "network error" in err for err in errors)
            else ""
        )
        summary = f"{'; '.join(errors[-4:])}{suffix}"
        self.logger.debug("SMTP verify finished email=%s status=unknown detail=%s", target_email, summary)
        return SMTPCheckResult(status="unknown", detail=summary)

    def _verify_with_host(self, host: str, target_email: str) -> SMTPCheckResult | None:
        started = time.monotonic()
        try:
            self.logger.debug("SMTP connect start host=%s email=%s timeout=%s", host, target_email, self.config.timeout)
            with smtplib.SMTP(host=host, port=25, timeout=self.config.timeout) as smtp:
                ehlo_code, ehlo_msg = smtp.ehlo(self.config.helo_host)
                self.logger.debug("SMTP EHLO host=%s code=%s msg=%s", host, ehlo_code, self._decode(ehlo_msg))
                if self.config.try_starttls and smtp.has_extn("starttls"):
                    try:
                        context = ssl.create_default_context()
                        smtp.starttls(context=context)
                        tls_ehlo_code, tls_ehlo_msg = smtp.ehlo(self.config.helo_host)
                        self.logger.debug(
                            "SMTP STARTTLS success host=%s ehlo_code=%s msg=%s",
                            host,
                            tls_ehlo_code,
                            self._decode(tls_ehlo_msg),
                        )
                    except smtplib.SMTPException as exc:
                        self.logger.info("STARTTLS not used for host=%s: %s", host, exc)

                mail_code, mail_msg = smtp.mail(self.config.mail_from)
                self.logger.debug("SMTP MAIL FROM host=%s code=%s msg=%s", host, mail_code, self._decode(mail_msg))
                if mail_code >= 500:
                    return SMTPCheckResult(
                        status="unknown",
                        detail=f"MAIL FROM отклонен: {mail_code} {self._decode(mail_msg)}",
                        code=mail_code,
                    )

                rcpt_code, rcpt_msg = smtp.rcpt(target_email)
                elapsed = time.monotonic() - started
                self.logger.debug(
                    "SMTP RCPT host=%s email=%s code=%s msg=%s elapsed=%.3fs",
                    host,
                    target_email,
                    rcpt_code,
                    self._decode(rcpt_msg),
                    elapsed,
                )
                return self._interpret_rcpt_response(rcpt_code, rcpt_msg)
        except (socket.timeout, TimeoutError):
            elapsed = time.monotonic() - started
            self.logger.warning("SMTP timeout for host=%s elapsed=%.3fs", host, elapsed)
            self._mark_host_unavailable(host, "timeout")
            return None
        except smtplib.SMTPConnectError as exc:
            self.logger.warning("SMTP connect error host=%s: %s", host, exc)
            self._mark_host_unavailable(host, f"connect error: {exc}")
            return None
        except smtplib.SMTPServerDisconnected:
            self.logger.warning("SMTP server disconnected host=%s", host)
            self._mark_host_unavailable(host, "server disconnected")
            return None
        except OSError as exc:
            self.logger.warning("SMTP network error host=%s: %s", host, exc)
            self._mark_host_unavailable(host, f"network error: {exc}")
            return None
        except smtplib.SMTPException as exc:
            return SMTPCheckResult(status="unknown", detail=f"SMTP ошибка: {exc}")

    @staticmethod
    def _decode(value: bytes | str) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _interpret_rcpt_response(self, code: int, message: bytes | str) -> SMTPCheckResult:
        detail = f"{code} {self._decode(message)}".strip()

        if code in (250, 251):
            return SMTPCheckResult(status="deliverable", detail=detail, code=code)

        if code in (550, 551, 552, 553, 554):
            return SMTPCheckResult(status="undeliverable", detail=detail, code=code)

        if code in (450, 451, 452, 421):
            return SMTPCheckResult(status="tempfail", detail=detail, code=code)

        if code in (530, 535) or code >= 500:
            return SMTPCheckResult(status="unknown", detail=f"policy/block: {detail}", code=code)

        return SMTPCheckResult(status="unknown", detail=detail, code=code)

    def _mark_host_unavailable(self, host: str, reason: str) -> None:
        cooldown = max(0.0, self.config.host_failure_cooldown_sec)
        if cooldown <= 0:
            return
        self._host_unavailable_until[host] = time.time() + cooldown
        self._host_unavailable_reason[host] = reason
        self.logger.debug("SMTP host marked unavailable host=%s reason=%s cooldown=%.1fs", host, reason, cooldown)

    def _cooldown_note(self, host: str) -> str | None:
        unavailable_until = self._host_unavailable_until.get(host)
        if unavailable_until is None:
            return None

        now = time.time()
        if now >= unavailable_until:
            self._host_unavailable_until.pop(host, None)
            self._host_unavailable_reason.pop(host, None)
            return None

        reason = self._host_unavailable_reason.get(host, "host unavailable")
        wait_left = int(unavailable_until - now)
        return f"{host}: skip due to recent {reason} (cooldown {wait_left}s)"
