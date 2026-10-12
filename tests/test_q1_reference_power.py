"""检验参考模型的单位、DC/AC容量口径和损耗情景。"""

from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from q1_reference_power import reference_from_poa


class ReferencePowerTests(unittest.TestCase):
    def test_zero_irradiance_produces_zero_dc_and_ac(self):
        dc, ac = reference_from_poa([0], 19.98e6, 20e6, 0.96)
        self.assertEqual(dc[0], 0)
        self.assertEqual(ac[0], 0)

    def test_dc_capacity_at_reference_irradiance_and_separate_ac_limit(self):
        dc, ac = reference_from_poa([1000, 2000], 19.98e6, 20e6, 0.96)
        np.testing.assert_allclose(dc, [19.98, 39.96])
        self.assertLess(ac[0], 19.98)
        self.assertAlmostEqual(ac[1], 20.0)

    def test_increasing_loss_does_not_increase_ac_power(self):
        outputs = [reference_from_poa([100, 500, 1000, 2000], 19.98e6, 20e6, 0.96, loss)[1]
                   for loss in [0, 0.1, 0.2]]
        self.assertTrue((outputs[0] >= outputs[1]).all())
        self.assertTrue((outputs[1] >= outputs[2]).all())


if __name__ == "__main__":
    unittest.main()
