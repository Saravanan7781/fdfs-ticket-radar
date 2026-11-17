"""Main FDFS Ticket Radar Orchestrator (BookMyShow + District by Zomato)."""

import json
import logging
import random
import sys
import time
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Set

# Indian Standard Time (IST = UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def get_now() -> datetime:
    """Return current timestamp in Indian Standard Time."""
    return datetime.now(IST)

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SCAN_TRIGGER_EVENT = threading.Event()
RECENT_ACTIVITY_LOGS: List[dict] = []
TRIGGER_FLAG_PATH = BASE_DIR / "config" / "trigger_scan.flag"


def trigger_instant_scan():
    """Trigger an immediate scan round (used by web UI button /api/scan-now)."""
    SCAN_TRIGGER_EVENT.set()
    try:
        TRIGGER_FLAG_PATH.touch(exist_ok=True)
    except Exception:
        pass

from config.settings import Settings
from core.bms_scanner import BMSScanner
from core.district_scanner import DistrictScanner
from core.fdfs_detector import FDFSDetector
from core.models import AlertEvent, WatchItem
from notifiers.ntfy_notifier import NtfyNotifier, to_ascii_header
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


def format_diagnostic_status(raw_shows: List, matched_shows: List, item: WatchItem, fallback_status: str) -> str:
    """Provide clear, actionable diagnostics explaining why open shows did or did not match filters."""
    if matched_shows:
        return f"🔥 {len(matched_shows)} MATCHING SHOWS OPEN!"
    if not raw_shows:
        return fallback_status

    theatres_desc = ", ".join(item.target_theatres) if item.target_theatres else "All Theatres"
    theatre_matches = [s for s in raw_shows if FDFSDetector.matches_theatre(s.theatre_name, item.target_theatres)]

    if theatre_matches and item.fdfs_only:
        times_sample = ", ".join(sorted(set(s.show_time for s in theatre_matches))[:3])
        return f"⚠️ {len(theatre_matches)} shows open in [{theatres_desc}] ({times_sample}), but all are after 08:00 AM & FDFS filter is ON! (Switch to 'All Shows' to alert)"
    elif not theatre_matches and item.target_theatres:
        other_theatres = ", ".join(sorted(set(s.theatre_name.split(":")[0] for s in raw_shows))[:3])
        return f"⚠️ {len(raw_shows)} shows open in {item.district} ({other_theatres}), but 0 at selected theatre [{theatres_desc}]."
    elif item.fdfs_only:
        times_sample = ", ".join(sorted(set(s.show_time for s in raw_shows))[:3])
        return f"⚠️ {len(raw_shows)} regular shows open ({times_sample}), but FDFS filter is ON (<= 08:00 AM). (Switch to 'All Shows' to alert)"
    elif item.target_date:
        dates_sample = ", ".join(sorted(set(s.date for s in raw_shows))[:2])
        return f"⚠️ {len(raw_shows)} shows open on ({dates_sample}), but 0 on target date ({item.target_date})."
    else:
        return f"⚠️ {len(raw_shows)} shows open in city, but 0 match current filter."


