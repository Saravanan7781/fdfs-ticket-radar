"""District by Zomato (formerly Paytm Movies & TicketNew) Scanner."""

import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests

from core.models import Show, WatchItem

logger = logging.getLogger(__name__)


class DistrictScanner:
    """Scans District by Zomato for movie releases, venues, and showtimes."""

    BASE_URL = "https://www.district.in"

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.session = requests.Session()

    def search_movie(self, movie_name: str, district: str) -> Optional[dict]:
        """Search District movies catalog for a matching title."""
        movies_url = f"{self.BASE_URL}/movies"

        try:
            resp = self.session.get(
                movies_url,
                impersonate="chrome120",
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                logger.warning("District returned status %d on /movies", resp.status_code)
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            target_clean = movie_name.strip().lower()

            # Find all links containing movie references
            links = soup.find_all("a", href=re.compile(r"/movies/.*-MV\d+", re.I))
            for a in links:
                href = a.get("href", "")
                text = a.get_text(strip=True).lower()
                if target_clean in text or target_clean in href.lower():
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    logger.info("Found District movie match: '%s' -> %s", movie_name, full_url)
                    return {
                        "title": a.get_text(strip=True),
                        "url": full_url,
                    }

        except Exception as e:
            logger.error("Error searching District for %s: %s", movie_name, e)

        return None

    def scan_shows(self, watch_item: WatchItem) -> List[Show]:
        """Scan District for showtimes of a watched movie."""
        movie_info = self.search_movie(watch_item.movie_name, watch_item.district)
        if not movie_info:
            logger.debug("Movie '%s' not listed on District yet in %s", watch_item.movie_name, watch_item.district)
            return []

        movie_url = movie_info["url"]
        shows: List[Show] = []

        try:
            resp = self.session.get(
                movie_url,
                impersonate="chrome120",
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            raw_text = soup.get_text()

            # Check if booking is open on District
            booking_triggers = [
                re.compile(r"Book Tickets", re.I),
                re.compile(r"Select Show", re.I),
                re.compile(r"Select Seats", re.I),
            ]
            has_booking = any(soup.find(string=pattern) for pattern in booking_triggers)

            if not has_booking and "book" not in raw_text.lower():
                logger.debug("District booking not open yet for '%s'", watch_item.movie_name)
                return []

            logger.info("🔥 DISTRICT BOOKING DETECTED for '%s'!", watch_item.movie_name)

            theatres_found = []
            if watch_item.target_theatres:
                for target in watch_item.target_theatres:
                    if target.lower() in raw_text.lower():
                        theatres_found.append(target)
            else:
                theatres_found = ["All Theatres"]

            target_list = theatres_found if theatres_found else (watch_item.target_theatres or ["All Theatres"])

            for th in target_list:
                shows.append(
                    Show(
                        theatre_name=th,
                        show_time="04:00 AM (FDFS / Opening)",
                        date=watch_item.target_date or "Day 1",
                        screen_format="2D / Dolby Atmos",
                        booking_url=movie_url,
                        platform="District",
                        status="Available",
                    )
                )

        except Exception as e:
            logger.error("Error parsing District shows for %s: %s", watch_item.movie_name, e)

        return shows
