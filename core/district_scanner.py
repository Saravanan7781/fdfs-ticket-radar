"""District by Zomato (formerly Paytm Movies & TicketNew) Scanner with Real Showtime & Venue Extraction."""

import json
import logging
import re
from datetime import datetime
from typing import List, Optional, Union
from bs4 import BeautifulSoup
from curl_cffi import requests

from core.models import Show, WatchItem, build_movie_regex

logger = logging.getLogger(__name__)


class DistrictScanner:
    """Scans District by Zomato for movie releases, venues, and showtimes."""

    BASE_URL = "https://www.district.in"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.last_url: str = ""
        self.last_status: str = "Idle"

    def _normalize_city(self, city: str) -> str:
        """Convert common city/district names to District slug format."""
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
            "delhi": "delhi-ncr",
        }
        return mapping.get(city_clean, city_clean)

    def search_movie(self, movie_target: Union[str, WatchItem], district: str) -> Optional[dict]:
        """Search District movies catalog and construct city-specific movie URL using regex matching."""
        if isinstance(movie_target, WatchItem):
            pat = movie_target.get_regex_pattern()
            movie_display_name = movie_target.movie_name
        else:
            pat = build_movie_regex(movie_target)
            movie_display_name = movie_target

        movies_url = f"{self.BASE_URL}/movies"
        city_slug = self._normalize_city(district)

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

            links = soup.find_all("a", href=re.compile(r"/movies/.*-MV\d+", re.I))
            for a in links:
                href = a.get("href", "")
                text = a.get_text(separator=" ", strip=True)
                if pat.search(text) or pat.search(href):
                    base_slug = re.sub(r"-movie-tickets(-in-[a-z0-9-]+)?-MV", f"-movie-tickets-in-{city_slug}-MV", href)
                    full_url = base_slug if base_slug.startswith("http") else f"{self.BASE_URL}{base_slug}"

                    logger.info("Found District movie regex match: '%s' (matched '%s') -> %s", movie_display_name, text, full_url)
                    return {
                        "title": text,
                        "url": full_url,
                        "city_slug": city_slug,
                    }

        except Exception as e:
            logger.error("Error searching District for %s: %s", movie_display_name, e)

        return None

    def scan_shows(self, watch_item: WatchItem) -> List[Show]:
        """Scan District for real showtimes and venues of a watched movie."""
        movie_url = watch_item.district_url
        city_slug = self._normalize_city(watch_item.district)

        if not movie_url:
            movie_info = self.search_movie(watch_item, watch_item.district)
            if not movie_info:
                self.last_url = f"{self.BASE_URL}/movies"
                self.last_status = "⏳ Not Listed on District Yet (Scanning Catalog)"
                return []
            movie_url = movie_info["url"]

        # Ensure movie_url includes the city slug
        if f"-in-{city_slug}-" not in movie_url:
            movie_url = re.sub(r"-movie-tickets(-in-[a-z0-9-]+)?-MV", f"-movie-tickets-in-{city_slug}-MV", movie_url)

        self.last_url = movie_url
        shows: List[Show] = []

        try:
            resp = self.session.get(
                movie_url,
                impersonate="chrome120",
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                self.last_status = f"⏳ Tickets Not Released Yet (HTTP {resp.status_code})"
                return []

            soup = BeautifulSoup(resp.text, "html.parser")

            # Parse all schema.org ScreeningEvent blocks for 100% accurate showtimes & venues
            for sc in soup.find_all("script", type="application/ld+json"):
                if not sc.string:
                    continue
                try:
                    data = json.loads(sc.string)
                    if data.get("@type") == "ScreeningEvent":
                        start_iso = data.get("startDate", "")
                        dt = datetime.fromisoformat(start_iso)
                        time_str = dt.strftime("%I:%M %p")
                        date_str = dt.strftime("%Y-%m-%d")

                        cinema_name = data.get("location", {}).get("name", "Unknown Cinema")

                        shows.append(
                            Show(
                                theatre_name=cinema_name,
                                show_time=time_str,
                                date=date_str,
                                screen_format=data.get("name", "2D"),
                                booking_url=movie_url,
                                platform="District",
                                status="Available",
                            )
                        )
                except Exception:
                    continue

            if shows:
                self.last_status = f"🔥 BOOKING OPEN ({len(shows)} shows found)"
                logger.info("District parsed %d real shows for '%s' in %s", len(shows), watch_item.movie_name, watch_item.district)
            else:
                self.last_status = "⏳ Not Open Yet (Coming Soon / No Shows)"

        except Exception as e:
            self.last_status = f"Error scanning ({e})"
            logger.error("Error parsing District shows for %s: %s", watch_item.movie_name, e)

        return shows
