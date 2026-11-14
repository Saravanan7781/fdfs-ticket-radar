"""BookMyShow Scanner with Real Showtime & Venue Extraction from JSON State."""

import json
import logging
import re
import time
from typing import List, Optional, Union
from bs4 import BeautifulSoup
from curl_cffi import requests

from core.models import Show, WatchItem, build_movie_regex

logger = logging.getLogger(__name__)


class BMSScanner:
    """Scans BookMyShow for movie releases, venues, and showtimes."""

    BASE_URL = "https://in.bookmyshow.com"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session: Optional[requests.Session] = None
        self.last_url: str = ""
        self.last_status: str = "Idle"
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

    def search_movie(self, movie_target: Union[str, WatchItem], district: str) -> Optional[dict]:
        """Search BMS explore and upcoming pages using regex matching for title and URL."""
        if isinstance(movie_target, WatchItem):
            pat = movie_target.get_regex_pattern()
            movie_display_name = movie_target.movie_name
        else:
            pat = build_movie_regex(movie_target)
            movie_display_name = movie_target

        city_slug, city_code = self._normalize_city(district)
        urls_to_check = [
            f"{self.BASE_URL}/explore/movies-{city_slug}",
            f"{self.BASE_URL}/explore/upcoming-movies-{city_slug}",
        ]

        for explore_url in urls_to_check:
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
                        break

                    soup = BeautifulSoup(resp.text, "html.parser")

                    links = soup.find_all("a", href=re.compile(r"/movies/"))
                    for a in links:
                        link_text = a.get_text(separator=" ", strip=True)
                        href = a.get("href", "")
                        if pat.search(link_text) or pat.search(href):
                            full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                            m = re.search(r"(?:/movies/)?(?:[^/]+/)*([^/]+)/(ET\d+)", full_url)
                            if m:
                                movie_slug = m.group(1)
                                event_code = m.group(2)
                            else:
                                event_match = re.search(r"(ET\d+)", href)
                                event_code = event_match.group(1) if event_match else None
                                slug_match = re.search(r"/movies/([^/]+)/", href)
                                movie_slug = slug_match.group(1) if slug_match else movie_display_name.lower().replace(" ", "-")

                            logger.info("Found BMS movie regex match: '%s' (matched '%s') -> %s", movie_display_name, link_text, full_url)
                            return {
                                "title": link_text,
                                "url": full_url,
                                "event_code": event_code,
                                "movie_slug": movie_slug,
                                "city_slug": city_slug,
                                "city_code": city_code,
                            }
                    break

                except Exception as e:
                    logger.error("Error searching BMS for %s: %s", movie_display_name, e)

        return None

    def scan_shows(self, watch_item: WatchItem) -> List[Show]:
        """Scan BMS for real venues and showtimes."""
        city_slug, city_code = self._normalize_city(watch_item.district)
        event_code = None
        movie_slug = None

        if watch_item.bms_url:
            self.last_url = watch_item.bms_url
            m = re.search(r"(?:/movies/)?(?:[^/]+/)*([^/]+)/(ET\d+)", watch_item.bms_url)
            if m:
                movie_slug = m.group(1)
                event_code = m.group(2)
            else:
                code_match = re.search(r"(ET\d+)", watch_item.bms_url)
                event_code = code_match.group(1) if code_match else None
                slug_match = re.search(r"/movies/([^/]+)/", watch_item.bms_url)
                movie_slug = slug_match.group(1) if slug_match else watch_item.movie_name.lower().replace(" ", "-")
        else:
            movie_info = self.search_movie(watch_item, watch_item.district)
            if movie_info:
                self.last_url = movie_info["url"]
                event_code = movie_info["event_code"]
                movie_slug = movie_info["movie_slug"]
            else:
                self.last_url = f"{self.BASE_URL}/explore/movies-{city_slug}"
                self.last_status = "⏳ Not Listed on BMS Yet (Scanning City Catalog)"
                return []

        if not event_code or not movie_slug:
            self.last_status = "⏳ Found Movie Page (Awaiting Showtimes)"
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

            # Update last_url to the actual resolved showtimes page if valid
            if resp.status_code == 200:
                self.last_url = resp.url or buytickets_url
            elif resp.status_code == 404:
                self.last_status = "⏳ Tickets Not Open Yet (Coming Soon / No Shows)"
                return []

            match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*window\.", resp.text) or re.search(
                r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*</script>", resp.text
            )
            if not match:
                self.last_status = "⏳ Not Open Yet (Coming Soon / Interested)"
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
                                                        booking_url=self.last_url,
                                                        platform="BookMyShow",
                                                        status=avail,
                                                    )
                                                )

            if shows:
                self.last_status = f"🔥 BOOKING OPEN ({len(shows)} shows found)"
                logger.info("BMS parsed %d real shows for '%s' in %s", len(shows), watch_item.movie_name, watch_item.district)
            else:
                self.last_status = "⏳ Not Open Yet (No Showtimes Available)"

        except Exception as e:
            self.last_status = f"Error scanning ({e})"
            logger.error("Error parsing BMS showtimes: %s", e)

        return shows
