# POT Architecture: 1200 Outreach Mailboxes (Updated)

## Цель

Дешево и отказоустойчиво обслуживать ~1200 email-адресов для нескольких клиентов/направлений, с контролем deliverability и безопасной ротацией.

## Базовая схема

- Control plane:
  - Scheduler формирует задания на отправку и проверку.
  - Политики лимитов/пулов/suppression-листов.
- Data plane:
  - Очередь (`SQS`/`RabbitMQ`) + stateless workers.
  - Отправка и сбор технических событий (SMTP/API ответы).
- Storage:
  - PostgreSQL (campaigns, mailbox state, quotas, suppression).
  - Redis (rate limit counters, locks, idempotency).
  - Object storage для сырых логов с retention.

## Operator tooling (актуально для этого репо)

- CLI-режим:
  - `pot/scripts/check_emails.py`
  - `pot/scripts/send_telegram.py`
- GUI-режим:
  - `gui/pot_gui.py` как операторская оболочка над CLI,
  - чекбоксы/поля для флагов,
  - редактор Telegram-сообщения,
  - live output и быстрая диагностика.

## Аккаунты, секреты, ротация

- Секреты хранить в Secret Manager/Vault (на проде), не в открытых файлах.
- На каждый mailbox вести `health_score`, bounce/complaint историю, cooldown.
- Ротация:
  - warmup 2-4 недели,
  - поэтапный рост лимитов,
  - auto-pause при деградации метрик.

## Нагрузка и лимиты

- Лимиты на 3 уровнях:
  - per inbox,
  - per recipient domain,
  - per campaign.
- Retry только для временных сбоев (4xx/429), с backoff + jitter.
- Circuit breaker для проблемных маршрутов/provider domain.

## Мониторинг

- Технические: queue lag, worker failures, SMTP/API error rate.
- Deliverability: bounce rate, spam complaints, unsubscribe, reply rate.
- Репутация: blacklist checks, SPF/DKIM/DMARC валидность.
- Алертинг: Slack/Telegram для аномалий.

## Риски и mitigation

- Провайдерские блокировки: dedicated domains/pools.
- Ошибки DNS/SPF/DKIM/DMARC: preflight-check перед кампаниями.
- Shared IP reputation: изоляция high-risk трафика.
- Утечки секретов: secret manager, least privilege, audit.
- VPN/route блокировка SMTP 25: fallback на `format+MX` режим и запуск SMTP-check из сети с открытым egress 25.

## Минимальная инфраструктура и стоимость (очень грубо)

- VPS (workers + scheduler): $15-40/мес
- Managed PostgreSQL: $25-80/мес
- Managed Redis: $15-50/мес
- Monitoring/logging: $10-60/мес
- Почтовые провайдеры/доменная инфраструктура: от ~$100+/мес в зависимости от объема

Итого стартовый контур: примерно $65-230+/мес без стоимости mailbox-пула и доменов.
