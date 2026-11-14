"""FDFS (First Day First Show) detection and filtering logic."""

import re
from datetime import datetime
from typing import List, Optional
from core.models import Show, WatchItem


class FDFSDetector:
    """Filters and identifies FDFS and target shows."""

    @staticmethod
    def parse_time_to_minutes(time_str: str) -> Optional[int]:
        """Convert a time string like '04:00 AM' or '07:30' into minutes since midnight."""
        cleaned = time_str.strip().upper()
        # Handle 12-hour format: '04:00 AM' / '4:00AM'
        match_12 = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)?$", cleaned)
        if match_12:
            hours = int(match_12.group(1))
            minutes = int(match_12.group(2))
            meridiem = match_12.group(3)

            if meridiem == "PM" and hours != 12:
                hours += 12
            elif meridiem == "AM" and hours == 12:
                hours = 0
            return hours * 60 + minutes

        return None

    @classmethod
    def is_fdfs_show(cls, show_time: str, max_time_str: str = "08:00") -> bool:
        """Return True if the showtime is early morning (<= max_time_str, e.g. 08:00 AM)."""
        show_minutes = cls.parse_time_to_minutes(show_time)
        max_minutes = cls.parse_time_to_minutes(max_time_str) or (8 * 60)  # Default 8:00 AM

        if show_minutes is None:
            return False

        # Consider shows between 03:00 AM (180m) and 08:00 AM (480m) as typical FDFS
        return show_minutes <= max_minutes

    @classmethod
    def matches_theatre(cls, theatre_name: str, target_theatres: List[str]) -> bool:
        """Check if theatre matches the target list (case-insensitive substring match)."""
        if not target_theatres:
            return True  # Empty means all theatres in the district

        theatre_lower = theatre_name.lower()
        for target in target_theatres:
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

            # 2. Date filter (if target_date is specified)
            if watch_item.target_date and show.date != watch_item.target_date:
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
