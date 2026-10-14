"""汇总station08第一问重跑，按共同完整日比较station01，生成当前对比稿。"""
import hashlib
import json

import pandas as pd
from q1_check_data import ROOT, save_csv


def load(station, name):
    return json.loads((ROOT / 'results/q1' / station / name).read_text())


def markdown_table(frame):
    frame = frame.rename(columns={
        'year_month': '月份', 'observed_days': '观测日', 'complete_power_days': '完整功率日',
        'mean_daily_integral_estimate_mwh': '日积分均值(MWh)', 'reference_mean_daily_integral_same_days_mwh': '同日参考均值(MWh)',
        'season': '季节', 'average_profile_peak_mw': '平均曲线峰值(MW)', 'average_profile_peak_clock': '峰值时刻',
        'included_year_months': '包含月份', 'scenario': '情景', 'common_daylight_points': '白昼样本数',
        'reference_peak_mw': '参考峰值(MW)', 'mean_actual_minus_reference_mw': '平均实际减参考(MW)',
        'mae_to_reference_mw': '平均绝对偏差(MW)', 'station': '站点', 'common_complete_days': '共同完整日',
        'mean_daily_integral_mwh': '日积分均值(MWh)', 'strong_irradiance_zero_low_points': '强辐照零低功率点',
        'p95_abs_ramp_mw': '变化绝对值P95(MW)', 'ramp_irradiance_pearson': '功率辐照变化相关系数'})
    if '情景' in frame:
        frame['情景'] = frame['情景'].replace({'reference_ac_loss0_mw': '额外损耗0%', 'reference_ac_loss10_mw': '额外损耗10%',
            'reference_ac_loss20_mw': '额外损耗20%', 'reference_ac_altitude200_loss0_mw': '海拔200m，损耗0%'})
    if '季节' in frame:
        frame['季节'] = frame['季节'].replace({'spring': '春', 'summer': '夏', 'autumn': '秋', 'winter': '冬'})
    def format_value(x):
        return f'{x:.3f}' if isinstance(x, float) else str(x)
    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(map(format_value, row)) + ' |' for row in frame.itertuples(index=False, name=None)])


