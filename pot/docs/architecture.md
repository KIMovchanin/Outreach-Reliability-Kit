# POT Architecture: 1200 Outreach Mailboxes

## Цель

Дешево и отказоустойчиво обслуживать ~1200 email-адресов для нескольких клиентов и направлений аутрича, с контролем deliverability и безопасной ротацией.

## Базовая схема

- Контрольная плоскость:
  - Scheduler (cron/Airflow-lite) создает задачи отправки по кампаниям.
  - API/CLI для управления лимитами, паузами, stop-lists и health score.
- Data plane:
  - Очередь задач (`SQS`/`RabbitMQ`) с приоритетами клиентов.
  - Пул воркеров отправки (stateless) обрабатывает сообщения и пишет события.
- Хранилища:
  - `PostgreSQL` (campaigns, mailbox state, quotas, suppression list).
  - `Redis` (rate limits, short locks, idempotency keys).
  - Object storage (логи сырых SMTP/API ответов, короткий retention).

## Учетные записи, секреты, ротация

- Секреты хранить в Secret Manager (или Vault), не в коде/ENV-файлах на проде.
- На каждый mailbox: `health_score`, последние бонсы/жалобы, cooldown.
- Ротация inbox:
  - Warmup 2-4 недели: постепенный рост объема.
  - Лимиты по этапам (например 20 -> 40 -> 80+/день).
  - Auto-pause при ухудшении метрик.
- Разделять клиентов по доменам/поддоменам и sender pools.

## Политика отправки и нагрузка

- Rate limits:
  - per inbox (час/день),
  - per recipient domain,
  - per campaign (burst cap).
- Планировщик выбирает sender из пула по health score + доступному лимиту.
- Retry стратегия: exponential backoff с jitter только для временных ошибок (4xx/API 429).
- Circuit breaker на provider/domain: при серии отказов временно отключать маршрут.

## Мониторинг и SLO

- Технические метрики:
  - SMTP/API error rate, queue lag, worker failures, retry depth.
- Deliverability метрики:
  - bounce rate, spam complaints, unsubscribe rate, reply rate.
  - proxy inbox placement (seed mailboxes, open/reply proxy).
- Репутационные проверки:
  - blacklist мониторинг (Spamhaus и аналоги), DKIM/SPF/DMARC статус.
- Алертинг:
  - Slack/Telegram paging при аномалиях, росте bounce/complaints, деградации очередей.

## Минимальная инфраструктура

- Вариант low-cost:
  - 1 VPS (2-4 vCPU) для воркеров + scheduler,
  - Managed PostgreSQL (small tier),
  - Managed Redis (минимальный tier),
  - S3-compatible storage,
  - Внешний почтовый провайдер/SMTP relay по необходимости.
- Serverless-вариант:
  - Queue + functions + managed DB/Redis,
  - меньше ops, но выше цена при пиках и сложнее отладка.

## Риски и mitigation

- Блокировки провайдерами/доменные санкции: dedicated domains, разделение клиентских пулов.
- DKIM/SPF/DMARC misconfig: автоматические preflight-checks перед запуском кампаний.
- Shared IP reputation: по возможности выделенные IP/домены, не смешивать риск-пулы.
- Утечка токенов/паролей: secret manager, short-lived credentials, audit trail.
- Throttling/429/4xx: adaptive rate limits, backoff, circuit breaker.

## Очень грубая стоимость/мес

- VPS: $15-40
- Managed PostgreSQL: $25-80
- Managed Redis: $15-50
- Monitoring/логирование: $10-60
- Почтовые провайдеры/инфраструктура отправки: сильно зависит от объема, обычно $100+ при масштабировании
- Итого старт: примерно $65-230+ без учета стоимости mailbox-парка и доменов.
