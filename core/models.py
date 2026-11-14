"""Data models for FDFS Ticket Radar."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


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
    district: str  # e.g., "Chennai", "Coimbatore"
    target_theatres: List[str] = Field(default_factory=list)  # Empty means ALL
    target_date: Optional[str] = None  # YYYY-MM-DD
    fdfs_only: bool = True
    fdfs_max_time: str = "08:00"  # Show time at or before 08:00 AM qualifies as FDFS
    enabled: bool = True


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
