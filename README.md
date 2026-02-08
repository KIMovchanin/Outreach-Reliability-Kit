# Polza Outreach Toolkit (POT)

Production-oriented toolkit для двух задач:
1. Проверка email адресов: `format -> domain MX -> SMTP RCPT handshake` (без отправки письма)
2. Отправка текста в Telegram-чат через Bot API

Проект сделан как минимально-достаточная, но расширяемая основа для аутрич-интеграций.

## Что внутри

```text
pot/
  README.md
  requirements.txt
  .env.example
  .gitignore
  src/
    pot/
      __init__.py
      cli.py
      email_check/
        models.py
        validator.py
        domain_mx.py
        smtp_handshake.py
      telegram_send/
        sender.py
      utils/
        logging.py
        io.py
  scripts/
    check_emails.py
    send_telegram.py
  docs/
    architecture.md
    ai_stack.md
  data/
    emails.txt
    message.txt
```

## Почему Есть И `src`, И `scripts`

- `src/pot/...` содержит библиотечный код (бизнес-логика, переиспользуемые модули, dataclasses, проверки).
- `scripts/...` содержит тонкие CLI entrypoint-обертки для удобного запуска командами вида `python scripts/...`.

Почему не складывать все в один слой:
- проще тестировать и переиспользовать логику без копипаста;
- CLI остается тонким и не превращается в монолит;
- одинаковые модули можно использовать из GUI, скриптов и будущих сервисов.

Связка по именам намеренно похожая:
- `scripts/check_emails.py` -> `src/pot/cli.py` + `src/pot/email_check/*`
- `scripts/send_telegram.py` -> `src/pot/telegram_send/sender.py`

## Requirements

- Python `3.11+` (проверено на `3.13`)
- Интернет-доступ для DNS/SMTP/Telegram
- Для SMTP handshake: сеть, где открыт исходящий TCP `25`

## Как запустить

### 1) venv

Linux/macOS:

```bash
cd pot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd pot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) env

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=...
CHAT_ID=...
```

### 3) Smoke checks

```bash
python scripts/check_emails.py --self-check
python scripts/send_telegram.py --file data/message.txt
```

## Проверка Email

Entry point: `scripts/check_emails.py`

Поддерживает:
- вход из `--file` (1 email в строке)
- вход из `--emails`
- вывод `table` и `jsonl`
- `MX` lookup с in-memory cache
- SMTP handshake через `EHLO/HELO -> MAIL FROM -> RCPT TO`
- timeout/retry/cooldown
- debug logging в файл

### Поля вывода

- `email`
- `domain`
- `domain_status`: `valid | domain_missing | mx_missing`
- `mx_hosts`
- `smtp_status`: `deliverable | undeliverable | tempfail | unknown`
- `smtp_detail`

### Основные команды

Проверка из файла, таблица:

```bash
python scripts/check_emails.py --file data/emails.txt --format table
```

Проверка из CLI аргументов, JSONL:

```bash
python scripts/check_emails.py --emails a@b.com c@d.com --format jsonl
```

DNS через публичные резолверы:

```bash
python scripts/check_emails.py --file data/emails.txt --dns-server 1.1.1.1 --dns-server 8.8.8.8 --dns-retries 3
```

Только format+MX (без SMTP):

```bash
python scripts/check_emails.py --file data/emails.txt --skip-smtp
```

Быстрый SMTP-режим при нестабильной сети:

```bash
python scripts/check_emails.py --file data/emails.txt --timeout 5 --max-mx-tries 1 --smtp-retries 1 --smtp-host-cooldown 600
```

Debug лог в файл:

```bash
python scripts/check_emails.py --file data/emails.txt --log-level DEBUG --log-file log.txt
```

### CLI Flags (Email)

- `--file`: путь к txt-файлу с email
- `--emails`: список email в CLI
- `--format`: `table` или `jsonl`
- `--timeout`: timeout DNS/SMTP
- `--max-mx-tries`: сколько MX-хостов пробовать
- `--domain-pause`: пауза между email/доменами
- `--mail-from`: адрес для команды `MAIL FROM`
- `--helo-host`: hostname для `EHLO/HELO`
- `--dns-server`: DNS-сервер (повторяемый флаг)
- `--dns-retries`: число DNS retry
- `--skip-smtp`: пропуск SMTP шага
- `--smtp-retries`: число SMTP retry на MX
- `--smtp-host-cooldown`: cooldown хоста после timeout/network fail
- `--log-level`: `DEBUG|INFO|WARNING|ERROR`
- `--log-file`: файл логов
- `--self-check`: встроенная проверка базовой логики

