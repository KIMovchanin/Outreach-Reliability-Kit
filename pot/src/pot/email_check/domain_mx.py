from __future__ import annotations

import logging
import time

import dns.exception
import dns.resolver

from .models import MXLookupResult


class DomainMXChecker:
    def __init__(
        self,
        timeout: float,
        logger: logging.Logger,
        dns_servers: list[str] | None = None,
        dns_retries: int = 2,
        dns_retry_delay: float = 0.25,
    ) -> None:
        self.timeout = timeout
        self.logger = logger
        self._cache: dict[str, MXLookupResult] = {}
        self._non_cacheable_details = {"таймаут DNS при проверке MX", "DNS nameserver недоступен"}
        self.dns_retries = max(1, dns_retries)
        self.dns_retry_delay = max(0.0, dns_retry_delay)
        self._resolver = dns.resolver.Resolver(configure=True)
        self._resolver.lifetime = timeout
        self._resolver.timeout = timeout
        if dns_servers:
            self._resolver.nameservers = dns_servers
            self.logger.info("Using custom DNS servers: %s", ",".join(dns_servers))

    def lookup(self, domain: str) -> MXLookupResult:
        if domain in self._cache:
            self.logger.debug("MX cache hit for domain=%s", domain)
            return self._cache[domain]

        self.logger.debug("MX cache miss for domain=%s", domain)
        result = self._lookup_uncached(domain)
        if result.detail not in self._non_cacheable_details:
            self._cache[domain] = result
            self.logger.debug("MX cached for domain=%s status=%s", domain, result.status)
        else:
            self.logger.debug("MX not cached for domain=%s detail=%s", domain, result.detail)
        return result

    def _lookup_uncached(self, domain: str) -> MXLookupResult:
        for attempt in range(1, self.dns_retries + 1):
            started = time.monotonic()
            try:
                self.logger.debug("MX lookup start domain=%s attempt=%s", domain, attempt)
                answers = self._resolver.resolve(domain, "MX")
                mx_records: list[tuple[int, str]] = []
                for answer in answers:
                    mx_host = str(answer.exchange).rstrip(".")
                    mx_records.append((int(answer.preference), mx_host))

                mx_hosts = [host for _, host in sorted(mx_records, key=lambda x: x[0]) if host]
                elapsed = time.monotonic() - started
                self.logger.debug(
                    "MX lookup success domain=%s attempt=%s hosts_count=%s elapsed=%.3fs",
                    domain,
                    attempt,
                    len(mx_hosts),
                    elapsed,
                )
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
                elapsed = time.monotonic() - started
                self.logger.warning("No nameservers for domain=%s attempt=%s elapsed=%.3fs", domain, attempt, elapsed)
                if attempt < self.dns_retries:
                    time.sleep(self.dns_retry_delay)
                    continue
                return MXLookupResult(domain=domain, status="mx_missing", detail="DNS nameserver недоступен")
            except (dns.exception.Timeout, dns.resolver.LifetimeTimeout):
                elapsed = time.monotonic() - started
                self.logger.warning("DNS timeout for domain=%s attempt=%s elapsed=%.3fs", domain, attempt, elapsed)
                if attempt < self.dns_retries:
                    time.sleep(self.dns_retry_delay)
                    continue
                return MXLookupResult(domain=domain, status="mx_missing", detail="таймаут DNS при проверке MX")
            except dns.exception.DNSException as exc:
                self.logger.error("DNS error for domain=%s: %s", domain, exc)
                return MXLookupResult(domain=domain, status="mx_missing", detail=f"ошибка DNS: {exc}")

        return MXLookupResult(domain=domain, status="mx_missing", detail="таймаут DNS при проверке MX")
