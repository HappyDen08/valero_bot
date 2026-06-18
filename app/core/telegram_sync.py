"""Синхронна відправка повідомлень у Telegram (для адмінки та сервісів)."""
import logging
import os
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


VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


def is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


def _send_media(chat_id: int, caption: str, media_path=None, file_id=None, video=False):
    """Відправляє фото або відео. Якщо є file_id — пересилає за ним (без
    перезавантаження файлу). Повертає (успіх, file_id_завантаженого_медіа)."""
    method = "sendVideo" if video else "sendPhoto"
    field = "video" if video else "photo"
    url = API.format(token=settings.BOT_TOKEN, method=method)
    data = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "HTML"}
    try:
        if file_id:
            data[field] = file_id
            r = requests.post(url, data=data, timeout=30)
        else:
            with open(media_path, "rb") as f:
                r = requests.post(url, data=data, files={field: f}, timeout=120)
        if not r.ok:
            logger.warning("%s %s: %s", method, chat_id, r.text)
            return False, None
        result = r.json().get("result", {})
        if video:
            return True, result.get("video", {}).get("file_id")
        photos = result.get("photo", [])
        return True, (photos[-1]["file_id"] if photos else None)
    except (requests.RequestException, OSError):
        logger.exception("Помилка %s %s", method, chat_id)
        return False, None


def broadcast_media(chat_ids: list[int], text: str, media_path=None) -> int:
    """Розсилка тексту або медіа (фото/відео визначається за розширенням) з підписом.
    Медіа вантажиться один раз, далі пересилається за file_id."""
    if not media_path:
        return broadcast(chat_ids, text)
    video = is_video(media_path)
    sent = 0
    file_id = None
    for chat_id in chat_ids:
        ok, new_id = _send_media(chat_id, text, media_path, file_id, video)
        if ok:
            sent += 1
            file_id = file_id or new_id
        time.sleep(0.05)
    return sent
