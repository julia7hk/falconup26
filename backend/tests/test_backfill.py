"""Tests for the backfill/refresh window selection.

Pure date arithmetic — no DB, no network.
"""

from datetime import date, timedelta

from scripts.backfill import OVERLAP_DAYS, YEARS, fetch_window


TODAY = date(2026, 9, 6)


class TestEmptyTable:
    def test_no_stored_data_pulls_full_years(self):
        start, end = fetch_window(None, TODAY)
        assert end == TODAY
        assert start == TODAY - timedelta(days=YEARS * 365)

    def test_newly_seeded_symbol_backfills_itself(self):
        """A symbol added to the catalog has no rows, so it takes the same
        path as a fresh database — no special handling needed."""
        assert fetch_window(None, TODAY) == fetch_window(None, TODAY, full=True)


class TestIncremental:
    def test_up_to_date_still_reads_back_the_overlap(self):
        start, end = fetch_window(TODAY, TODAY)
        assert end == TODAY
        assert start == TODAY - timedelta(days=OVERLAP_DAYS)

    def test_one_day_behind(self):
        last = TODAY - timedelta(days=1)
        start, _ = fetch_window(last, TODAY)
        assert start == last - timedelta(days=OVERLAP_DAYS)

    def test_far_behind_uses_the_same_rule(self):
        """A 16-day gap is not a special case — same arithmetic, wider window.
        This is what lets production catch up on its first run."""
        last = TODAY - timedelta(days=16)
        start, end = fetch_window(last, TODAY)
        assert start == last - timedelta(days=OVERLAP_DAYS)
        assert end == TODAY
        assert (end - start).days == 16 + OVERLAP_DAYS

    def test_window_always_covers_the_last_stored_date(self):
        for gap in (0, 1, 3, 16, 400):
            last = TODAY - timedelta(days=gap)
            start, end = fetch_window(last, TODAY)
            assert start < last <= end


class TestFullMode:
    def test_full_ignores_stored_date(self):
        recent = TODAY - timedelta(days=1)
        assert fetch_window(recent, TODAY, full=True) == fetch_window(None, TODAY)

    def test_full_differs_from_incremental_when_data_exists(self):
        recent = TODAY - timedelta(days=1)
        assert fetch_window(recent, TODAY, full=True) != fetch_window(recent, TODAY)


class TestEdgeCases:
    def test_future_stored_date_is_clamped(self):
        """Clock skew or bad data must not produce start > end."""
        start, end = fetch_window(TODAY + timedelta(days=5), TODAY)
        assert start < end
        assert start == TODAY - timedelta(days=OVERLAP_DAYS)

    def test_start_is_never_after_end(self):
        for gap in (-30, -1, 0, 1, 90, 5000):
            start, end = fetch_window(TODAY - timedelta(days=gap), TODAY)
            assert start < end
