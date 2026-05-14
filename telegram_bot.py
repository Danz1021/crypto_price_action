"""
telegram_bot.py — Telegram 訊息發送模組
"""

import logging
import requests

logger = logging.getLogger(__name__)


class TelegramBot:

    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = chat_id
        self.base    = f"https://api.telegram.org/bot{token}"

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        url = f"{self.base}/sendMessage"
        payload = {
            "chat_id":    self.chat_id,
            "text":       text,
            "parse_mode": parse_mode,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            data = resp.json()
            if not data.get("ok"):
                logger.error("Telegram send failed: %s", data)
                return False
            logger.info("Telegram message sent (msg_id=%s)", data["result"]["message_id"])
            return True
        except Exception as exc:
            logger.error("Telegram exception: %s", exc)
            return False

    def test_connection(self) -> bool:
        """驗證 Token 與 Chat ID 是否正確"""
        try:
            resp = requests.get(f"{self.base}/getMe", timeout=10)
            return resp.json().get("ok", False)
        except Exception:
            return False
