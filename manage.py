"""Interactive Watchlist Manager for FDFS Ticket Radar."""

import json
import sys
from pathlib import Path
from config.settings import Settings
from core.models import WatchItem
from notifiers.ntfy_notifier import NtfyNotifier


def load_data() -> dict:
    if Settings.WATCHLIST_PATH.exists():
        with open(Settings.WATCHLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"watchlist": []}


def save_data(data: dict):
    Settings.WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(Settings.WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def print_header():
    print("\n" + "═" * 60)
    print("      🎬 FDFS TICKET RADAR — EASY FILTER MANAGER")
    print("═" * 60)


def prompt_movie_details(existing: dict = None) -> dict:
    """Prompt user for movie details with sensible defaults."""
    ex = existing or {}
    print("\n👉 Fill in the details (Press Enter to keep current value):\n")

    cur_name = ex.get("movie_name", "Coolie")
    name = input(f"• Movie Name [{cur_name}]: ").strip() or cur_name

    cur_city = ex.get("district", "Chennai")
    city = input(f"• City / District [{cur_city}]: ").strip() or cur_city

    cur_theatres = ", ".join(ex.get("target_theatres", [])) or "ALL THEATRES"
    th_input = input(f"• Target Theatres (comma-separated, or 'all') [{cur_theatres}]: ").strip()

    if th_input.lower() in ("all", "*", ""):
        theatres = [] if th_input.lower() in ("all", "*") else ex.get("target_theatres", [])
    else:
        theatres = [t.strip() for t in th_input.split(",") if t.strip()]

    cur_date = ex.get("target_date") or "Any (Release Day)"
    date_input = input(f"• Specific Date (YYYY-MM-DD or Enter for any) [{cur_date}]: ").strip()
    target_date = date_input if date_input else (ex.get("target_date") if cur_date != "Any (Release Day)" else None)

    cur_fdfs = "Y" if ex.get("fdfs_only", True) else "N"
    fdfs_input = input(f"• FDFS Only (Morning shows <= 08:00 AM)? (Y/N) [{cur_fdfs}]: ").strip().upper()
    fdfs_only = (fdfs_input == "Y") if fdfs_input else ex.get("fdfs_only", True)

    item_id = f"{name.lower().replace(' ', '_')}_{city.lower()}"
    return {
        "id": item_id,
        "movie_name": name,
        "district": city,
        "target_theatres": theatres,
        "target_date": target_date,
        "fdfs_only": fdfs_only,
        "fdfs_max_time": "08:00",
        "bms_url": ex.get("bms_url"),
        "district_url": ex.get("district_url"),
        "enabled": True,
    }


def quick_edit():
    data = load_data()
    watchlist = data.get("watchlist", [])
    if not watchlist:
        print("\n[!] Watchlist is currently empty. Let's add your first movie!")
        add_movie()
        return

    print("\nSelect a movie to edit:")
    for i, item in enumerate(watchlist, 1):
        th = ", ".join(item.get("target_theatres", [])) or "ALL THEATRES"
        print(f"  {i}. {item.get('movie_name')} ({item.get('district')}) | Theatres: [{th}]")

    choice = input(f"\nSelect number [1-{len(watchlist)}]: ").strip()
    idx = int(choice) - 1 if choice.isdigit() and 1 <= int(choice) <= len(watchlist) else 0

    updated = prompt_movie_details(watchlist[idx])
    watchlist[idx] = updated
    data["watchlist"] = watchlist
    save_data(data)

    print("\n" + "─" * 60)
    print(f"✅ UPDATED: '{updated['movie_name']}' in {updated['district']}!")
    print(f"   Theatres: {', '.join(updated['target_theatres']) or 'ALL'}")
    print(f"   FDFS Only: {updated['fdfs_only']}")
    print("─" * 60)
    print("💡 The running radar will automatically pick up these changes immediately!\n")


def add_movie():
    data = load_data()
    watchlist = data.get("watchlist", [])
    new_item = prompt_movie_details()
    watchlist.append(new_item)
    data["watchlist"] = watchlist
    save_data(data)
    print(f"\n✅ Added '{new_item['movie_name']}' in {new_item['district']} to watchlist!\n")


def list_movies():
    data = load_data()
    watchlist = data.get("watchlist", [])
    if not watchlist:
        print("\n[!] Watchlist is empty.\n")
        return

    print("\n" + "=" * 60)
    print("  📋 CURRENT WATCHLIST")
    print("=" * 60)
    for i, item in enumerate(watchlist, 1):
        th = ", ".join(item.get("target_theatres", [])) or "ALL THEATRES in District"
        fdfs_str = "Early Morning FDFS (<= 8 AM)" if item.get("fdfs_only", True) else "All Shows"
        print(f"{i}. 🎬 {item.get('movie_name')} ({item.get('district')})")
        print(f"   🏛️ Theatres: {th}")
        print(f"   ⏰ Timing: {fdfs_str}")
        print(f"   📅 Date: {item.get('target_date') or 'Release Day'}\n")
    print("=" * 60 + "\n")


def delete_movie():
    data = load_data()
    watchlist = data.get("watchlist", [])
    if not watchlist:
        print("\n[!] Watchlist is empty.\n")
        return

    print("\nSelect a movie to remove:")
    for i, item in enumerate(watchlist, 1):
        print(f"  {i}. {item.get('movie_name')} ({item.get('district')})")

    choice = input(f"\nSelect number to delete [1-{len(watchlist)}]: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(watchlist):
        removed = watchlist.pop(int(choice) - 1)
        data["watchlist"] = watchlist
        save_data(data)
        print(f"\n🗑️ Removed '{removed.get('movie_name')}' from watchlist.\n")


def test_siren():
    print(f"\n🔔 Sending test siren to phone (ntfy.sh/{Settings.NTFY_TOPIC})...")
    notifier = NtfyNotifier(Settings.NTFY_TOPIC)
    if notifier.send_test_alert():
        print("✅ Siren sent! Check your phone.\n")
    else:
        print("❌ Failed to send alert. Check internet.\n")


def main_menu():
    while True:
        print_header()
        print("1. ⚡ Quick Edit Current Movie & Theatres")
        print("2. ➕ Add a New Movie to Track")
        print("3. 📋 View All Tracked Movies")
        print("4. 🗑️ Delete a Movie")
        print("5. 🚨 Test Phone Siren Alert")
        print("6. 🚪 Exit")
        print("═" * 60)

        choice = input("Enter choice [1-6]: ").strip()

        if choice == "1":
            quick_edit()
        elif choice == "2":
            add_movie()
        elif choice == "3":
            list_movies()
        elif choice == "4":
            delete_movie()
        elif choice == "5":
            test_siren()
        elif choice in ("6", "q", "exit"):
            print("\nGoodbye!\n")
            break
        else:
            print("\nInvalid choice. Try again.\n")


if __name__ == "__main__":
    main_menu()
