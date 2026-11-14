"""Unified 24/7 Cloud Runner for FDFS Ticket Radar.

Runs the continuous Radar Scanner in a background thread and the Web Dashboard
on the main thread (listening on $PORT for cloud platforms like Render, Railway, Koyeb).
"""

import logging
import os
import sys
import threading
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from radar import run_radar
from web_ui import start_server

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("cloud-app")


def start_radar_thread():
    """Start radar loop in background thread."""
    logger.info("Starting background FDFS Ticket Radar thread...")
    radar_thread = threading.Thread(target=run_radar, daemon=True, name="RadarScannerThread")
    radar_thread.start()
    return radar_thread


def main():
    port = int(os.environ.get("PORT", "5055"))
    print("=" * 65)
    print("  🚀 FDFS TICKET RADAR — 24/7 CLOUD SERVICE")
    print("=" * 65)
    print(f"• Cloud Web Port: {port}")
    print("• Background Radar: ACTIVE")
    print("• Health Check Endpoint: /health")
    print("=" * 65)

    # 1. Start continuous scanner in daemon thread
    start_radar_thread()

    # 2. Start HTTP server in main thread (binds to $PORT)
    start_server(port=port, open_browser=False)


if __name__ == "__main__":
    main()
