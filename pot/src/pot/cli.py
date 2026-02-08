from __future__ import annotations

import argparse
import json
import time
from typing import Sequence

from pot.email_check.domain_mx import DomainMXChecker
from pot.email_check.models import EmailCheckResult
from pot.email_check.smtp_handshake import SMTPCheckerConfig, SMTPHandshakeChecker
from pot.email_check.validator import collect_emails, extract_domain, is_valid_email_format
from pot.utils.io import read_lines
from pot.utils.logging import setup_logging

DEFAULT_TIMEOUT = 8.0
DEFAULT_MAX_MX_TRIES = 2
DEFAULT_DOMAIN_PAUSE_SEC = 0.3
DEFAULT_MAIL_FROM = "verify@yourdomain.test"
DEFAULT_HELO_HOST = "localhost"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="POT email domain + SMTP handshake checker")
    parser.add_argument("--file", help="Path to file with emails (one per line)")
    parser.add_argument("--emails", nargs="*", default=[], help="Emails from CLI")
    parser.add_argument("--format", choices=["table", "jsonl"], default="table", help="Output format")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Network timeout in seconds")
    parser.add_argument("--max-mx-tries", type=int, default=DEFAULT_MAX_MX_TRIES, help="How many MX hosts to try")
    parser.add_argument("--domain-pause", type=float, default=DEFAULT_DOMAIN_PAUSE_SEC, help="Pause between domains")
    parser.add_argument("--mail-from", default=DEFAULT_MAIL_FROM, help="MAIL FROM address used in SMTP probe")
    parser.add_argument("--helo-host", default=DEFAULT_HELO_HOST, help="Hostname for EHLO/HELO")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--self-check", action="store_true", help="Run lightweight internal checks and exit")
    return parser


def check_emails(
    emails: Sequence[str],
    timeout: float,
    max_mx_tries: int,
    domain_pause: float,
    mail_from: str,
    helo_host: str,
) -> list[EmailCheckResult]:
    logger = setup_logging()
    mx_checker = DomainMXChecker(timeout=timeout, logger=logger)
    smtp_checker = SMTPHandshakeChecker(
        config=SMTPCheckerConfig(
            timeout=timeout,
            max_mx_tries=max_mx_tries,
            mail_from=mail_from,
            helo_host=helo_host,
        ),
        logger=logger,
    )

    results: list[EmailCheckResult] = []
    for email in emails:
        if not is_valid_email_format(email):
            results.append(
                EmailCheckResult(
                    email=email,
                    domain=extract_domain(email),
                    domain_status="domain_missing",
                    mx_hosts=[],
                    smtp_status="unknown",
                    smtp_detail="некорректный формат email",
                )
            )
            continue

        domain = extract_domain(email)
        mx_result = mx_checker.lookup(domain)
        smtp_status = "unknown"
        smtp_detail = "SMTP skipped"

        if mx_result.status == "valid":
            smtp_result = smtp_checker.verify(email, mx_result.mx_hosts)
            smtp_status = smtp_result.status
            smtp_detail = smtp_result.detail

        results.append(
            EmailCheckResult(
                email=email,
                domain=domain,
                domain_status=mx_result.status,
                mx_hosts=mx_result.mx_hosts,
                smtp_status=smtp_status,
                smtp_detail=smtp_detail,
            )
        )
        time.sleep(max(0.0, domain_pause))

    return results


def print_table(results: Sequence[EmailCheckResult]) -> None:
    rows = [
        {
            "email": r.email,
            "domain": r.domain,
            "domain_status": r.domain_status,
            "mx_hosts": ",".join(r.mx_hosts),
            "smtp_status": r.smtp_status,
            "smtp_detail": r.smtp_detail,
        }
        for r in results
    ]

    headers = ["email", "domain", "domain_status", "mx_hosts", "smtp_status", "smtp_detail"]
    widths = {key: len(key) for key in headers}
    for row in rows:
        for key in headers:
            widths[key] = max(widths[key], len(str(row[key])))

    separator = " | ".join("-" * widths[key] for key in headers)
    print(" | ".join(key.ljust(widths[key]) for key in headers))
    print(separator)
    for row in rows:
        print(" | ".join(str(row[key]).ljust(widths[key]) for key in headers))


def print_jsonl(results: Sequence[EmailCheckResult]) -> None:
    for result in results:
        print(json.dumps(result.to_dict(), ensure_ascii=False))


def run_self_check() -> int:
    sample = ["USER@example.com", "bad-email", " one@sample.org "]
    normalized = collect_emails(cli_emails=sample, file_emails=[])
    if normalized != ["user@example.com", "bad-email", "one@sample.org"]:
        print("SELF-CHECK FAILED: collect_emails")
        return 1

    if not is_valid_email_format("a.b+c@domain.tld"):
        print("SELF-CHECK FAILED: valid format")
        return 1

    if is_valid_email_format("wrong@@domain"):
        print("SELF-CHECK FAILED: invalid format")
        return 1

    rows = [
        EmailCheckResult(
            email="user@example.com",
            domain="example.com",
            domain_status="valid",
            mx_hosts=["mx1.example.com"],
            smtp_status="unknown",
            smtp_detail="sample",
        )
    ]
    print("SELF-CHECK OK")
    print_table(rows)
    print_jsonl(rows)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    if args.self_check:
        return run_self_check()

    file_emails: list[str] = []
    if args.file:
        try:
            file_emails = read_lines(args.file)
        except FileNotFoundError as exc:
            print(exc)
            return 2

    emails = collect_emails(cli_emails=args.emails, file_emails=file_emails)
    if not emails:
        parser.error("Provide emails via --emails and/or --file")

    results = check_emails(
        emails=emails,
        timeout=args.timeout,
        max_mx_tries=max(1, args.max_mx_tries),
        domain_pause=max(0.0, args.domain_pause),
        mail_from=args.mail_from,
        helo_host=args.helo_host,
    )

    if args.format == "jsonl":
        print_jsonl(results)
    else:
        print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
