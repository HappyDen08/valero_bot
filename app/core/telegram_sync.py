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


def _send_photo(chat_id: int, caption: str, image_path=None, file_id=None):
    """Відправляє фото. Якщо є file_id — пересилає за ним (без перезавантаження файлу).
    Повертає (успіх, file_id_завантаженого_фото)."""
    url = API.format(token=settings.BOT_TOKEN, method="sendPhoto")
    data = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "HTML"}
    try:
        if file_id:
            data["photo"] = file_id
            r = requests.post(url, data=data, timeout=20)
        else:
            with open(image_path, "rb") as f:
                r = requests.post(url, data=data, files={"photo": f}, timeout=60)
        if not r.ok:
            logger.warning("sendPhoto %s: %s", chat_id, r.text)
            return False, None
        photos = r.json().get("result", {}).get("photo", [])
        return True, (photos[-1]["file_id"] if photos else None)
    except (requests.RequestException, OSError):
        logger.exception("Помилка sendPhoto %s", chat_id)
        return False, None


def broadcast_media(chat_ids: list[int], text: str, image_path=None) -> int:
    """Розсилка тексту або фото з підписом. Фото вантажиться один раз,
    далі пересилається за file_id. Повертає кількість доставлених."""
    if not image_path:
        return broadcast(chat_ids, text)
    sent = 0
    file_id = None
    for chat_id in chat_ids:
        ok, new_id = _send_photo(chat_id, text, image_path, file_id)
        if ok:
            sent += 1
            file_id = file_id or new_id
        time.sleep(0.05)
    return sent
