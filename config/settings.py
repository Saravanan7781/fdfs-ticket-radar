"""Configuration and global settings for FDFS Ticket Radar."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load optional .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings:
    """Radar settings & credentials."""

    BASE_DIR: Path = BASE_DIR
    WATCHLIST_PATH: Path = BASE_DIR / "config" / "watchlist.json"
    STATUS_PATH: Path = BASE_DIR / "config" / "status.json"

    # Notification Channels
    # ntfy.sh is 100% free with no accounts required.
    # Set your own private topic name (e.g. 'saravanan-fdfs-siren-7781')
    DEFAULT_TOPIC: str = "saravanan-fdfs-siren-7781"
    NTFY_TOPIC: str = os.getenv("NTFY_TOPIC", "saravanan-fdfs-siren-7781").strip() or "saravanan-fdfs-siren-7781"

    @classmethod
    def get_ntfy_topic(cls) -> str:
        """Dynamically resolve the active ntfy topic from watchlist.json, env, or default."""
        if cls.WATCHLIST_PATH.exists():
            try:
                import json
                with open(cls.WATCHLIST_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("ntfy_topic") and str(data["ntfy_topic"]).strip():
                        return str(data["ntfy_topic"]).strip()
            except Exception:
                pass
        env_val = os.getenv("NTFY_TOPIC", "").strip()
        if env_val:
            return env_val
        return cls.DEFAULT_TOPIC

    # Optional Telegram alerts
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Polling intervals (in seconds)
    POLL_INTERVAL_CALM: int = int(os.getenv("POLL_INTERVAL_CALM", "180"))  # 3 min when far away
    POLL_INTERVAL_WAR_ROOM: int = int(os.getenv("POLL_INTERVAL_WAR_ROOM", "50"))  # ~50s when near release
    JITTER_SECONDS: int = 12  # Random offset ±12s so requests look human

    # Siren alert (Priority 5 rings through phone's Do-Not-Disturb / Silent mode)
    ENABLE_PHONE_SIREN: bool = os.getenv("ENABLE_PHONE_SIREN", "true").lower() in ("true", "1", "yes")
