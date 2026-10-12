"""防止缺测日被当完整日，以及跨缺口制造15分钟变化。"""

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from q1_characteristics import complete_daily_integrals, continuous_changes


class CharacteristicsTests(unittest.TestCase):
    def setUp(self):
        self.day = pd.DataFrame({
            "time_local": pd.date_range("2019-05-01", periods=96, freq="15min", tz="Asia/Shanghai"),
            "power_clean": np.ones(96), "power": np.ones(96),
            "reference_ac_loss0_mw": np.ones(96) * 2, "needs_review": np.zeros(96, dtype=bool),
        })

    def test_constant_one_mw_integrates_to_twenty_four_mwh(self):
        daily = complete_daily_integrals(self.day)
        self.assertTrue(daily.loc[0, "complete_power_day"])
        self.assertEqual(daily.loc[0, "actual_daily_integral_estimate_mwh"], 24.0)
        self.assertEqual(daily.loc[0, "reference_daily_integral_same_day_mwh"], 48.0)

    def test_one_missing_power_does_not_become_zero_or_a_complete_day(self):
        self.day.loc[40, "power_clean"] = np.nan
        daily = complete_daily_integrals(self.day)
        self.assertFalse(daily.loc[0, "complete_power_day"])
        self.assertTrue(pd.isna(daily.loc[0, "actual_daily_integral_estimate_mwh"]))
        self.assertTrue(pd.isna(daily.loc[0, "reference_daily_integral_same_day_mwh"]))

    def test_ninety_six_rows_with_duplicate_time_are_not_a_complete_grid(self):
        self.day.loc[40, "time_local"] = self.day.loc[39, "time_local"]
        daily = complete_daily_integrals(self.day)
        self.assertFalse(daily.loc[0, "complete_grid"])
        self.assertTrue(pd.isna(daily.loc[0, "actual_daily_integral_estimate_mwh"]))

    def test_ramp_does_not_bridge_time_gap_or_missing_power(self):
        frame = pd.DataFrame({
            "source_csv_row": [2, 3, 4, 5],
            "time_local": pd.to_datetime(["2019-05-01 10:00", "2019-05-01 10:15",
                                           "2019-05-01 10:45", "2019-05-01 11:00"]).tz_localize("Asia/Shanghai"),
            "power_clean": [0, 1, 3, np.nan], "lmd_totalirrad_clean": [0, 100, 300, 400],
            "is_daylight": [True] * 4,
        })
        ramps = continuous_changes(frame)
        self.assertEqual(ramps.loc[1, "power_change_15min_mw"], 1.0)
        self.assertTrue(ramps.loc[[0, 2, 3], "power_change_15min_mw"].isna().all())
        self.assertEqual(int(ramps["valid_daylight_weather_power_pair"].sum()), 1)


if __name__ == "__main__":
    unittest.main()
