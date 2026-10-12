"""验证会影响统计的清洗边界：连续性、昼夜证据、首点和真实零值。"""

import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from q1_clean_data import clean_local_values, find_frozen_runs


class CleaningBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads((ROOT / "docs/q1_cleaning_rules.json").read_text())
        self.data = pd.DataFrame({
            "time_local": pd.date_range("2018-12-08 17:00", periods=6, freq="15min", tz="Asia/Shanghai"),
            "source_csv_row": range(2, 8), "power": [10.0] * 6,
            "lmd_totalirrad": [400.0] * 6, "lmd_diffuseirrad": [80.0] * 6,
            "lmd_temperature": [10.0] * 6, "lmd_pressure": [1000.0] * 6,
            "lmd_winddirection": [180.0] * 6, "lmd_windspeed": [2.0] * 6,
            "nwp_globalirrad": [50.0, 20.0, 0.0, 0.0, 0.0, 0.0],
            "solar_elevation_deg": [-2.0, -5.0, -8.0, -11.0, -14.0, -17.0],
            "is_daylight": [False] * 6, "capacity_mw": [20.0] * 6,
        })

    def test_frozen_repeat_is_masked_but_anchor_and_raw_are_preserved(self):
        cleaned, log, runs = clean_local_values(self.data, self.rules)
        pd.testing.assert_frame_equal(cleaned[self.data.columns], self.data)
        self.assertEqual(len(cleaned), 6)
        self.assertEqual(cleaned.loc[0, "power_clean"], 10.0)
        self.assertTrue(cleaned.loc[1:, "power_clean"].isna().all())
        self.assertTrue(cleaned.loc[0, "flag_frozen_anchor_review"])
        self.assertEqual(len(log), 5 * 7)
        self.assertEqual(len(runs), 1)
        pd.testing.assert_series_equal(cleaned["nwp_globalirrad"], self.data["nwp_globalirrad"])

    def test_gap_does_not_join_short_runs_into_a_frozen_block(self):
        frame = self.data.iloc[:4].copy()
        frame.loc[2:, "time_local"] += pd.Timedelta(hours=1)
        candidate, repeats, runs = find_frozen_runs(frame, self.rules)
        self.assertFalse(candidate.any())
        self.assertFalse(repeats.any())
        self.assertTrue(runs.empty)

    def test_positive_flat_daytime_is_not_removed_without_night_evidence(self):
        frame = self.data.copy()
        frame["solar_elevation_deg"] = 30.0
        frame["is_daylight"] = True
        cleaned, log, runs = clean_local_values(frame, self.rules)
        self.assertTrue(runs.empty)
        self.assertTrue(log.empty)
        self.assertTrue(cleaned["power_clean"].eq(10).all())

    def test_ordinary_zero_night_is_not_a_frozen_failure(self):
        frame = self.data.copy()
        frame["power"] = 0.0
        frame["lmd_totalirrad"] = 0.0
        cleaned, log, runs = clean_local_values(frame, self.rules)
        self.assertTrue(runs.empty)
        self.assertTrue(log.empty)
        self.assertTrue(cleaned["power_clean"].eq(0).all())

    def test_daytime_zero_with_changing_weather_remains_observed_zero(self):
        frame = self.data.copy()
        frame["power"] = 0.0
        frame["is_daylight"] = True
        frame["solar_elevation_deg"] = 30.0
        frame["lmd_temperature"] = np.arange(6) + 10.0
        cleaned, log, runs = clean_local_values(frame, self.rules)
        self.assertTrue(runs.empty)
        self.assertTrue(log.empty)
        self.assertTrue(cleaned["flag_day_low_power_raw"].all())
        self.assertTrue(cleaned["valid_power_for_q1"].all())
        self.assertTrue(cleaned["power_clean"].eq(0).all())


if __name__ == "__main__":
    unittest.main()
