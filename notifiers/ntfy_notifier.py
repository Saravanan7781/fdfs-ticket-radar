"""High-priority phone push notifications via ntfy.sh (Emergency Siren Alert)."""

import logging
import re
from typing import Optional
import httpx
from config.settings import Settings
from core.models import AlertEvent

logger = logging.getLogger(__name__)


def to_ascii_header(text: str) -> str:
    """Ensure HTTP header strings are pure ASCII to avoid Latin-1 / ASCII encoding errors."""
    return text.encode("ascii", "ignore").decode("ascii").strip()


class NtfyNotifier:
    """Sends lock-screen notifications with custom urgency and 1-tap action buttons."""

    def __init__(self, topic: Optional[str] = None):
        self.topic = (topic or Settings.get_ntfy_topic()).strip().lstrip("/")
        self.url = f"https://ntfy.sh/{self.topic}"

    def send_fdfs_alert(self, alert: AlertEvent) -> bool:
        """Send urgent siren alert with 1-tap booking button."""
        show_type = "⚡ Early Morning FDFS" if alert.is_fdfs else "⏰ Regular Show"
        clean_title = to_ascii_header(f"{'FDFS SIREN' if alert.is_fdfs else 'TICKETS OPEN'}: {alert.movie_name} ({alert.show_time})")

        message = (
            f"🎬 Movie: {alert.movie_name}\n"
            f"📍 District: {alert.district}\n"
            f"🏛️ Theatre: {alert.theatre_name}\n"
            f"⏰ Show: {alert.show_time} ({alert.date}) [{show_type}]\n"
            f"⚡ Platform: {alert.platform}\n\n"
            f"TAP BELOW TO BOOK SEATS NOW!"
        )

        clean_platform = to_ascii_header(alert.platform)
        headers = {
            "Title": clean_title,
            "Priority": "5",  # 5 = Max / Urgent (triggers alarm & overrides DND)
            "Tags": "rotating_light,ticket,alarm_clock" if alert.is_fdfs else "ticket,clapper,white_check_mark",
            "Click": alert.booking_url,
            "Actions": f"view, Book on {clean_platform}, {alert.booking_url}",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    self.url,
                    content=message.encode("utf-8"),
                    headers=headers,
                )
                if resp.status_code == 200:
                    logger.info("Successfully sent emergency phone siren alert via ntfy.sh topic: %s", self.topic)
                    return True
                else:
                    logger.error("Failed to send ntfy alert: HTTP %d %s", resp.status_code, resp.text)
                    return False
        except Exception as e:
            logger.exception("Error dispatching ntfy notification: %s", e)
            return False

    def send_test_alert(self) -> bool:
        """Send an urgent test siren notification to verify user's phone setup."""
        headers = {
            "Title": "FDFS Ticket Radar Test Alert!",
            "Priority": "5",  # Max / Urgent priority so test alert definitely rings and pops up!
            "Tags": "rotating_light,white_check_mark,popcorn",
            "Click": f"https://ntfy.sh/{self.topic}",
            "Actions": f"view, Open ntfy Web, https://ntfy.sh/{self.topic}",
        }
        message = (
            f"Your phone is successfully connected to topic: '{self.topic}'.\n\n"
            "Emergency sirens and 1-tap booking buttons will pop up on your screen when tickets open!"
        )
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self.url, content=message.encode("utf-8"), headers=headers)
                return resp.status_code == 200
        except Exception as e:
            logger.error("Failed test alert: %s", e)
            return False
