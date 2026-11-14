"""Optional Telegram notifier for FDFS Ticket Radar."""

import logging
from typing import Optional
import httpx
from core.models import AlertEvent

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Delivers FDFS ticket alerts to a Telegram chat or channel."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_fdfs_alert(self, alert: AlertEvent) -> bool:
        """Send formatted HTML alert to Telegram."""
        if not self.is_configured:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        text = (
            f"🚨 <b>FDFS TICKET ALERT!</b> 🚨\n\n"
            f"🎬 <b>Movie:</b> {alert.movie_name}\n"
            f"📍 <b>District:</b> {alert.district}\n"
            f"🏛️ <b>Theatre:</b> <code>{alert.theatre_name}</code>\n"
            f"⏰ <b>Show Time:</b> <b>{alert.show_time}</b> ({alert.date})\n"
            f"⚡ <b>Platform:</b> <b>{alert.platform}</b>\n\n"
            f"👉 <a href='{alert.booking_url}'><b>CLICK HERE TO BOOK SEATS NOW</b></a>"
        )

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.error("Failed sending Telegram alert: %s", e)
            return False
