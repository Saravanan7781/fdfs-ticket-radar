"""Main FDFS Ticket Radar Orchestrator (BookMyShow + District by Zomato)."""

import json
import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import Settings
from core.bms_scanner import BMSScanner
from core.district_scanner import DistrictScanner
from core.fdfs_detector import FDFSDetector
from core.models import AlertEvent, WatchItem
from notifiers.ntfy_notifier import NtfyNotifier
from notifiers.telegram_notifier import TelegramNotifier

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("fdfs-radar")


def load_watchlist() -> List[WatchItem]:
    """Load items from config/watchlist.json."""
    if not Settings.WATCHLIST_PATH.exists():
        logger.error("Watchlist file not found at: %s", Settings.WATCHLIST_PATH)
        return []

    try:
        with open(Settings.WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = [WatchItem(**w) for w in data.get("watchlist", []) if w.get("enabled", True)]
            return items
    except Exception as e:
        logger.error("Error reading watchlist: %s", e)
        return []


def run_radar():
    """Start continuous FDFS radar monitoring."""
    print("=" * 65)
    print("  🚨 FDFS TICKET RADAR (BookMyShow + District by Zomato)")
    print("=" * 65)
    print(f"• Phone Siren Channel: https://ntfy.sh/{Settings.NTFY_TOPIC}")
    print(f"• Watchlist File: {Settings.WATCHLIST_PATH}")

    watchlist = load_watchlist()
    if not watchlist:
        print("[!] No active movies in watchlist.json. Edit config/watchlist.json to add a movie.")
        sys.exit(1)

    print(f"• Loaded {len(watchlist)} movie(s) to track:")
    for item in watchlist:
        theatres_desc = ", ".join(item.target_theatres) if item.target_theatres else "ALL THEATRES in District"
        print(f"   🎬 '{item.movie_name}' ({item.district}) -> Theatres: [{theatres_desc}] | FDFS: {item.fdfs_only}")
    print("=" * 65)

    # Initialize scanners and notifiers
    bms = BMSScanner()
    district = DistrictScanner()
    ntfy = NtfyNotifier(Settings.NTFY_TOPIC)
    tele = TelegramNotifier(Settings.TELEGRAM_BOT_TOKEN, Settings.TELEGRAM_CHAT_ID)

    # Test ntfy connection on startup
    print(f"\n[🔔] Sending welcome ping to ntfy.sh/{Settings.NTFY_TOPIC}...")
    ntfy.send_test_alert()

    # Deduplication cache: (movie_id, platform, theatre, date)
    alerted_keys: Set[str] = set()

    scan_round = 1
    try:
        while True:
            # Reload watchlist in case user modified it
            watchlist = load_watchlist()
            now_str = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{now_str}] 🛰️  Round #{scan_round}: Scanning BookMyShow & District...")

            round_summary = []
            for item in watchlist:
                theatres_desc = ", ".join(item.target_theatres) if item.target_theatres else "ALL THEATRES in District"
                fdfs_desc = f"FDFS only (<= {item.fdfs_max_time} AM)" if item.fdfs_only else "All Show Times"
                regex_info = f"Custom Regex: /{item.movie_regex}/i" if item.movie_regex else f"Smart Regex Active (matches '{item.movie_name}', punctuation & suffixes)"

                print(f"\n   ┌─ 🎬 Tracking: '{item.movie_name}' ({item.district})")
                print(f"   │  🔍 Matcher: {regex_info}")
                print(f"   │  🎯 Filter:  Theatres: [{theatres_desc}] | {fdfs_desc}")

                # 1. Scan BookMyShow
                bms_raw = bms.scan_shows(item)
                bms_matched = FDFSDetector.filter_shows(bms_raw, item)

                bms_url_disp = bms.last_url or f"https://in.bookmyshow.com/explore/movies-{item.district.lower()}"
                if bms_matched:
                    bms_status_disp = f"🔥 {len(bms_matched)} MATCHING SHOWS OPEN!"
                elif bms_raw:
                    bms_status_disp = f"⚠️ {len(bms_raw)} shows open in district, but 0 match target filter [{theatres_desc}]"
                else:
                    bms_status_disp = bms.last_status

                print(f"   ├─ 🎟️ BookMyShow:")
                print(f"   │  • Monitored URL: {bms_url_disp}")
                print(f"   │  • Status:        {bms_status_disp}")

                # 2. Scan District
                dist_raw = district.scan_shows(item)
                dist_matched = FDFSDetector.filter_shows(dist_raw, item)

                dist_url_disp = district.last_url or "https://www.district.in/movies"
                if dist_matched:
                    dist_status_disp = f"🔥 {len(dist_matched)} MATCHING SHOWS OPEN!"
                elif dist_raw:
                    dist_status_disp = f"⚠️ {len(dist_raw)} shows open in district, but 0 match target filter [{theatres_desc}]"
                else:
                    dist_status_disp = district.last_status

                print(f"   └─ 🎟️ District by Zomato:")
                print(f"      • Monitored URL: {dist_url_disp}")
                print(f"      • Status:        {dist_status_disp}")

                all_matches = bms_matched + dist_matched

                round_summary.append({
                    "movie_name": item.movie_name,
                    "district": item.district,
                    "target_theatres": item.target_theatres,
                    "fdfs_only": item.fdfs_only,
                    "bms_url": bms_url_disp,
                    "bms_status": bms_status_disp,
                    "district_url": dist_url_disp,
                    "district_status": dist_status_disp,
                    "matched_shows_count": len(all_matches),
                })

                for show in all_matches:
                    key = f"{item.id}:{show.platform}:{show.theatre_name}:{show.show_time}:{show.date}"
                    if key in alerted_keys:
                        continue  # Already alerted for this exact show

                    # 🔥 TRIGGER SIREN ALERT!
                    alert = AlertEvent(
                        movie_name=item.movie_name,
                        district=item.district,
                        platform=show.platform,
                        theatre_name=show.theatre_name,
                        show_time=show.show_time,
                        date=show.date,
                        booking_url=show.booking_url,
                        is_fdfs=show.is_fdfs,
                    )

                    print("\n" + "🔥" * 30)
                    print(f"🚨 TICKETS DETECTED ON {show.platform.upper()}! 🚨")
                    print(f"Movie: {item.movie_name}")
                    print(f"Theatre: {show.theatre_name}")
                    print(f"Show: {show.show_time}")
                    print(f"Book: {show.booking_url}")
                    print("🔥" * 30 + "\n")

                    # Push emergency sirens
                    ntfy.send_fdfs_alert(alert)
                    if tele.is_configured:
                        tele.send_fdfs_alert(alert)

                    alerted_keys.add(key)

            # Update live status file for mobile dashboard
            status_data = {
                "is_running": True,
                "scan_round": scan_round,
                "last_scan_time": datetime.now().strftime("%I:%M:%S %p"),
                "last_scan_timestamp": int(time.time()),
                "movies_count": len(watchlist),
                "movies": round_summary,
            }
            try:
                Settings.STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(Settings.STATUS_PATH, "w", encoding="utf-8") as f:
                    json.dump(status_data, f, indent=2)
            except Exception as e:
                logger.debug("Error writing status file: %s", e)

            # Calculate sleep with random human jitter
            sleep_time = Settings.POLL_INTERVAL_WAR_ROOM + random.randint(
                -Settings.JITTER_SECONDS, Settings.JITTER_SECONDS
            )
            logger.info("Scan completed. Next check in %d seconds. (Ctrl+C to stop)", sleep_time)
            scan_round += 1
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\n[🛑] FDFS Ticket Radar stopped by user. Goodbye!")


if __name__ == "__main__":
    run_radar()
