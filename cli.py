"""CLI management tool for FDFS Ticket Radar."""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import Settings
from core.models import WatchItem
from notifiers.ntfy_notifier import NtfyNotifier


def load_raw_data() -> dict:
    if Settings.WATCHLIST_PATH.exists():
        with open(Settings.WATCHLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"watchlist": []}


def save_raw_data(data: dict):
    Settings.WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(Settings.WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def cmd_list(args):
    data = load_raw_data()
    items = data.get("watchlist", [])
    if not items:
        print("\n[!] Watchlist is empty. Use 'python cli.py add' to track a movie.\n")
        return

    print("\n" + "=" * 60)
    print("  📋 ACTIVE FDFS WATCHLIST")
    print("=" * 60)
    for i, item in enumerate(items, 1):
        th = ", ".join(item.get("target_theatres", [])) or "ALL THEATRES in District"
        status = "🟢 Active" if item.get("enabled", True) else "⏸️ Paused"
        print(f"{i}. {item.get('movie_name')} ({item.get('district')}) [{status}]")
        print(f"   Theatres: {th}")
        print(f"   Date: {item.get('target_date') or 'Any'} | FDFS Only: {item.get('fdfs_only', True)}\n")
    print("=" * 60 + "\n")


def cmd_add(args):
    data = load_raw_data()
    theatres = [t.strip() for t in args.theatres.split(",")] if args.theatres else []
    item_id = f"{args.movie.lower().replace(' ', '_')}_{args.city.lower()}"

    new_item = {
        "id": item_id,
        "movie_name": args.movie.strip(),
        "movie_regex": args.regex.strip() if args.regex else None,
        "district": args.city.strip(),
        "target_theatres": theatres,
        "target_date": args.date,
        "fdfs_only": not args.all_shows,
        "fdfs_max_time": args.max_time or "08:00",
        "bms_url": args.bms_url,
        "district_url": args.district_url,
        "enabled": True,
    }

    # Replace if exists, else append
    existing = [w for w in data.get("watchlist", []) if w.get("id") != item_id]
    existing.append(new_item)
    data["watchlist"] = existing
    save_raw_data(data)

    print(f"\n[✅] Added '{args.movie}' in {args.city} to watchlist!")
    print(f"     Target Theatres: {theatres or 'ALL'}")
    print(f"     FDFS Only: {not args.all_shows} (before {args.max_time or '08:00 AM'})\n")


def cmd_test(args):
    print(f"\n[🔔] Sending test siren alert to ntfy.sh/{Settings.NTFY_TOPIC}...")
    notifier = NtfyNotifier(Settings.NTFY_TOPIC)
    success = notifier.send_test_alert()
    if success:
        print("[SUCCESS] Test notification dispatched! Check your phone app or visit:")
        print(f"          👉 https://ntfy.sh/{Settings.NTFY_TOPIC}\n")
    else:
        print("[ERROR] Failed to send test notification. Check internet connection.\n")


def main():
    parser = argparse.ArgumentParser(description="FDFS Ticket Radar CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # list
    subparsers.add_parser("list", help="List all tracked movies in watchlist")

    # add
    parser_add = subparsers.add_parser("add", help="Add a new movie to track")
    parser_add.add_argument("--movie", required=True, help="Movie name or regex (e.g. 'Coolie', 'O\.?M')")
    parser_add.add_argument("--regex", help="Optional custom regex for movie matching (e.g. 'O\.?M', 'Thalapathy\\s*69')")
    parser_add.add_argument("--city", required=True, help="District/City (e.g. 'Chennai')")
    parser_add.add_argument("--theatres", help="Comma-separated theatres (e.g. 'Rohini,Vettri')")
    parser_add.add_argument("--date", help="Release date in YYYY-MM-DD")
    parser_add.add_argument("--all-shows", action="store_true", help="Alert on any show, not just FDFS")
    parser_add.add_argument("--max-time", default="08:00", help="Max time for FDFS (default: 08:00)")
    parser_add.add_argument("--bms-url", help="Direct BookMyShow movie/tickets URL (optional)")
    parser_add.add_argument("--district-url", help="Direct District movie URL (optional)")

    # test
    subparsers.add_parser("test", help="Send a test notification to your phone")

    args = parser.parse_args()
    if args.subcommand == "list":
        cmd_list(args)
    elif args.subcommand == "add":
        cmd_add(args)
    elif args.subcommand == "test":
        cmd_test(args)


if __name__ == "__main__":
    main()
