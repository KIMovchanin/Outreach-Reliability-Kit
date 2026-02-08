from __future__ import annotations

import argparse
import logging
import os
from typing import Sequence

import requests
from dotenv import load_dotenv

from pot.utils.io import read_text
from pot.utils.logging import setup_logging

TELEGRAM_API_BASE = "https://api.telegram.org"
REQUEST_TIMEOUT_SEC = 15


def send_message(token: str, chat_id: str, text: str) -> None:
    logger = logging.getLogger("pot")
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SEC)
    except requests.RequestException as exc:
        logger.error("Telegram request failed: %s", exc)
        raise RuntimeError(f"Telegram request failed: {exc}") from exc

    if response.status_code >= 400:
        logger.error(
            "Telegram API error status=%s body=%s",
            response.status_code,
            response.text,
        )
        raise RuntimeError(f"Telegram API error: HTTP {response.status_code}")

    body = response.json()
    if not body.get("ok"):
        logger.error("Telegram API returned not ok: %s", body)
        raise RuntimeError(f"Telegram API returned not ok: {body}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send message to Telegram via Bot API")
    parser.add_argument("--file", required=True, help="Path to .txt file with message")
    parser.add_argument("--token", help="Telegram bot token (overrides env BOT_TOKEN)")
    parser.add_argument("--chat-id", help="Telegram chat id (overrides env CHAT_ID)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = setup_logging(args.log_level)
    load_dotenv()

    token = args.token or os.getenv("BOT_TOKEN", "")
    chat_id = args.chat_id or os.getenv("CHAT_ID", "")

    if not token or not chat_id:
        print("Ошибка: BOT_TOKEN и CHAT_ID должны быть заданы в env/.env или аргументами --token/--chat-id")
        return 2

    try:
        text = read_text(args.file)
    except FileNotFoundError as exc:
        print(exc)
        return 2

    if not text.strip():
        print("Предупреждение: файл сообщения пустой, отправка отменена")
        return 1

    try:
        send_message(token=token, chat_id=chat_id, text=text)
    except RuntimeError as exc:
        logger.error("Telegram send failed: %s", exc)
        print(f"Ошибка отправки: {exc}")
        return 3

    print("Сообщение успешно отправлено")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
