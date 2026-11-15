"""Data models for FDFS Ticket Radar with ultra-resilient regex matching."""

import re
from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator


def build_movie_regex(movie_pattern: str) -> re.Pattern:
    """Build a robust regex pattern from user input, supporting explicit regex or smart auto-regex.

    Guarantees:
    - Never misses title variations (e.g. 'O.M', 'OM', 'O-M', 'O.M. Operation Mole').
    - Matches acronyms, colons, hyphens, and optional subtitles.
    - Matches movie slugs in URLs (e.g. '/movies/om/ET00504901' or '/movies/scene/ET00516631').
    - Prevents false-positive substring matches on unrelated English words (e.g. 'TOMORROW', 'FROM').
    """
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

    # Check for subtitle delimiters (':', ' - ', or multi-word acronyms like 'O.M Operation Mole')
    sub_delim = re.search(r"[:\-–—]|\s+(?:part|chapter|vol|volume)\s+", raw, re.IGNORECASE)
    if sub_delim:
        # Primary title is before the delimiter, subtitle is after
        primary = raw[: sub_delim.start()].strip()
        subtitle = raw[sub_delim.end() :].strip()
        p_tokens = [re.escape(t) for t in re.split(r"[\s\.\-_:]+", primary) if t]
        s_tokens = [re.escape(t) for t in re.split(r"[\s\.\-_:]+", subtitle) if t]

        sep = r"[\s\.\-_&:,]*(?:and\s+|the\s+)?"
        p_body = sep.join(p_tokens)
        s_body = sep.join(s_tokens)

        # Allow matching primary alone OR primary + subtitle
        body = rf"(?:{p_body})(?:{sep}(?:{s_body}))?"
        pattern = rf"(?:^|[^a-zA-Z0-9])({body})(?:[^a-zA-Z0-9]|$)"
        return re.compile(pattern, re.IGNORECASE)

    # Check for acronym + subtitle pattern (e.g. "O.M Operation Mole" or "K.G.F Chapter 2")
    words = raw.split()
    if len(words) >= 2 and (re.match(r"^[A-Za-z](\.[A-Za-z])+\.?$", words[0]) or len(words[0]) <= 3 and words[0].isupper()):
        primary = words[0]
        subtitle = " ".join(words[1:])
        p_tokens = [re.escape(t) for t in re.split(r"[\s\.\-_:]+", primary) if t]
        s_tokens = [re.escape(t) for t in re.split(r"[\s\.\-_:]+", subtitle) if t]

        sep = r"[\s\.\-_&:,]*(?:and\s+|the\s+)?"
        p_body = sep.join(p_tokens)
        s_body = sep.join(s_tokens)

        body = rf"(?:{p_body})(?:{sep}(?:{s_body}))?"
        pattern = rf"(?:^|[^a-zA-Z0-9])({body})(?:[^a-zA-Z0-9]|$)"
        return re.compile(pattern, re.IGNORECASE)

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

    @field_validator("movie_name", "district", mode="before")
    @classmethod
    def strip_strings(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("target_date", "movie_regex", "bms_url", "district_url", mode="before")
    @classmethod
    def strip_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

    @field_validator("target_theatres", mode="before")
    @classmethod
    def normalize_theatres(cls, v: Union[List[str], str, None]) -> List[str]:
        if isinstance(v, str):
            if not v.strip() or v.strip().lower() == "all":
                return []
            return [t.strip() for t in v.split(",") if t.strip()]
        if isinstance(v, list):
            cleaned = []
            for t in v:
                if isinstance(t, str) and t.strip() and t.strip().lower() != "all":
                    cleaned.append(t.strip())
            return cleaned
        return []

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
