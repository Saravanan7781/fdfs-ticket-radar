"""High-priority phone push notifications via ntfy.sh (Emergency Siren Alert)."""

import logging
from typing import Optional
import httpx
from core.models import AlertEvent

logger = logging.getLogger(__name__)


class NtfyNotifier:
    """Sends lock-screen notifications with custom urgency and 1-tap action buttons."""

    def __init__(self, topic: str):
        self.topic = topic.strip().lstrip("/")
        self.url = f"https://ntfy.sh/{self.topic}"

    def send_fdfs_alert(self, alert: AlertEvent) -> bool:
        """Send urgent siren alert with 1-tap booking button."""
        show_type = "⚡ Early Morning FDFS" if alert.is_fdfs else "⏰ Regular Show"
        title = f"{'FDFS SIREN' if alert.is_fdfs else 'TICKETS OPEN'}: {alert.movie_name} ({alert.show_time})"
        message = (
            f"Movie: {alert.movie_name}\n"
            f"District: {alert.district}\n"
            f"Theatre: {alert.theatre_name}\n"
            f"Show: {alert.show_time} ({alert.date}) [{show_type}]\n"
            f"Platform: {alert.platform}\n\n"
            f"TAP BELOW TO BOOK SEATS NOW!"
        )

        # In HTTP/1.1, headers must be ASCII-safe
        headers = {
            "Title": title,
            "Priority": "5",  # 5 = Max / Urgent (triggers alarm & overrides DND)
            "Tags": "rotating_light,ticket,alarm_clock" if alert.is_fdfs else "ticket,clapper,white_check_mark",
            "Actions": f"view, Book on {alert.platform}, {alert.booking_url}",
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
        """Send a test notification to verify user's phone setup."""
        headers = {
            "Title": "FDFS Ticket Radar Connected!",
            "Priority": "4",
            "Tags": "white_check_mark,popcorn",
            "Actions": "view, Open ntfy, https://ntfy.sh",
        }
        message = (
            f"Your phone is successfully subscribed to topic: '{self.topic}'.\n"
            "When tickets open for your target movie, an emergency siren will ring here!"
        )
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self.url, content=message.encode("utf-8"), headers=headers)
                return resp.status_code == 200
        except Exception as e:
            logger.error("Failed test alert: %s", e)
            return False
