"""Data models for FDFS Ticket Radar."""

import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


def build_movie_regex(movie_pattern: str) -> re.Pattern:
    """Build a robust regex pattern from user input, supporting explicit regex or smart auto-regex."""
    raw = movie_pattern.strip()

    # Check if user explicitly wrote regex symbols
    has_regex_chars = any(c in raw for c in [r".*", r"\s", r"|", r"[", r"]", r"(", r")", r"\d", r"+", r"?", r"\\"])

    if has_regex_chars:
        # Check if user already provided boundaries
        if r"\b" in raw or "^" in raw or "$" in raw:
            try:
                return re.compile(raw, re.IGNORECASE)
            except re.error:
                pass
        else:
            try:
                bounded = rf"(?:^|[^a-zA-Z0-9])(?:{raw})(?:[^a-zA-Z0-9]|$)"
                return re.compile(bounded, re.IGNORECASE)
            except re.error:
                try:
                    return re.compile(raw, re.IGNORECASE)
                except re.error:
                    pass

    # Smart auto-regex: handles punctuation, dots (O.M -> OM / O.M / O-M), hyphens, spaces, stop words
    tokens = re.split(r"[\s\.\-_:]+", raw)
    tokens = [re.escape(t) for t in tokens if t]

    if not tokens:
        return re.compile(re.escape(raw), re.IGNORECASE)

    sep = r"[\s\.\-_&:,]*(?:and\s+|the\s+)?"
    body = sep.join(tokens)
    pattern = rf"(?:^|[^a-zA-Z0-9])({body})(?:[^a-zA-Z0-9]|$)"
    return re.compile(pattern, re.IGNORECASE)


class Show(BaseModel):
    """Represents a specific movie showtime at a venue."""

    theatre_name: str
    show_time: str  # e.g., "04:00 AM" or "07:15 AM"
    date: str  # YYYY-MM-DD
    screen_format: str = "2D"  # e.g., "Tamil 2D", "IMAX"
    booking_url: str  # Direct URL to book on BMS or District
    platform: str  # "BookMyShow" or "District"
    is_fdfs: bool = False
    status: str = "Available"  # "Available", "Fast Filling"


class WatchItem(BaseModel):
    """Represents a movie and district being monitored."""

    id: str
    movie_name: str
    movie_regex: Optional[str] = None  # Optional explicit regex override
    district: str  # e.g., "Chennai", "Coimbatore"
    target_theatres: List[str] = Field(default_factory=list)  # Empty means ALL
    target_date: Optional[str] = None  # YYYY-MM-DD
    fdfs_only: bool = True
    fdfs_max_time: str = "08:00"  # Show time at or before 08:00 AM qualifies as FDFS
    bms_url: Optional[str] = None  # Direct BookMyShow movie/booking URL (optional)
    district_url: Optional[str] = None  # Direct District movie/booking URL (optional)
    enabled: bool = True

    def get_regex_pattern(self) -> re.Pattern:
        """Return compiled regex pattern for movie matching."""
        pattern_str = self.movie_regex if self.movie_regex else self.movie_name
        return build_movie_regex(pattern_str)

    def matches_title_or_url(self, text: str, url: str = "") -> bool:
        """Check if candidate text or URL matches this movie's regex pattern."""
        pat = self.get_regex_pattern()
        return bool(pat.search(text) or (url and pat.search(url)))


class AlertEvent(BaseModel):
    """Notification event payload when tickets are found."""

    movie_name: str
    district: str
    platform: str
    theatre_name: str
    show_time: str
    date: str
    booking_url: str
    is_fdfs: bool = True
    detected_at: datetime = Field(default_factory=datetime.now)
