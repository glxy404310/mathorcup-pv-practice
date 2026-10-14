"""问题2—4的预测信息边界与附件指标检验。"""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from q234_forecast import history_features, metrics, project, test_mask


class ForecastBoundaryTests(unittest.TestCase):
    def data(self):
        index = pd.date_range('2018-08-01',periods=45*96,freq='15min',tz='Asia/Shanghai')
        return pd.DataFrame({'power_clean':np.sin(np.arange(len(index))/96)**2*10,
            'reference_mw':10.,'clear_ghi':800.,'elevation':45.,'azimuth':180.,
            'daylight':True,'test':False,'nwp_globalirrad':500.,'lmd_totalirrad_clean':500.},index=index)

    def test_future_power_and_weather_cannot_change_history_model_input(self):
        data = self.data()
        issue = pd.Timestamp('2018-08-25',tz='Asia/Shanghai')
        target = pd.date_range(issue+pd.Timedelta(days=1),periods=672,freq='15min')
        x,baseline,last = history_features(data,issue,target)
        modified = data.copy()
        modified.loc[modified.index>=issue,'power_clean'] = 999.
        modified['nwp_globalirrad'],modified['lmd_totalirrad_clean'] = -999.,-999.
        other,b2,last2 = history_features(modified,issue,target)
        pd.testing.assert_frame_equal(x,other)
        for name in baseline: np.testing.assert_array_equal(baseline[name],b2[name])
        self.assertLess(last,issue);self.assertEqual(last,last2)

    def test_preceding_test_power_is_not_used_as_history(self):
        data = self.data()
        data.loc[data.index.day>=25,'test'] = True
        issue = pd.Timestamp('2018-09-03',tz='Asia/Shanghai')
        target = pd.date_range(issue+pd.Timedelta(days=1),periods=672,freq='15min')
        x,baseline,_ = history_features(data,issue,target)
        data.loc[data.test,'power_clean'] = 9999.
        other,b2,_ = history_features(data,issue,target)
        pd.testing.assert_frame_equal(x,other)
        for name in baseline: np.testing.assert_array_equal(baseline[name],b2[name])

    def test_qr_uses_strict_threshold_cr_is_percent_and_me_is_pred_minus_actual(self):
        score = metrics([0,0,999],[4,5,999],[True,True,False],20)
        self.assertEqual(score['n'],2)
        self.assertEqual(score['QR_pct'],50.)
        self.assertAlmostEqual(score['nME'],.225)
        self.assertAlmostEqual(score['nRMSE'],np.sqrt((.2**2+.25**2)/2))
        self.assertAlmostEqual(score['CR_pct'],(1-score['nRMSE'])*100)

    def test_last_seven_natural_days_and_no_night_truth_mask(self):
        dates = pd.date_range('2019-02-01',periods=28,freq='D',tz='Asia/Shanghai')
        mask = test_mask(dates)
        self.assertEqual(mask.sum(),7)
        self.assertEqual(dates[mask][0].day,22)
        values = project([-3,30,5],[True,True,False])
        np.testing.assert_array_equal(values,[0,20,0])


if __name__=='__main__': unittest.main()
