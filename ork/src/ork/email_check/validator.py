from __future__ import annotations

import re
from typing import Iterable

_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def is_valid_email_format(email: str) -> bool:
    return bool(_EMAIL_PATTERN.match(email))


def extract_domain(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].strip().lower()


def collect_emails(cli_emails: Iterable[str], file_emails: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in [*file_emails, *cli_emails]:
        email = normalize_email(raw)
        if not email or email in seen:
            continue
        ordered.append(email)
        seen.add(email)
    return ordered
