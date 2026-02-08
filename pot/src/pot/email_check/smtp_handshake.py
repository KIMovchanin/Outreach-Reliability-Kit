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


class SMTPHandshakeChecker:
    def __init__(self, config: SMTPCheckerConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger

    def verify(self, target_email: str, mx_hosts: list[str]) -> SMTPCheckResult:
        if not mx_hosts:
            return SMTPCheckResult(status="unknown", detail="нет MX-хостов для SMTP проверки")

        errors: list[str] = []
        host_candidates = mx_hosts[: max(1, self.config.max_mx_tries)]

        for host in host_candidates:
            for attempt in range(1, self.config.retry_attempts + 1):
                result = self._verify_with_host(host, target_email)
                if result is not None:
                    return result

                errors.append(f"{host}: попытка {attempt} не удалась")
                if attempt < self.config.retry_attempts:
                    time.sleep(self.config.retry_delay_sec)

        return SMTPCheckResult(status="unknown", detail="; ".join(errors[-4:]) or "не удалось проверить")

    def _verify_with_host(self, host: str, target_email: str) -> SMTPCheckResult | None:
        try:
            with smtplib.SMTP(host=host, port=25, timeout=self.config.timeout) as smtp:
                smtp.ehlo(self.config.helo_host)
                if self.config.try_starttls and smtp.has_extn("starttls"):
                    try:
                        context = ssl.create_default_context()
                        smtp.starttls(context=context)
                        smtp.ehlo(self.config.helo_host)
                    except smtplib.SMTPException as exc:
                        self.logger.info("STARTTLS not used for host=%s: %s", host, exc)

                mail_code, mail_msg = smtp.mail(self.config.mail_from)
                if mail_code >= 500:
                    return SMTPCheckResult(
                        status="unknown",
                        detail=f"MAIL FROM отклонен: {mail_code} {self._decode(mail_msg)}",
                        code=mail_code,
                    )

                rcpt_code, rcpt_msg = smtp.rcpt(target_email)
                return self._interpret_rcpt_response(rcpt_code, rcpt_msg)
        except (socket.timeout, TimeoutError):
            self.logger.warning("SMTP timeout for host=%s", host)
            return None
        except smtplib.SMTPConnectError as exc:
            self.logger.warning("SMTP connect error host=%s: %s", host, exc)
            return None
        except smtplib.SMTPServerDisconnected:
            self.logger.warning("SMTP server disconnected host=%s", host)
            return None
        except OSError as exc:
            self.logger.warning("SMTP network error host=%s: %s", host, exc)
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