def main():
    stations = ('station01', 'station08')
    folder = ROOT / 'results/q1/station08'
    # 昨日ZIP已不在项目中，按昨日清洗表保留的全部原始列核对station01。
    original = pd.read_csv(ROOT / 'data/PVOD/station01.csv')
    previous = pd.read_csv(ROOT / 'data/processed/station01_q1_clean.csv')
    pd.testing.assert_frame_equal(original, previous[original.columns], check_exact=False, rtol=1e-12, atol=1e-12)
    audits = {s: load(s, 'summary.json') for s in stations}
    cleans = {s: load(s, 'cleaning_summary.json') for s in stations}
    chars = {s: load(s, 'characteristics_summary.json') for s in stations}
    refs = {s: load(s, 'reference_summary.json') for s in stations}
    daily = {s: pd.read_csv(ROOT / 'results/q1' / s / 'daily_characteristics.csv') for s in stations}
    common_dates = sorted(set.intersection(*[set(daily[s].loc[daily[s].complete_power_day, 'date_local']) for s in stations]))
    save_csv(pd.DataFrame({'date_local': common_dates}), folder / 'comparison_common_complete_dates.csv')
    quality, matched = [], []
    for station in stations:
        a, c = audits[station], cleans[station]
        quality.append({'站点': station, '原始记录': a['rows'], '缺失时间点': a['missing_timestamps'],
                        '可疑持值段': c['candidate_frozen_runs'], '清洗缺失功率点': c['invalid_power_points'],
                        '完整功率日': c['complete_power_days'], '强辐照零低功率点': c['day_zero_flags_retained'],
                        '清洗后夜间正功率点': c['remaining_night_positive_power_points']})
        data = pd.read_csv(ROOT / 'data/processed' / f'{station}_q1_clean.csv')
        path = ROOT / 'data/processed' / f'{station}_q1_clean.csv'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == chars[station]['cleaned_data_sha256'] == refs[station]['cleaned_data_sha256']
        assert hashlib.sha256((ROOT / 'results/q1' / station / 'reference_power.csv').read_bytes()).hexdigest() == chars[station]['reference_data_sha256']
        times = pd.to_datetime(data.time_utc, utc=True).dt.tz_convert('Asia/Shanghai')
        data['time_local_parsed'] = times
        data = data.loc[times.dt.strftime('%Y-%m-%d').isin(common_dates)].copy()
        selected_daily = daily[station].loc[daily[station].date_local.isin(common_dates)]
        assert len(data) == len(common_dates) * 96 and data.power_clean.notna().all()
        pairs = data.time_local_parsed.diff().eq(pd.Timedelta(minutes=15)) & data.is_daylight & data.is_daylight.shift(fill_value=False)
        ramps = data.power_clean.diff().loc[pairs]
        iramps = data.lmd_totalirrad_clean.diff().loc[pairs]
        daylight = data.loc[data.is_daylight]
        zero = (daylight.lmd_totalirrad_clean > 200) & (daylight.power_clean <= 0.01)
        matched.append({'station': station, 'common_complete_days': len(common_dates), 'common_records': len(data),
                        'mean_daily_integral_mwh': selected_daily.actual_daily_integral_estimate_mwh.mean(),
                        'daylight_points': len(daylight), 'strong_irradiance_zero_low_points': int(zero.sum()),
                        'zero_low_fraction_of_daylight': zero.mean(), 'daylight_ramp_pairs': len(ramps),
                        'p95_abs_ramp_mw': ramps.abs().quantile(.95), 'max_abs_ramp_mw': ramps.abs().max(),
                        'ramp_irradiance_pearson': ramps.corr(iramps)})
    save_csv(pd.DataFrame(quality), folder / 'station_quality_comparison.csv')
    save_csv(pd.DataFrame(matched), folder / 'common_days_comparison.csv')
    missing = pd.read_csv(folder / 'missing_timestamps.csv')
    missing_days = sorted(pd.to_datetime(missing.missing_time_local).dt.strftime('%Y-%m-%d').unique())
    a, c, ch, r = audits['station08'], cleans['station08'], chars['station08'], refs['station08']
    rules = ROOT / 'docs/q1_cleaning_rules_station08.json'
    assumptions = ROOT / 'docs/q1_reference_assumptions_station08.json'
    assert hashlib.sha256(rules.read_bytes()).hexdigest() == c['rules_sha256']
    assert hashlib.sha256(assumptions.read_bytes()).hexdigest() == r['assumptions_sha256']
    assert a['source_sha256'] == c['source_sha256'] == r['source_zip_sha256']
    monthly = pd.read_csv(folder / 'monthly_characteristics.csv')
    seasonal = pd.read_csv(folder / 'seasonal_characteristics.csv')
    sensitivity = pd.read_csv(folder / 'reference_sensitivity.csv')
    extreme = pd.read_csv(folder / 'largest_daylight_changes.csv').iloc[0]
    base = r['scenarios'][0]
    h, low = ch['monthly_highest'], ch['monthly_lowest']
    text = rf'''# 第一问重跑与站点对比：station08

整理日期：2026-10-13。沿用第一问的模型和统计口径；station01仅保留对比复现必需的数据和结果，当前正文以station08为主。

## 1 数据与清洗

从`data/PVOD/station08.csv`和`metadata.csv`读取，UTC转换为北京时间。范围为{a['start_local']}至{a['end_local']}，共{a['rows']:,}条15分钟记录。无重复时间戳、字段缺失或基础非法值。时间网格缺失{a['missing_timestamps']}点，全部位于{', '.join(missing_days)}，对应3个整日；缺失日期没有补零或插值。现有{c['complete_power_days']}个观测日均有完整96点功率，但不代表时间范围内没有缺日。四个规定月末测试周各672点完整，清洗后功率也完整。

清洗沿用station01的阈值和规则，仅当功率与六项现场气象连续至少4点完全相同，且段内存在深夜正功率、正辐照时，才将后续重复值置缺失。本次候选持值段{c['candidate_frozen_runs']}个，修改字段值{c['modified_cells']}个。白昼强辐照下零/低功率{c['day_zero_flags_retained']}点、近地平线夜间正功率{c['remaining_night_positive_power_points']}点继续保留并标记。规则未发现异常不等于所有物理口径已核实。

## 2 晴空参考模型

使用station08元数据：经度113.89999°E、纬度36.70761°N，朝南33°，78042块265 Wp组件，直流额定容量20.68113 MWp。装机容量字段20000 kW，仍暂设交流限制20 MW；组件容量和交流限制分别定义。采用Ineichen晴空辐照、isotropic板面转换、固定组件温度25°C和PVWatts逆变器（假设额定效率96%）。海拔基准0m，反射率0.25。计算公式为：

$$P_{{dc,ref}}(t)=20.68113\,\frac{{G_{{poa}}(t)}}{{1000}}(1-L)\quad\mathrm{{MW}}.$$

逆变器DC输入限制为20/0.96 MW，额外损耗与逆变器损耗分别计算。坐标和组件配置来自元数据，其余假设沿用昨日方案；未通过实测功率拟合。采用pvlib {r['pvlib_version']}。夜间参考设为0，实测值不改动。参考不是严格上限，也不是日前预测。

## 3 月度和日内特性

日积分估计为96个采样功率求和×0.25小时；功率是瞬时或区间平均尚未确认，因此不宣称精确实测电量。实际和参考仅使用同一批完整日。缺日不进入分母。

{markdown_table(monthly[['year_month', 'observed_days', 'complete_power_days', 'mean_daily_integral_estimate_mwh', 'reference_mean_daily_integral_same_days_mwh']])}

![月度日积分估计](../figures/q1/station08_monthly_integral.png)

日积分估计均值最高为{h['year_month']}的{h['mean_daily_integral_estimate_mwh']:.2f} MWh，最低为{low['year_month']}的{low['mean_daily_integral_estimate_mwh']:.2f} MWh。2018年11月缺失3日，2019年6月仅到13日；不能将样本均值推广为完整月结果，也不能把月度差异唯一归因于季节。

{markdown_table(seasonal[['season', 'complete_power_days', 'average_profile_peak_mw', 'average_profile_peak_clock', 'included_year_months']])}

![季节平均日内曲线](../figures/q1/station08_seasonal_diurnal.png)

季节定义与昨日一致：3—5月春、6—8月夏、9—11月秋、12—2月冬。每组各时刻使用同一批完整日，阴影为不同日期P25—P75分布，不是置信区间。夏季跨2018年7/8月和2019年6月1—13日，不是单一完整夏季。平均峰值时刻是样本统计结果。

## 4 参考偏差与15分钟波动

共同有效白昼点{base['common_daylight_points']:,}个，实际减基准参考平均为{base['mean_actual_minus_reference_mw']:.3f} MW，平均绝对偏差{base['mae_to_reference_mw']:.3f} MW，实际超过参考{base['actual_exceeds_reference_points']}点。该MAE是物理参考偏差，不能写成预测误差。

![固定诊断日参考对照](../figures/q1/station08_reference_day.png)

只对连续15分钟且两端白昼、功率有效的点计算变化。有效点对{ch['daylight_power_pairs']:,}个，绝对变化中位数{ch['median_abs_15min_change_mw']:.3f} MW、P95为{ch['p95_abs_15min_change_mw']:.3f} MW、最大{ch['max_abs_15min_change_mw']:.3f} MW。功率变化与现场辐照变化的Pearson相关系数为{ch['power_irradiance_change_correlation']:.3f}，不能据此认定唯一因果原因。

最大变化时刻{extreme['time_local']}，功率变化{extreme['power_change_15min_mw']:.3f} MW，同期现场总辐照变化{extreme['irradiance_change_15min_wm2']:.1f} W/m²。事件取自station08结果表，没有沿用station01事件。

![白昼15分钟波动](../figures/q1/station08_daylight_fluctuation.png)

## 5 参数敏感性

{markdown_table(sensitivity[['scenario', 'common_daylight_points', 'reference_peak_mw', 'mean_actual_minus_reference_mw', 'mae_to_reference_mw']])}

0%、10%、20%损耗和200m海拔均为人为设定的敏感性情景。损耗较大时更接近实测并不能证明真实损耗就是该值；尚缺实际组件温度、海拔、逆变器数量和运维信息。

## 6 station08是否更适合

{markdown_table(pd.DataFrame(quality))}

两站各有345个完整功率日，但日期集合不同：station01因清洗排除3个日期，station08原始缺3个日期。因此进一步只比较两站共同完整的{len(common_dates)}天、各{len(common_dates)*96:,}条记录。站点坐标不同，白昼点数可以不同；共同日期控制日历覆盖，仍不能控制各站天气与设备差异。

{markdown_table(pd.DataFrame(matched)[['station', 'common_complete_days', 'mean_daily_integral_mwh', 'strong_irradiance_zero_low_points', 'p95_abs_ramp_mw', 'ramp_irradiance_pearson']])}

station08在当前规则下没有station01的深夜多字段持值问题，强辐照零/低功率标记也更少，适合用于第一问的替代站点分析。但它有3天原始缺测，清洗后完整日数量没有增加，近地平线夜间正功率也没有更少。因此可称当前已检查的异常较少，不能称全面优于station01，更不能据此认定后续预测准确率更高。后续预测需采用相同切分、基线和评估口径实测。

## 7 复现与证据

```bash
.venv/bin/python src/q1_check_data.py --station station08 --source data/PVOD
.venv/bin/python src/q1_clean_data.py --rules docs/q1_cleaning_rules_station08.json
.venv/bin/python src/q1_reference_power.py --assumptions docs/q1_reference_assumptions_station08.json --source data/PVOD
.venv/bin/python src/q1_characteristics.py --station station08
.venv/bin/python src/build_q1_station08_report.py
```

昨日ZIP已不在项目内，本次核对目录station01与昨日清洗表保留的全部原始列一致（浮点容差1e-12）；两站结果文件也分别校验数据哈希。逐点结果、月度/季节表、敏感性表、日期对照及哈希清单位于`results/q1/station08/`。第一问仍受不足完整一年、功率AC/DC和采样区间口径未确认、参考设备参数简化、异常原因未确认等限制。模型公式和方法依据沿用`docs/第一问_参考功率方案.md`中的pvlib接口说明；该文件的station01设备参数不用于本次station08计算。
'''
    draft = ROOT / 'paper/第一问_station08重跑与对比.md'
    draft.write_text(text, encoding='utf-8')
    inputs = [ROOT / 'data/PVOD/metadata.csv', ROOT / 'data/PVOD/station08.csv', rules, assumptions]
    for station in stations:
        for name in ('summary.json', 'cleaning_summary.json', 'reference_summary.json', 'characteristics_summary.json', 'daily_characteristics.csv'):
            inputs.append(ROOT / 'results/q1' / station / name)
        inputs.extend([ROOT / 'data/processed' / f'{station}_q1_clean.csv', ROOT / 'results/q1' / station / 'reference_power.csv'])
    inputs.extend(ROOT / 'src' / name for name in ('q1_check_data.py', 'q1_clean_data.py', 'q1_reference_power.py', 'q1_characteristics.py', 'build_q1_station08_report.py'))
    manifest = {'version': 'q1-station08-rerun-v1', 'date': '2026-10-13', 'station01_raw_columns_match_previous_processed': True, 'original_zip_available': False,
                'common_complete_days': len(common_dates), 'missing_station08_dates': missing_days,
                'inputs_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                'draft_sha256': hashlib.sha256(draft.read_bytes()).hexdigest(), 'status': '练习审阅稿，设备及采样口径仍待核实'}
    (folder / 'rerun_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'draft': str(draft), 'common_days': len(common_dates), 'comparison': matched}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
