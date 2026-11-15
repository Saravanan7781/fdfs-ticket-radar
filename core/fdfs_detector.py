"""FDFS (First Day First Show) detection and filtering logic."""

import re
from datetime import datetime
from typing import List, Optional
from core.models import Show, WatchItem


class FDFSDetector:
    """Filters and identifies FDFS and target shows."""

    @staticmethod
    def normalize_date(date_str: Optional[str]) -> str:
        """Standardize any date format to YYYY-MM-DD.

        Handles:
        - '20261115' -> '2026-11-15' (BMS showDateCode)
        - '2026-11-15' -> '2026-11-15' (ISO/District)
        - '2026-11-15T09:00:00' -> '2026-11-15'
        - '15-11-2026' or '15/11/2026' -> '2026-11-15'
        """
        if not date_str:
            return ""

        raw = date_str.strip()
        if "T" in raw:
            raw = raw.split("T")[0]

        digits_only = re.sub(r"[^0-9]", "", raw)
        if len(digits_only) == 8:
            # YYYYMMDD
            if int(digits_only[:4]) >= 2000:
                return f"{digits_only[:4]}-{digits_only[4:6]}-{digits_only[6:8]}"
            # DDMMYYYY
            elif int(digits_only[4:8]) >= 2000:
                return f"{digits_only[4:8]}-{digits_only[2:4]}-{digits_only[0:2]}"

        # Standard YYYY-MM-DD match
        m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        return raw

    @classmethod
    def parse_time_to_minutes(cls, time_str: str) -> Optional[int]:
        """Convert a time string like '04:00 AM', '4:00A.M.', '07:30', or ISO datetime into minutes since midnight."""
        if not time_str:
            return None

        cleaned = time_str.strip()

        # Handle ISO timestamp: '2026-11-15T04:00:00'
        if "T" in cleaned:
            try:
                dt = datetime.fromisoformat(cleaned)
                return dt.hour * 60 + dt.minute
            except Exception:
                cleaned = cleaned.split("T")[-1]

        # Standardize meridiem (e.g. A.M., P.M., am, pm, attached to digits)
        cleaned = re.sub(r"(?i)[pP]\.?[mM]\.?", " PM", cleaned)
        cleaned = re.sub(r"(?i)[aA]\.?[mM]\.?", " AM", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().upper()

        # Handle 12-hour format: '04:00 AM', '4:00AM', '04:00:00 AM'
        match_12 = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?$", cleaned)
        if match_12:
            hours = int(match_12.group(1))
            minutes = int(match_12.group(2))
            meridiem = match_12.group(3)

            if meridiem == "PM" and hours != 12:
                hours += 12
            elif meridiem == "AM" and hours == 12:
                hours = 0
            return hours * 60 + minutes

        # Handle 24-hour format: '04:00' or '14:30'
        match_24 = re.match(r"^(\d{1,2}):(\d{2})$", cleaned)
        if match_24:
            hours = int(match_24.group(1))
            minutes = int(match_24.group(2))
            return hours * 60 + minutes

        return None

    @classmethod
    def is_fdfs_show(cls, show_time: str, max_time_str: str = "08:00") -> bool:
        """Return True if the showtime is early morning (<= max_time_str, e.g. 08:00 AM)."""
        show_minutes = cls.parse_time_to_minutes(show_time)
        max_minutes = cls.parse_time_to_minutes(max_time_str) or (8 * 60)  # Default 8:00 AM

        if show_minutes is None:
            return False

        # Consider shows up to max_time (e.g. 12:30 AM midnight special up to 08:00 AM)
        return show_minutes <= max_minutes

    @classmethod
    def matches_theatre(cls, theatre_name: str, target_theatres: List[str]) -> bool:
        """Check if theatre matches the target list (case-insensitive substring match)."""
        if not target_theatres:
            return True  # Empty means all theatres in the district

        theatre_lower = theatre_name.lower()
        for target in target_theatres:
            if not target or not target.strip():
                continue
            if target.strip().lower() in theatre_lower:
                return True
        return False

    @classmethod
    def filter_shows(cls, shows: List[Show], watch_item: WatchItem) -> List[Show]:
        """Filter a list of raw shows according to user's criteria."""
        matched = []
        for show in shows:
            # 1. Theatre filter
            if not cls.matches_theatre(show.theatre_name, watch_item.target_theatres):
                continue

            # 2. Date filter (with bulletproof normalization across formats)
            if watch_item.target_date:
                norm_watch_date = cls.normalize_date(watch_item.target_date)
                norm_show_date = cls.normalize_date(show.date)
                if norm_watch_date and norm_show_date and norm_watch_date != norm_show_date:
                    continue

            # 3. FDFS filter
            if watch_item.fdfs_only:
                if not cls.is_fdfs_show(show.show_time, watch_item.fdfs_max_time):
                    continue
                show.is_fdfs = True
            else:
                show.is_fdfs = cls.is_fdfs_show(show.show_time, watch_item.fdfs_max_time)

            # 4. Availability check (ignore sold out)
            if "sold" in show.status.lower():
                continue

            matched.append(show)

        return matched
