from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DomainStatus = Literal["valid", "domain_missing", "mx_missing"]
SMTPStatus = Literal["deliverable", "undeliverable", "unknown", "tempfail"]


@dataclass(slots=True)
class MXLookupResult:
    domain: str
    status: DomainStatus
    mx_hosts: list[str] = field(default_factory=list)
    detail: str = ""


@dataclass(slots=True)
class SMTPCheckResult:
    status: SMTPStatus
    detail: str
    code: int | None = None


@dataclass(slots=True)
class EmailCheckResult:
    email: str
    domain: str
    domain_status: DomainStatus
    mx_hosts: list[str]
    smtp_status: SMTPStatus
    smtp_detail: str

    def to_dict(self) -> dict[str, str | list[str]]:
        return {
            "email": self.email,
            "domain": self.domain,
            "domain_status": self.domain_status,
            "mx_hosts": self.mx_hosts,
            "smtp_status": self.smtp_status,
            "smtp_detail": self.smtp_detail,
        }
