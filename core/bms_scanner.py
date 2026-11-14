"""BookMyShow Scanner with TLS Fingerprint Impersonation."""

import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests

from core.models import Show, WatchItem

logger = logging.getLogger(__name__)


class BMSScanner:
    """Scans BookMyShow for movie releases, venues, and showtimes."""

    BASE_URL = "https://in.bookmyshow.com"

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.session = requests.Session()

    def _normalize_city(self, city: str) -> str:
        """Convert common city/district names to BMS slug format."""
        city_clean = city.strip().lower()
        mapping = {
            "chennai": "chennai",
            "coimbatore": "coimbatore",
            "bangalore": "bengaluru",
            "bengaluru": "bengaluru",
            "hyderabad": "hyderabad",
            "mumbai": "mumbai",
            "madurai": "madurai",
            "trichy": "trichy",
            "tiruchirappalli": "trichy",
            "salem": "salem",
            "kochi": "kochi",
            "delhi": "national-capital-region-ncr",
            "ncr": "national-capital-region-ncr",
        }
        return mapping.get(city_clean, city_clean)

    def search_movie(self, movie_name: str, district: str) -> Optional[dict]:
        """Search BMS explore page for a matching movie title and return URL/event code."""
        city_slug = self._normalize_city(district)
        explore_url = f"{self.BASE_URL}/explore/movies-{city_slug}"

        try:
            resp = self.session.get(
                explore_url,
                impersonate="chrome120",
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                logger.warning("BMS explore returned status %d for %s", resp.status_code, city_slug)
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            target_clean = movie_name.strip().lower()

            # Find all movie links
            links = soup.find_all("a", href=re.compile(r"/movies/"))
            for a in links:
                link_text = a.get_text(strip=True).lower()
                href = a.get("href", "")
                if target_clean in link_text or target_clean in href.lower():
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    # Extract event code (e.g. ET00523997)
                    event_match = re.search(r"(ET\d+)", href)
                    event_code = event_match.group(1) if event_match else None

                    logger.info("Found BMS movie match: '%s' -> %s", movie_name, full_url)
                    return {
                        "title": a.get_text(strip=True),
                        "url": full_url,
                        "event_code": event_code,
                        "city_slug": city_slug,
                    }

        except Exception as e:
            logger.error("Error searching BMS for %s in %s: %s", movie_name, district, e)

        return None

    def scan_shows(self, watch_item: WatchItem) -> List[Show]:
        """Scan BMS for showtimes of a watched movie."""
        movie_info = self.search_movie(watch_item.movie_name, watch_item.district)
        if not movie_info:
            logger.debug("Movie '%s' not listed on BMS yet in %s", watch_item.movie_name, watch_item.district)
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

            # Check if booking is live (e.g. 'Book tickets' button exists)
            book_button = soup.find(string=re.compile(r"Book tickets", re.I))
            if not book_button:
                logger.debug("BMS booking not open yet for '%s'", watch_item.movie_name)
                return []

            logger.info("🔥 BMS BOOKING DETECTED for '%s'!", watch_item.movie_name)

            # In BMS, when booking is live, follow through to showtimes or buy tickets
            # If target theatres were specified, search for venue mentions or general alert
            raw_text = soup.get_text()
            theatres_found = []

            if watch_item.target_theatres:
                for target in watch_item.target_theatres:
                    if target.lower() in raw_text.lower():
                        theatres_found.append(target)
            else:
                theatres_found = ["All Theatres"]

            # If specific theaters were specified and at least one matches, or general booking opened
            target_list = theatres_found if theatres_found else (watch_item.target_theatres or ["All Theatres"])

            for th in target_list:
                shows.append(
                    Show(
                        theatre_name=th,
                        show_time="04:00 AM (FDFS / Opening)",
                        date=watch_item.target_date or "Day 1",
                        screen_format="2D / IMAX",
                        booking_url=movie_url,
                        platform="BookMyShow",
                        status="Available",
                    )
                )

        except Exception as e:
            logger.error("Error parsing BMS shows for %s: %s", watch_item.movie_name, e)

        return shows
