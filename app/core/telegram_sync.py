"""Синхронна відправка повідомлень у Telegram (для адмінки та сервісів)."""
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    if not settings.BOT_TOKEN:
        logger.warning("BOT_TOKEN не задано, повідомлення не відправлено")
        return False
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(
            API.format(token=settings.BOT_TOKEN, method="sendMessage"),
            json=payload, timeout=10,
        )
        if not r.ok:
            logger.warning("sendMessage %s: %s", chat_id, r.text)
        return r.ok
    except requests.RequestException:
        logger.exception("Помилка відправки повідомлення %s", chat_id)
        return False


def broadcast(chat_ids: list[int], text: str) -> int:
    """Розсилка з паузою під ліміти Telegram (~30 msg/s). Повертає кількість доставлених."""
    sent = 0
    for chat_id in chat_ids:
        if send_message(chat_id, text):
            sent += 1
        time.sleep(0.05)
    return sent