def run_radar():
    """Start continuous FDFS radar monitoring."""
    print("=" * 65)
    print("  🚨 FDFS TICKET RADAR (BookMyShow + District by Zomato)")
    print("=" * 65)
    active_topic = Settings.get_ntfy_topic()
    print(f"• Phone Siren Channel: https://ntfy.sh/{active_topic}")
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
    ntfy = NtfyNotifier(active_topic)
    tele = TelegramNotifier(Settings.TELEGRAM_BOT_TOKEN, Settings.TELEGRAM_CHAT_ID)

    # Test ntfy connection on startup
    print(f"\n[🔔] Sending welcome ping to ntfy.sh/{active_topic}...")
    ntfy.send_test_alert()

    # Deduplication cache: (movie_id, platform, theatre, date)
    alerted_keys: Set[str] = set()
    advisory_keys: Set[str] = set()

    scan_round = 1
    try:
        while True:
            # Check if this round was triggered manually by user ("⚡ Scan Now")
            manual_triggered = SCAN_TRIGGER_EVENT.is_set() or TRIGGER_FLAG_PATH.exists()
            if manual_triggered:
                SCAN_TRIGGER_EVENT.clear()
                try:
                    TRIGGER_FLAG_PATH.unlink(missing_ok=True)
                except Exception:
                    pass

            # Reload watchlist and active ntfy topic in case user modified it
            watchlist = load_watchlist()
            current_topic = Settings.get_ntfy_topic()
            if ntfy.topic != current_topic:
                ntfy = NtfyNotifier(current_topic)
            now_str = get_now().strftime("%I:%M:%S %p IST")
            trigger_tag = " [⚡ USER MANUAL SCAN]" if manual_triggered else ""
            print(f"\n[{now_str}] 🛰️  Round #{scan_round}{trigger_tag}: Scanning BookMyShow & District...")

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
                bms_status_disp = format_diagnostic_status(bms_raw, bms_matched, item, bms.last_status)

                print(f"   ├─ 🎟️ BookMyShow:")
                print(f"   │  • Monitored URL: {bms_url_disp}")
                print(f"   │  • Status:        {bms_status_disp}")

                # 2. Scan District
                dist_raw = district.scan_shows(item)
                dist_matched = FDFSDetector.filter_shows(dist_raw, item)
                dist_url_disp = district.last_url or "https://www.district.in/movies"
                dist_status_disp = format_diagnostic_status(dist_raw, dist_matched, item, district.last_status)

                print(f"   └─ 🎟️ District by Zomato:")
                print(f"      • Monitored URL: {dist_url_disp}")
                print(f"      • Status:        {dist_status_disp}")

                all_matches = bms_matched + dist_matched
                raw_all = bms_raw + dist_raw

                matched_shows_preview = [
                    {
                        "theatre": s.theatre_name,
                        "time": s.show_time,
                        "date": s.date,
                        "platform": s.platform,
                        "format": s.screen_format,
                        "booking_url": s.booking_url,
                    }
                    for s in all_matches
                ]

                round_summary.append({
                    "id": item.id,
                    "movie_name": item.movie_name,
                    "district": item.district,
                    "target_theatres": item.target_theatres,
                    "fdfs_only": item.fdfs_only,
                    "bms_url": bms_url_disp,
                    "bms_status": bms_status_disp,
                    "district_url": dist_url_disp,
                    "district_status": dist_status_disp,
                    "matched_shows_count": len(all_matches),
                    "matched_shows_list": matched_shows_preview,
                })

                # Check for regular shows advisory if FDFS filter is ON but regular shows opened
                if item.fdfs_only and not all_matches and raw_all:
                    matching_theatre_raw = [
                        s for s in raw_all 
                        if FDFSDetector.matches_theatre(s.theatre_name, item.target_theatres) and "sold" not in s.status.lower()
                    ]
                    advisory_key = f"adv:{item.id}:{len(matching_theatre_raw)}"
                    if matching_theatre_raw and advisory_key not in advisory_keys:
                        print(f"\n[ℹ️] Dispatching regular shows advisory alert for '{item.movie_name}'...")
                        ntfy.send_filter_advisory_alert(item.movie_name, item.district, matching_theatre_raw, item.fdfs_max_time)
                        advisory_keys.add(advisory_key)

                # Determine which shows are new
                new_shows = []
                for show in all_matches:
                    key = f"{item.id}:{show.platform}:{show.theatre_name}:{show.show_time}:{show.date}"
                    if key not in alerted_keys:
                        new_shows.append((key, show))

                # If user pressed "Scan Now", or if there are brand new matching shows:
                shows_to_alert = []
                if manual_triggered and all_matches:
                    # Force alert for currently open shows on manual user request!
                    shows_to_alert = all_matches
                elif new_shows:
                    shows_to_alert = [s for _, s in new_shows]

                if shows_to_alert:
                    is_any_fdfs = any(s.is_fdfs for s in shows_to_alert)
                    print("\n" + "🔥" * 30)
                    print(f"🚨 TICKETS DETECTED FOR '{item.movie_name}' ({len(shows_to_alert)} shows)! 🚨")
                    for s in shows_to_alert[:5]:
                        print(f"  • {s.platform}: {s.theatre_name} @ {s.show_time}")
                    print("🔥" * 30 + "\n")

                    # Push single consolidated emergency siren alert
                    delivered = ntfy.send_matched_shows_alert(
                        movie_name=item.movie_name,
                        district=item.district,
                        shows=shows_to_alert,
                        is_fdfs=is_any_fdfs,
                        is_manual_scan=manual_triggered,
                    )

                    if tele.is_configured:
                        for s in shows_to_alert[:3]:
                            tele.send_fdfs_alert(AlertEvent(
                                movie_name=item.movie_name,
                                district=item.district,
                                platform=s.platform,
                                theatre_name=s.theatre_name,
                                show_time=s.show_time,
                                date=s.date,
                                booking_url=s.booking_url,
                                is_fdfs=s.is_fdfs,
                            ))

                    if delivered:
                        for k, _ in new_shows:
                            alerted_keys.add(k)

            # Record round activity log
            total_matches_in_round = sum(m.get("matched_shows_count", 0) for m in round_summary)

            # If user manually clicked "Scan Now" but no tickets are open yet, ping phone with confirmation
            if manual_triggered and total_matches_in_round == 0:
                titles_disp = ", ".join(m.get("movie_name", "") for m in round_summary) or "Active watchlist"
                ntfy._dispatch(
                    {
                        "Title": to_ascii_header(f"Radar Scan: All Quiet ({len(watchlist)} Titles)"),
                        "Priority": "3",
                        "Tags": "satellite,white_check_mark",
                        "Click": f"https://ntfy.sh/{ntfy.topic}",
                    },
                    f"Round #{scan_round} manual scan complete.\nMonitoring: {titles_disp}.\nStatus: No matching tickets released yet.\nRadar scanning 24/7!",
                )
            activity_entry = {
                "round": scan_round,
                "time": get_now().strftime("%I:%M:%S %p"),
                "total_matches": total_matches_in_round,
                "summary": f"Round #{scan_round}: Checked {len(watchlist)} title(s). " + (
                    f"🔥 {total_matches_in_round} MATCHING SHOWS OPEN!" if total_matches_in_round > 0 else "All quiet (no matching tickets released yet)."
                ),
            }
            RECENT_ACTIVITY_LOGS.insert(0, activity_entry)
            if len(RECENT_ACTIVITY_LOGS) > 25:
                RECENT_ACTIVITY_LOGS.pop()

            # Calculate sleep with random human jitter
            sleep_time = Settings.POLL_INTERVAL_WAR_ROOM + random.randint(
                -Settings.JITTER_SECONDS, Settings.JITTER_SECONDS
            )

            # Update live status file for mobile dashboard
            status_data = {
                "is_running": True,
                "scan_round": scan_round,
                "last_scan_time": get_now().strftime("%I:%M:%S %p IST"),
                "last_scan_timestamp": int(time.time()),
                "next_check_in": sleep_time,
                "next_scan_timestamp": int(time.time() + sleep_time),
                "movies_count": len(watchlist),
                "movies": round_summary,
                "recent_logs": RECENT_ACTIVITY_LOGS,
            }
            try:
                Settings.STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(Settings.STATUS_PATH, "w", encoding="utf-8") as f:
                    json.dump(status_data, f, indent=2)
            except Exception as e:
                logger.debug("Error writing status file: %s", e)

            logger.info("Scan completed. Next check in %d seconds. (Ctrl+C to stop)", sleep_time)
            scan_round += 1

            # Wait for sleep_time or until an instant scan is requested
            for _ in range(sleep_time):
                if SCAN_TRIGGER_EVENT.is_set() or TRIGGER_FLAG_PATH.exists():
                    logger.info("⚡ Instant scan triggered by user via dashboard!")
                    break
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n[🛑] FDFS Ticket Radar stopped by user. Goodbye!")


if __name__ == "__main__":
    run_radar()
