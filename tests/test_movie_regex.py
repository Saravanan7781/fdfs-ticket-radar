"""Unit tests for movie title regex matching in FDFS Ticket Radar."""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.models import WatchItem, build_movie_regex


class TestMovieRegex(unittest.TestCase):
    def test_smart_punctuation_handling(self):
        # 'O.M' should match all punctuation variations
        pat = build_movie_regex("O.M")
        self.assertTrue(pat.search("O.M"))
        self.assertTrue(pat.search("OM"))
        self.assertTrue(pat.search("O-M"))
        self.assertTrue(pat.search("O M"))
        self.assertTrue(pat.search("O.M."))
        self.assertTrue(pat.search("O.M (Tamil)"))
        self.assertTrue(pat.search("/movies/om/ET0012345"))
        self.assertTrue(pat.search("/movies/o-m-movie-tickets-in-coimbatore-MV233181"))

        # Should NOT match substring in unrelated words
        self.assertFalse(pat.search("Pyre U | Drama, Romance"))
        self.assertFalse(pat.search("TOMORROW"))
        self.assertFalse(pat.search("WELCOME"))

    def test_movie_with_language_and_format_tags(self):
        pat = build_movie_regex("Coolie")
        self.assertTrue(pat.search("Coolie"))
        self.assertTrue(pat.search("Coolie (Tamil)"))
        self.assertTrue(pat.search("Coolie - IMAX 2D"))
        self.assertTrue(pat.search("Coolie: Chapter 1"))
        self.assertFalse(pat.search("Uncoolie"))

    def test_custom_regex_in_watch_item(self):
        # Custom regex with groups and alternatives
        item = WatchItem(
            id="test",
            movie_name="Thalapathy 69",
            movie_regex=r"Thalapathy\s*(?:69|T69)",
            district="Chennai",
        )
        pat = item.get_regex_pattern()
        self.assertTrue(pat.search("Thalapathy 69"))
        self.assertTrue(pat.search("Thalapathy69"))
        self.assertTrue(pat.search("Thalapathy T69"))
        self.assertFalse(pat.search("Thalapathy 70"))

    def test_prefix_wildcard_regex(self):
        # Match 'O.M' prefix for full titles like 'OM Operation Mole'
        item = WatchItem(
            id="test2",
            movie_name="O.M",
            movie_regex=r"O\.?M.*",
            district="Coimbatore",
        )
        pat = item.get_regex_pattern()
        self.assertTrue(pat.search("OM Operation Mole"))
        self.assertTrue(pat.search("O.M"))
        self.assertFalse(pat.search("Romance"))


if __name__ == "__main__":
    unittest.main()
