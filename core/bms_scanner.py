"""BookMyShow Scanner with Real Showtime & Venue Extraction from JSON State."""

import json
import logging
import re
import time
from typing import List, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests

from core.models import Show, WatchItem

logger = logging.getLogger(__name__)


class BMSScanner:
    """Scans BookMyShow for movie releases, venues, and showtimes."""

    BASE_URL = "https://in.bookmyshow.com"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session: Optional[requests.Session] = None
        self._init_warmed_session()

    def _init_warmed_session(self):
        """Create a session and warm it up on the BMS homepage to acquire Cloudflare bot cookies."""
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://in.bookmyshow.com/",
            "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        })
        try:
            self.session.get(self.BASE_URL, impersonate="chrome120", timeout=self.timeout)
            logger.debug("BMS session warmed up with cookies.")
        except Exception as e:
            logger.warning("BMS session warm-up error: %s", e)

    def _normalize_city(self, city: str) -> tuple[str, str]:
        """Convert city/district name to (city_slug, city_code) tuple."""
        city_clean = city.strip().lower()
        mapping = {
            "chennai": ("chennai", "chen"),
            "coimbatore": ("coimbatore", "coim"),
            "bangalore": ("bengaluru", "bang"),
            "bengaluru": ("bengaluru", "bang"),
            "hyderabad": ("hyderabad", "hyd"),
            "mumbai": ("mumbai", "mumbai"),
            "madurai": ("madurai", "madu"),
            "trichy": ("trichy", "trch"),
            "tiruchirappalli": ("trichy", "trch"),
            "salem": ("salem", "slm"),
            "kochi": ("kochi", "koch"),
            "delhi": ("national-capital-region-ncr", "ncr"),
        }
        return mapping.get(city_clean, (city_clean, city_clean[:4]))

    def search_movie(self, movie_name: str, district: str) -> Optional[dict]:
        """Search BMS explore page for a matching movie title and return URL/event code."""
        city_slug, city_code = self._normalize_city(district)
        explore_url = f"{self.BASE_URL}/explore/movies-{city_slug}"

        for attempt in range(2):
            try:
                resp = self.session.get(
                    explore_url,
                    impersonate="chrome120",
                    timeout=self.timeout,
                )
                if resp.status_code == 403:
                    logger.warning("BMS returned 403, refreshing session...")
                    time.sleep(2)
                    self._init_warmed_session()
                    continue

                if resp.status_code != 200:
                    return None

                soup = BeautifulSoup(resp.text, "html.parser")
                target_clean = movie_name.strip().lower()

                links = soup.find_all("a", href=re.compile(r"/movies/"))
                for a in links:
                    link_text = a.get_text(strip=True).lower()
                    href = a.get("href", "")
                    if target_clean in link_text or target_clean in href.lower():
                        full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                        event_match = re.search(r"(ET\d+)", href)
                        event_code = event_match.group(1) if event_match else None

                        # Extract movie slug
                        slug_match = re.search(r"/movies/([^/]+)/", href)
                        movie_slug = slug_match.group(1) if slug_match else movie_name.lower().replace(" ", "-")

                        logger.info("Found BMS movie: '%s' -> %s", movie_name, full_url)
                        return {
                            "title": a.get_text(strip=True),
                            "url": full_url,
                            "event_code": event_code,
                            "movie_slug": movie_slug,
                            "city_slug": city_slug,
                            "city_code": city_code,
                        }
                break

            except Exception as e:
                logger.error("Error searching BMS for %s: %s", movie_name, e)

        return None

    def scan_shows(self, watch_item: WatchItem) -> List[Show]:
        """Scan BMS for real venues and showtimes."""
        city_slug, city_code = self._normalize_city(watch_item.district)
        event_code = None
        movie_slug = None

        if watch_item.bms_url:
            code_match = re.search(r"(ET\d+)", watch_item.bms_url)
            event_code = code_match.group(1) if code_match else None
            slug_match = re.search(r"/movies/([^/]+)/", watch_item.bms_url)
            movie_slug = slug_match.group(1) if slug_match else watch_item.movie_name.lower().replace(" ", "-")
        else:
            movie_info = self.search_movie(watch_item.movie_name, watch_item.district)
            if movie_info:
                event_code = movie_info["event_code"]
                movie_slug = movie_info["movie_slug"]

        if not event_code or not movie_slug:
            return []

        # Construct buytickets URL
        buytickets_url = f"{self.BASE_URL}/buytickets/{movie_slug}-{city_slug}/movie-{city_code}-{event_code}-MT/"
        shows: List[Show] = []

        try:
            resp = self.session.get(
                buytickets_url,
                impersonate="chrome120",
                timeout=self.timeout,
            )
            if resp.status_code == 403:
                self._init_warmed_session()
                resp = self.session.get(buytickets_url, impersonate="chrome120", timeout=self.timeout)

            if resp.status_code != 200:
                logger.debug("BMS buytickets returned %d", resp.status_code)
                return []

            # Parse JSON __INITIAL_STATE__
            match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*window\.", resp.text) or re.search(
                r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*</script>", resp.text
            )
            if not match:
                return []

            data = json.loads(match.group(1))
            queries = data.get("showtimesFunctionalApi", {}).get("queries", {})

            for qk, qv in queries.items():
                if "fetchPrimaryDynamic" in qk:
                    widgets = qv.get("data", {}).get("data", {}).get("showtimeWidgets", [])
                    for w in widgets:
                        if w.get("type") == "groupList":
                            for grp in w.get("data", []):
                                for item in grp.get("data", []):
                                    header_data = item.get("header", {}).get("data", {})
                                    v_name = None
                                    for comp in header_data.get("components", []):
                                        c_data = comp.get("data", {})
                                        add_data = c_data.get("cta", {}).get("additionalData", {})
                                        if add_data.get("venueName"):
                                            v_name = add_data.get("venueName")
                                            break

                                    if not v_name:
                                        continue

                                    for sec in item.get("showtimesSections", []):
                                        for s_item in sec.get("showtimes", []):
                                            show_time = (
                                                s_item.get("title")
                                                or s_item.get("showTime")
                                                or s_item.get("additionalData", {}).get("showTime")
                                            )
                                            avail = s_item.get("additionalData", {}).get("seatAvalibility", "Available")
                                            show_date = s_item.get("additionalData", {}).get("showDateCode", "")

                                            if show_time:
                                                shows.append(
                                                    Show(
                                                        theatre_name=v_name,
                                                        show_time=show_time,
                                                        date=show_date or watch_item.target_date or "Today",
                                                        screen_format="2D",
                                                        booking_url=resp.url or buytickets_url,
                                                        platform="BookMyShow",
                                                        status=avail,
                                                    )
                                                )

            if shows:
                logger.info("BMS parsed %d real shows for '%s' in %s", len(shows), watch_item.movie_name, watch_item.district)

        except Exception as e:
            logger.error("Error parsing BMS showtimes: %s", e)

        return shows
