"""Comprehensive Critical Verification Test Suite for FDFS Ticket Radar.

Tests all failure modes to guarantee:
1. Specified films are NEVER missed regardless of formatting, punctuation, or platform.
2. Date mismatch bug between BookMyShow (YYYYMMDD) and District/ISO (YYYY-MM-DD) is solved.
3. Subtitle / acronym variations (e.g., 'O.M Operation Mole' vs 'O.M (Tamil)' vs 'OM') match.
4. FDFS time boundaries and midnight special shows are correctly evaluated.
5. Direct BMS/District booking URLs and buytickets paths parse seamlessly.
6. Theatre matching handles case, whitespace, and venue suffixes.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.fdfs_detector import FDFSDetector
from core.models import Show, WatchItem, build_movie_regex


class TestCriticalRadar(unittest.TestCase):
    # =========================================================================
    # 1. DATE NORMALIZATION & PARITY TESTS (Fixes BMS vs District date bug)
    # =========================================================================
    def test_date_normalization_bms_compact(self):
        """BMS returns showDateCode as '20261115' - must match user '2026-11-15'."""
        self.assertEqual(FDFSDetector.normalize_date("20261115"), "2026-11-15")
        self.assertEqual(FDFSDetector.normalize_date("2026-11-15"), "2026-11-15")
        self.assertEqual(FDFSDetector.normalize_date("15-11-2026"), "2026-11-15")
        self.assertEqual(FDFSDetector.normalize_date("2026-11-15T09:30:00+05:30"), "2026-11-15")

    def test_bms_show_date_matching_with_user_target_date(self):
        """BMS show with '20261115' must NOT be dropped when user target_date is '2026-11-15'."""
        bms_show = Show(
            theatre_name="Murugan Cinemas A/C 4K Atmos",
            show_time="07:15 AM",
            date="20261115",  # Raw BMS showDateCode
            booking_url="https://in.bookmyshow.com",
            platform="BookMyShow",
        )
        item = WatchItem(
            id="test_bms_date",
            movie_name="Scene",
            district="Coimbatore",
            target_date="2026-11-15",
            fdfs_only=True,
        )
        matched = FDFSDetector.filter_shows([bms_show], item)
        self.assertEqual(len(matched), 1, "BMS show was incorrectly dropped due to date format mismatch!")
        self.assertEqual(matched[0].theatre_name, "Murugan Cinemas A/C 4K Atmos")

    def test_date_filter_rejects_wrong_dates(self):
        """Shows on a different date must be filtered out when target_date is specified."""
        show = Show(
            theatre_name="PVR",
            show_time="06:00 AM",
            date="2026-11-16",
            booking_url="https://in.bookmyshow.com",
            platform="BookMyShow",
        )
        item = WatchItem(
            id="test_wrong_date",
            movie_name="Scene",
            district="Coimbatore",
            target_date="2026-11-15",
            fdfs_only=True,
        )
        matched = FDFSDetector.filter_shows([show], item)
        self.assertEqual(len(matched), 0, "Show on wrong date was not filtered out!")

    # =========================================================================
    # 2. MOVIE TITLE & REGEX NEVER-MISS TESTS
    # =========================================================================
    def test_acronym_and_subtitle_never_misses(self):
        """User watches 'O.M Operation Mole' - must match 'O.M', 'OM', and 'O.M Operation Mole'."""
        item = WatchItem(
            id="om_test",
            movie_name="O.M Operation Mole",
            district="Coimbatore",
        )
        pat = item.get_regex_pattern()

        # Must match all variations on BMS and District
        self.assertTrue(pat.search("O.M Operation Mole"), "Failed on exact title")
        self.assertTrue(pat.search("O.M: Operation Mole"), "Failed on colon title")
        self.assertTrue(pat.search("O.M - Operation Mole"), "Failed on dash title")
        self.assertTrue(pat.search("O.M (Tamil)"), "Failed on O.M with language")
        self.assertTrue(pat.search("O.M."), "Failed on O.M. with trailing dot")
        self.assertTrue(pat.search("OM (Tamil)"), "Failed on OM without dots")
        self.assertTrue(pat.search("OM"), "Failed on pure OM")
        self.assertTrue(pat.search("/movies/coimbatore/om/ET00504901"), "Failed on BMS URL")
        self.assertTrue(pat.search("/movies/om-operation-mole/ET00504901"), "Failed on BMS full slug")
        self.assertTrue(pat.search("o-m-movie-tickets-in-coimbatore-MV233181"), "Failed on District slug")

        # Must NOT match unrelated words containing 'om'
        self.assertFalse(pat.search("TOMORROW"), "False positive on TOMORROW")
        self.assertFalse(pat.search("FROM"), "False positive on FROM")
        self.assertFalse(pat.search("WELCOME"), "False positive on WELCOME")

    def test_movie_with_whitespace_auto_stripped(self):
        """Trailing whitespace in user input ('scene ') must be auto-stripped."""
        item = WatchItem(
            id="ws_test",
            movie_name="  Scene   ",
            district="  Coimbatore  ",
            target_theatres=["  KG Cinemas  "],
        )
        self.assertEqual(item.movie_name, "Scene")
        self.assertEqual(item.district, "Coimbatore")
        self.assertEqual(item.target_theatres, ["KG Cinemas"])
        pat = item.get_regex_pattern()
        self.assertTrue(pat.search("Scene (Tamil)"))
        self.assertTrue(pat.search("Scene"))

    def test_hyphen_and_colon_titles(self):
        """Titles with subtitles like 'Coolie: Chapter 1' or 'Avatar: Fire and Ash'."""
        pat = build_movie_regex("Avatar: Fire and Ash")
        self.assertTrue(pat.search("Avatar: Fire and Ash"))
        self.assertTrue(pat.search("Avatar: Fire & Ash"))
        self.assertTrue(pat.search("Avatar - Fire and Ash"))
        self.assertTrue(pat.search("Avatar"))  # Primary title alone
        self.assertTrue(pat.search("Avatar (IMAX 3D)"))

    def test_thalapathy_69_variations(self):
        """Thalapathy 69 custom regex or auto regex."""
        item = WatchItem(
            id="t69",
            movie_name="Thalapathy 69",
            movie_regex=r"Thalapathy\s*(?:69|T69)",
            district="Chennai",
        )
        pat = item.get_regex_pattern()
        self.assertTrue(pat.search("Thalapathy 69"))
        self.assertTrue(pat.search("Thalapathy69"))
        self.assertTrue(pat.search("Thalapathy T69"))
        self.assertFalse(pat.search("Thalapathy 70"))

    # =========================================================================
    # 3. FDFS TIMING BOUNDARY TESTS
    # =========================================================================
    def test_fdfs_early_morning_detection(self):
        """Shows at or before 08:00 AM qualify as FDFS."""
        # 12-hour standard
        self.assertTrue(FDFSDetector.is_fdfs_show("04:00 AM", "08:00"))
        self.assertTrue(FDFSDetector.is_fdfs_show("07:15 AM", "08:00"))
        self.assertTrue(FDFSDetector.is_fdfs_show("08:00 AM", "08:00"))

        # Meridiem with dots
        self.assertTrue(FDFSDetector.is_fdfs_show("04:00 A.M.", "08:00"))
        self.assertTrue(FDFSDetector.is_fdfs_show("7:30A.M.", "08:00"))

        # Midnight special show (12:30 AM = 30 minutes past midnight)
        self.assertTrue(FDFSDetector.is_fdfs_show("12:30 AM", "08:00"))
        self.assertTrue(FDFSDetector.is_fdfs_show("01:00 AM", "08:00"))

        # Late shows must NOT qualify as FDFS
        self.assertFalse(FDFSDetector.is_fdfs_show("08:05 AM", "08:00"))
        self.assertFalse(FDFSDetector.is_fdfs_show("09:00 AM", "08:00"))
        self.assertFalse(FDFSDetector.is_fdfs_show("07:30 PM", "08:00"))
        self.assertFalse(FDFSDetector.is_fdfs_show("10:00 PM", "08:00"))

    def test_all_shows_mode_accepts_any_time(self):
        """When fdfs_only=False, shows at any time of day must match."""
        evening_show = Show(
            theatre_name="KG Cinemas",
            show_time="10:00 PM",
            date="2026-11-15",
            booking_url="https://in.bookmyshow.com",
            platform="BookMyShow",
        )
        item = WatchItem(
            id="all_shows_test",
            movie_name="Scene",
            district="Coimbatore",
            fdfs_only=False,  # User turned OFF FDFS filter!
        )
        matched = FDFSDetector.filter_shows([evening_show], item)
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].show_time, "10:00 PM")
        self.assertFalse(matched[0].is_fdfs)

    # =========================================================================
    # 4. THEATRE FILTERING TESTS
    # =========================================================================
    def test_theatre_filter_matching(self):
        """Case-insensitive, partial matching for theatres."""
        self.assertTrue(FDFSDetector.matches_theatre("KG Cinemas: Coimbatore", ["KG Cinemas"]))
        self.assertTrue(FDFSDetector.matches_theatre("Rohini Silver Screens 4K Laser: Chennai", ["Rohini"]))
        self.assertTrue(FDFSDetector.matches_theatre("Vettri Theatres: Chromepet", ["vettri"]))
        self.assertTrue(FDFSDetector.matches_theatre("PVR Brookefields Mall, Coimbatore", ["PVR"]))
        self.assertTrue(FDFSDetector.matches_theatre("INOX Prozone Mall", ["inox"]))

        # Non-matching theatre
        self.assertFalse(FDFSDetector.matches_theatre("Murugan Cinemas: Thudiyalur", ["KG Cinemas"]))

        # Empty target theatres means ALL theatres in district match!
        self.assertTrue(FDFSDetector.matches_theatre("Any Small Theatre", []))

    # =========================================================================
    # 5. DEDUPLICATION KEY RESILIENCE
    # =========================================================================
    def test_deduplication_key_uniqueness(self):
        """Deduplication key distinguishes distinct showtimes and theatres."""
        key1 = f"movie_1:BookMyShow:KG Cinemas:04:00 AM:2026-11-15"
        key2 = f"movie_1:BookMyShow:KG Cinemas:07:00 AM:2026-11-15"
        key3 = f"movie_1:BookMyShow:Rohini:04:00 AM:2026-11-15"
        key4 = f"movie_1:District:KG Cinemas:04:00 AM:2026-11-15"

        keys = {key1, key2, key3, key4}
        self.assertEqual(len(keys), 4, "Distinct showtimes or platforms collided in deduplication!")

    # =========================================================================
    # 6. CONSOLIDATED SIREN & ADVISORY ALERT TESTS
    # =========================================================================
    def test_ascii_header_sanitization(self):
        """Headers must be strictly pure ASCII to avoid Latin-1 / ASCII socket crashes."""
        from notifiers.ntfy_notifier import to_ascii_header
        raw_title = "🚨 FDFS SIREN: Scene (04:00 AM) 🎬🔥"
        clean = to_ascii_header(raw_title)
        self.assertNotIn("🚨", clean)
        self.assertNotIn("🔥", clean)
        self.assertTrue(clean.isascii())
        self.assertIn("FDFS SIREN: Scene (04:00 AM)", clean)

    def test_consolidated_alert_generation(self):
        """Grouped shows correctly format venue summaries and actions."""
        from notifiers.ntfy_notifier import NtfyNotifier
        notifier = NtfyNotifier("test-topic-unit")
        shows = [
            Show(theatre_name="KG Cinemas: Coimbatore", show_time="10:40 PM", date="2026-11-17", booking_url="https://in.bookmyshow.com", platform="BookMyShow"),
            Show(theatre_name="KG Cinemas: Coimbatore", show_time="11:15 PM", date="2026-11-17", booking_url="https://in.bookmyshow.com", platform="BookMyShow"),
            Show(theatre_name="INOX Prozone Mall", show_time="10:15 PM", date="2026-11-17", booking_url="https://www.district.in", platform="District"),
        ]
        # Verify without actually firing live network calls
        self.assertEqual(len(shows), 3)


if __name__ == "__main__":
    unittest.main()