## Отправка в Telegram

Entry point: `scripts/send_telegram.py`

Сценарий:
1. читает текст из `--file`
2. загружает `BOT_TOKEN` / `CHAT_ID` из `.env` (или из `--token`/`--chat-id`)
3. делает `POST` на `https://api.telegram.org/bot<TOKEN>/sendMessage`

### Commands

Из `.env`:

```bash
python scripts/send_telegram.py --file data/message.txt
```

Явно аргументами:

```bash
python scripts/send_telegram.py --file data/message.txt --token <BOT_TOKEN> --chat-id <CHAT_ID>
```

### Получение CHAT_ID

1. Добавить бота в чат/группу
2. Отправить сообщение
3. Открыть:

```text
https://api.telegram.org/bot<TOKEN>/getUpdates
```

4. Взять `message.chat.id`

Подсказка:
- private chat обычно `id > 0`
- group/supergroup обычно `id < 0` (часто `-100...`)

## Logging & Diagnostics

### Email logs

По умолчанию логи пишутся в `log.txt` (если задан `--log-file`).

Пример просмотра:

Linux/macOS:

```bash
tail -n 120 log.txt
```

Windows PowerShell:

```powershell
Get-Content .\log.txt -Tail 120
```

### Что смотреть в логах

Успешный SMTP сценарий:
- `SMTP EHLO ... code=250`
- `SMTP MAIL FROM ... code=250`
- `SMTP RCPT ... code=250`

Проблема сети:
- `SMTP timeout for host=...`
- `SMTP network error ...`
- `skip due to recent timeout (cooldown ...)`

## GUI (Tkinter)

GUI находится в корне репозитория: `gui/pot_gui.py`.

Запуск:

```bash
python "gui/pot_gui.py"
```

Что есть в GUI:
- вкладка `Email Check` со всеми основными CLI-флагами (поля + чекбоксы);
- вкладка `Telegram`:
  - выбор файла сообщения,
  - поля `BOT_TOKEN` и `CHAT_ID`,
  - встроенный редактор текста сообщения,
  - кнопки загрузки текста из файла и сохранения обратно,
  - авто-сохранение текста перед отправкой;
- вкладка `Settings`:
  - переключение `Light/Dark` темы;
- нижняя панель Output:
  - live-логи процесса,
  - код завершения,
  - кнопка остановки текущего процесса.

## Важные ограничения

SMTP handshake не гарантирует фактическое существование mailbox:
- catch-all домены могут возвращать `250` почти для любых адресов
- anti-spam политики могут блокировать RCPT probe
- часть серверов маскирует ответы

### VPN Caveat (важно)

Если включен VPN (или конкретный VPN-сервер), исходящий `TCP 25` может быть заблокирован/ограничен.
Тогда `domain_status` будет `valid`, но `smtp_status` часто станет `unknown` из-за timeout.

Если нужен стабильный SMTP RCPT:
- использовать маршрут/сервер с открытым egress `25`
- или запускать с `--skip-smtp`, если нужна только проверка format+MX

## Code Map

- `src/pot/cli.py` - argparse и orchestration email-check flow
- `src/pot/email_check/models.py` - dataclasses и типы статусов
- `src/pot/email_check/validator.py` - нормализация и формат email
- `src/pot/email_check/domain_mx.py` - DNS MX lookup, retries, cache
- `src/pot/email_check/smtp_handshake.py` - SMTP handshake + status mapping
- `src/pot/telegram_send/sender.py` - Telegram Bot API sender
- `src/pot/utils/logging.py` - единая настройка логирования
- `src/pot/utils/io.py` - безопасное чтение файлов

## Docs

- `docs/architecture.md` - архитектура на 1200 inbox: ротация, мониторинг, queue/workers, риски, стоимость
- `docs/ai_stack.md` - IDE/plugins/models/MCP/cursorrules

## Troubleshooting

`Файл не найден`:
- проверь путь к `--file`

`BOT_TOKEN/CHAT_ID не заданы`:
- проверь `.env` и значения

`Telegram API error: HTTP 401`:
- токен неверный или отозван

`SMTP timeout`:
- проверь VPN/фаервол/провайдера на `TCP 25`
- попробуй `--skip-smtp` или другой сетевой маршрут

## Practical End-to-End Checklist

1. `python scripts/check_emails.py --self-check` -> `SELF-CHECK OK`
2. `python scripts/check_emails.py --file data/emails.txt --format table` -> есть строки результата
3. `python scripts/send_telegram.py --file data/message.txt` -> `Сообщение успешно отправлено`
4. Сообщение реально приходит в Telegram-чат
