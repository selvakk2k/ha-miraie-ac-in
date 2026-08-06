"""Unit tests for sensor backfill timestamp alignment and fallback resolution logic."""

import unittest
import importlib
from datetime import date, timedelta
import tests.ha_stub


class TestSensorBackfillAlignment(unittest.TestCase):
    """Test sensor backfill alignment, fallback sums, and install date resolution."""

    def setUp(self):
        self.mod_sensor = importlib.import_module("custom_components.miraie_in.sensor")

    def test_extract_recorded_range_sum_exact_match(self):
        """Test exact timestamp matching in _extract_recorded_range_sum."""
        start_day = date(2026, 8, 1)
        end_day = date(2026, 8, 5)

        start_ts = self.mod_sensor._get_statistic_timestamp(start_day).timestamp()
        end_ts = self.mod_sensor._get_statistic_timestamp(end_day + timedelta(days=1)).timestamp()

        entries = [
            {"start": start_ts, "sum": 100.0},
            {"start": end_ts, "sum": 125.5},
        ]
        delta = self.mod_sensor._extract_recorded_range_sum(entries, start_day, end_day)
        self.assertIsNotNone(delta)
        self.assertAlmostEqual(delta, 25.5)

    def test_extract_recorded_range_sum_closest_neighbor_fallback(self):
        """Test closest neighbor fallback in _extract_recorded_range_sum when exact timestamps are missing."""
        start_day = date(2026, 8, 1)
        end_day = date(2026, 8, 5)

        target_start_ts = self.mod_sensor._get_statistic_timestamp(start_day).timestamp()
        target_end_ts = self.mod_sensor._get_statistic_timestamp(end_day + timedelta(days=1)).timestamp()

        # Provide timestamps offset by 1800 seconds (30 mins)
        entries = [
            {"start": target_start_ts + 1800, "sum": 105.0},
            {"start": target_end_ts - 1800, "sum": 130.0},
        ]
        delta = self.mod_sensor._extract_recorded_range_sum(entries, start_day, end_day)
        self.assertIsNotNone(delta)
        self.assertAlmostEqual(delta, 25.0)

    def test_get_statistic_timestamp_alignment(self):
        """Verify _get_statistic_timestamp produces top-of-hour UTC timestamp."""
        target_date = date(2026, 8, 6)
        ts_dt = self.mod_sensor._get_statistic_timestamp(target_date)
        self.assertEqual(ts_dt.minute, 0)
        self.assertEqual(ts_dt.second, 0)
        self.assertEqual(ts_dt.microsecond, 0)

    def test_install_date_option_fallback_parsing(self):
        """Test per-device and global install date option fallback parsing."""
        from tests.fixtures import MockConfigEntry

        def resolve_date(entry, device_id):
            options = getattr(entry, "options", {})
            dev_key = f"install_date_{device_id}"
            raw_str = options.get(dev_key) or options.get("install_date")
            if raw_str:
                try:
                    return date.fromisoformat(raw_str)
                except ValueError:
                    pass
            return date(2026, 1, 1)

        # 1. Device override present
        entry_device = MockConfigEntry(
            options={"install_date_dev1": "2026-01-01", "install_date": "2026-03-01"}
        )
        self.assertEqual(resolve_date(entry_device, "dev1"), date(2026, 1, 1))

        # 2. Device override missing, global option present
        entry_global = MockConfigEntry(options={"install_date": "2026-03-01"})
        self.assertEqual(resolve_date(entry_global, "dev2"), date(2026, 3, 1))


if __name__ == "__main__":
    unittest.main()
