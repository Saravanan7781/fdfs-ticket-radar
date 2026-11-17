"""High-priority phone push notifications via ntfy.sh (Emergency Siren Alert)."""

import logging
import re
from typing import List, Optional
from curl_cffi import requests as cffi_requests
import httpx
from config.settings import Settings
from core.models import AlertEvent, Show

logger = logging.getLogger(__name__)


def to_ascii_header(text: str) -> str:
    """Ensure HTTP header strings are pure ASCII to avoid Latin-1 / ASCII encoding errors."""
    return text.encode("ascii", "ignore").decode("ascii").strip()


class NtfyNotifier:
    """Sends lock-screen notifications with custom urgency and 1-tap action buttons."""

    def __init__(self, topic: Optional[str] = None):
        self.topic = (topic or Settings.get_ntfy_topic()).strip().lstrip("/")
        self.url = f"https://ntfy.sh/{self.topic}"

    def _dispatch(self, headers: dict, message: str) -> bool:
        """Internal helper to dispatch ntfy request via curl_cffi with httpx fallback."""
        # 1. Primary: Use curl_cffi with Chrome 120 TLS fingerprint
        try:
            resp = cffi_requests.post(
                self.url,
                data=message.encode("utf-8"),
                headers=headers,
                impersonate="chrome120",
                timeout=12,
            )
            if resp.status_code == 200:
                logger.info("Successfully sent phone siren alert via ntfy.sh topic: %s", self.topic)
                return True
            else:
                logger.warning("cffi_requests status %d, trying httpx fallback...", resp.status_code)
        except Exception as e:
            logger.warning("cffi_requests exception: %s, trying httpx fallback...", e)

        # 2. Fallback: Standard httpx
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self.url, content=message.encode("utf-8"), headers=headers)
                if resp.status_code == 200:
                    logger.info("Successfully sent alert via httpx to topic: %s", self.topic)
                    return True
                else:
                    logger.error("Failed to send ntfy alert via httpx: HTTP %d %s", resp.status_code, resp.text)
                    return False
        except Exception as e:
            logger.exception("Error dispatching ntfy notification: %s", e)
            return False

    def send_matched_shows_alert(
        self,
        movie_name: str,
        district: str,
        shows: List[Show],
        is_fdfs: bool = False,
        is_manual_scan: bool = False,
    ) -> bool:
        """Send a single consolidated emergency siren notification grouping all newly opened theatres and showtimes."""
        if not shows:
            return False

        # Group shows by theatre name
        theatre_map = {}
        platforms_seen = set()
        for s in shows:
            clean_theatre = s.theatre_name.split(":")[0].strip()
            theatre_map.setdefault(clean_theatre, []).append(s.show_time)
            platforms_seen.add(s.platform)

        theatre_lines = []
        for th, times in sorted(theatre_map.items()):
            distinct_times = sorted(set(times))
            times_str = ", ".join(distinct_times[:5])
            if len(distinct_times) > 5:
                times_str += f" (+{len(distinct_times)-5} more)"
            theatre_lines.append(f"• {th}: {times_str}")

        theatres_summary = "\n".join(theatre_lines[:8])
        if len(theatre_lines) > 8:
            theatres_summary += f"\n...and {len(theatre_lines)-8} other theatre(s)"

        platforms_str = ", ".join(sorted(platforms_seen)) or "BookMyShow / District"

        prefix = "FDFS SIREN" if is_fdfs else "TICKETS OPEN"
        if is_manual_scan:
            prefix = f"SCAN NOW - {prefix}"
        clean_title = to_ascii_header(f"{prefix}: {movie_name} ({district})")

        message = (
            f"🎬 Movie: {movie_name}\n"
            f"📍 District: {district}\n"
            f"🔥 {len(shows)} MATCHING SHOW(S) OPEN FOR BOOKING!\n\n"
            f"🏛️ Theatres & Showtimes:\n"
            f"{theatres_summary}\n\n"
            f"⚡ Available on: {platforms_str}\n"
            f"👉 TAP BELOW TO BOOK SEATS NOW!"
        )

        # Build direct 1-tap action buttons for BMS and District
        bms_url = next((s.booking_url for s in shows if "bookmyshow" in s.platform.lower() and s.booking_url), None)
        dist_url = next((s.booking_url for s in shows if "district" in s.platform.lower() and s.booking_url), None)

        actions = []
        if bms_url:
            actions.append(f"view, Book on BookMyShow, {bms_url}")
        if dist_url:
            actions.append(f"view, Book on District, {dist_url}")

        top_click_url = bms_url or dist_url or f"https://ntfy.sh/{self.topic}"

        headers = {
            "Title": clean_title,
            "Priority": "5",  # 5 = Max / Urgent (triggers alarm & overrides DND)
            "Tags": "rotating_light,ticket,alarm_clock" if is_fdfs else "ticket,clapper,fire",
            "Click": top_click_url,
        }
        if actions:
            headers["Actions"] = "; ".join(actions)

        return self._dispatch(headers, message)

    def send_filter_advisory_alert(
        self,
        movie_name: str,
        district: str,
        shows: List[Show],
        fdfs_max_time: str = "08:00",
    ) -> bool:
        """Send high-priority advisory when regular shows open in the district/theatre but FDFS filter is ON."""
        if not shows:
            return False

        theatre_map = {}
        for s in shows:
            th = s.theatre_name.split(":")[0].strip()
            theatre_map.setdefault(th, []).append(s.show_time)

        lines = [f"• {th}: {', '.join(sorted(set(t))[:3])}" for th, t in sorted(theatre_map.items())[:5]]
        theatre_summary = "\n".join(lines)

        bms_url = next((s.booking_url for s in shows if "bookmyshow" in s.platform.lower() and s.booking_url), None)
        dist_url = next((s.booking_url for s in shows if "district" in s.platform.lower() and s.booking_url), None)
        top_url = bms_url or dist_url or f"https://ntfy.sh/{self.topic}"

        clean_title = to_ascii_header(f"REGULAR SHOWS OPEN: {movie_name} ({district})")
        message = (
            f"🎬 Movie: {movie_name}\n"
            f"📍 District: {district}\n"
            f"⚠️ {len(shows)} Regular Show(s) Just Released!\n\n"
            f"🏛️ Theatres:\n{theatre_summary}\n\n"
            f"ℹ️ Your radar filter is currently set to 'Early Morning FDFS (<= {fdfs_max_time})'.\n"
            f"👉 Open dashboard and switch to 'All Shows' to trigger full sirens for these showtimes!"
        )

        headers = {
            "Title": clean_title,
            "Priority": "4",  # High priority notification banner
            "Tags": "information_source,ticket,eyes",
            "Click": top_url,
        }
        actions = []
        if bms_url:
            actions.append(f"view, Book on BMS, {bms_url}")
        if dist_url:
            actions.append(f"view, Book on District, {dist_url}")
        if actions:
            headers["Actions"] = "; ".join(actions)

        return self._dispatch(headers, message)

    def send_fdfs_alert(self, alert: AlertEvent) -> bool:
        """Send urgent siren alert for a single show event."""
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
        return self._dispatch(headers, message)

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
        return self._dispatch(headers, message)
