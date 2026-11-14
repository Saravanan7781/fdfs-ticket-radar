"""District by Zomato (formerly Paytm Movies & TicketNew) Scanner with Real Showtime & Venue Extraction."""

import json
import logging
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests

from core.models import Show, WatchItem

logger = logging.getLogger(__name__)


class DistrictScanner:
    """Scans District by Zomato for movie releases, venues, and showtimes."""

    BASE_URL = "https://www.district.in"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()

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

    def search_movie(self, movie_name: str, district: str) -> Optional[dict]:
        """Search District movies catalog and construct city-specific movie URL."""
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
            target_clean = movie_name.strip().lower()

            # Find all links containing movie references
            links = soup.find_all("a", href=re.compile(r"/movies/.*-MV\d+", re.I))
            for a in links:
                href = a.get("href", "")
                text = a.get_text(strip=True).lower()
                if target_clean in text or target_clean in href.lower():
                    # Construct the city-specific URL e.g. /movies/scene-movie-tickets-in-coimbatore-MV233181
                    # Remove any existing city injection or add it cleanly
                    base_slug = re.sub(r"-movie-tickets(-in-[a-z0-9-]+)?-MV", f"-movie-tickets-in-{city_slug}-MV", href)
                    full_url = base_slug if base_slug.startswith("http") else f"{self.BASE_URL}{base_slug}"

                    logger.info("Found District city-specific URL for '%s': %s", movie_name, full_url)
                    return {
                        "title": a.get_text(strip=True),
                        "url": full_url,
                        "city_slug": city_slug,
                    }

        except Exception as e:
            logger.error("Error searching District for %s: %s", movie_name, e)

        return None

    def scan_shows(self, watch_item: WatchItem) -> List[Show]:
        """Scan District for real showtimes and venues of a watched movie."""
        movie_url = watch_item.district_url
        city_slug = self._normalize_city(watch_item.district)

        if not movie_url:
            movie_info = self.search_movie(watch_item.movie_name, watch_item.district)
            if not movie_info:
                logger.debug("Movie '%s' not listed on District yet in %s", watch_item.movie_name, watch_item.district)
                return []
            movie_url = movie_info["url"]

        # Ensure movie_url includes the city slug
        if f"-in-{city_slug}-" not in movie_url:
            movie_url = re.sub(r"-movie-tickets(-in-[a-z0-9-]+)?-MV", f"-movie-tickets-in-{city_slug}-MV", movie_url)

        shows: List[Show] = []

        try:
            resp = self.session.get(
                movie_url,
                impersonate="chrome120",
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                logger.debug("District city page status %d for %s", resp.status_code, movie_url)
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
                        locality = data.get("location", {}).get("address", {}).get("addressLocality", "")

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
                logger.info("District parsed %d real shows for '%s' in %s", len(shows), watch_item.movie_name, watch_item.district)

        except Exception as e:
            logger.error("Error parsing District shows for %s: %s", watch_item.movie_name, e)

        return shows
