from __future__ import annotations

import logging

import dns.exception
import dns.resolver

from .models import MXLookupResult


class DomainMXChecker:
    def __init__(self, timeout: float, logger: logging.Logger) -> None:
        self.timeout = timeout
        self.logger = logger
        self._cache: dict[str, MXLookupResult] = {}
        self._resolver = dns.resolver.Resolver(configure=True)
        self._resolver.lifetime = timeout
        self._resolver.timeout = timeout

    def lookup(self, domain: str) -> MXLookupResult:
        if domain in self._cache:
            return self._cache[domain]

        result = self._lookup_uncached(domain)
        self._cache[domain] = result
        return result

    def _lookup_uncached(self, domain: str) -> MXLookupResult:
        try:
            answers = self._resolver.resolve(domain, "MX")
            mx_records: list[tuple[int, str]] = []
            for answer in answers:
                mx_host = str(answer.exchange).rstrip(".")
                mx_records.append((int(answer.preference), mx_host))

            mx_hosts = [host for _, host in sorted(mx_records, key=lambda x: x[0]) if host]
            if not mx_hosts:
                return MXLookupResult(
                    domain=domain,
                    status="mx_missing",
                    detail="MX-записи отсутствуют или некорректны",
                )
            return MXLookupResult(domain=domain, status="valid", mx_hosts=mx_hosts, detail="MX-записи найдены")
        except dns.resolver.NXDOMAIN:
            return MXLookupResult(domain=domain, status="domain_missing", detail="домен отсутствует")
        except dns.resolver.NoAnswer:
            return MXLookupResult(
                domain=domain,
                status="mx_missing",
                detail="MX-записи отсутствуют или некорректны",
            )
        except dns.resolver.NoNameservers:
            self.logger.warning("No nameservers for domain=%s", domain)
            return MXLookupResult(domain=domain, status="mx_missing", detail="DNS nameserver недоступен")
        except dns.exception.Timeout:
            self.logger.warning("DNS timeout for domain=%s", domain)
            return MXLookupResult(domain=domain, status="mx_missing", detail="таймаут DNS при проверке MX")
        except dns.resolver.LifetimeTimeout:
            self.logger.warning("DNS lifetime timeout for domain=%s", domain)
            return MXLookupResult(domain=domain, status="mx_missing", detail="таймаут DNS при проверке MX")
        except dns.exception.DNSException as exc:
            self.logger.error("DNS error for domain=%s: %s", domain, exc)
            return MXLookupResult(domain=domain, status="mx_missing", detail=f"ошибка DNS: {exc}")
