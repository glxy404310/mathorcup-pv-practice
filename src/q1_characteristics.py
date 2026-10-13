"""第一问步骤4：月度日积分估计、季节日内曲线、白昼偏差与连续15分钟变化。"""

import calendar
import argparse
import hashlib
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

from q1_check_data import ROOT, STEP, save_csv


SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
SEASON_LABELS = {"spring": "春季", "summer": "夏季（非完整、跨年时段）", "autumn": "秋季", "winter": "冬季"}


def complete_daily_integrals(data):
    """只对本地日历日的完整96点求积分近似；缺失绝不隐式当0。"""
    records = []
    for day, group in data.groupby(data["time_local"].dt.date):
        start = pd.Timestamp(day, tz="Asia/Shanghai")
        expected = pd.date_range(start, periods=96, freq="15min")
        complete_grid = pd.DatetimeIndex(group["time_local"]).equals(expected)
        valid_points = int(group["power_clean"].notna().sum())
        complete = complete_grid and valid_points == 96
        records.append({
            "date_local": str(day), "year_month": str(day)[:7], "season": SEASONS[day.month],
            "observed_points": len(group), "valid_power_points": valid_points,
            "complete_grid": complete_grid, "complete_power_day": complete,
            "review_points": int(group["needs_review"].sum()),
            "actual_daily_integral_estimate_mwh": float(group["power_clean"].sum() * 0.25) if complete else np.nan,
            "reference_daily_integral_same_day_mwh": float(group["reference_ac_loss0_mw"].sum() * 0.25) if complete else np.nan,
            "raw_daily_integral_estimate_mwh": float(group["power"].sum() * 0.25) if complete_grid and group["power"].notna().all() else np.nan,
        })
    return pd.DataFrame(records)


def continuous_changes(data):
    """只有时间连续且两个样本均非缺失时计算变化，天气变化也单独检查有效性。"""
    contiguous = data["time_local"].diff().eq(STEP)
    power_pair = contiguous & data["power_clean"].notna() & data["power_clean"].shift().notna()
    weather_pair = contiguous & data["lmd_totalirrad_clean"].notna() & data["lmd_totalirrad_clean"].shift().notna()
    daylight_pair = data["is_daylight"] & data["is_daylight"].shift(fill_value=False)
    output = data[["source_csv_row", "time_local", "power_clean", "lmd_totalirrad_clean"]].copy()
    output["power_change_15min_mw"] = data["power_clean"].diff().where(power_pair)
    output["irradiance_change_15min_wm2"] = data["lmd_totalirrad_clean"].diff().where(weather_pair)
    output["valid_power_pair"] = power_pair
    output["both_points_daylight"] = daylight_pair
    output["valid_daylight_weather_power_pair"] = power_pair & weather_pair & daylight_pair
    return output


def aggregate_months(daily):
    rows = []
    for month, group in daily.groupby("year_month", sort=True):
        eligible = group.loc[group["complete_power_day"]]
        year, number = map(int, month.split("-"))
        energy = eligible["actual_daily_integral_estimate_mwh"]
        rows.append({"year_month": month, "calendar_days": calendar.monthrange(year, number)[1],
                     "observed_days": len(group), "complete_power_days": len(eligible),
                     "incomplete_power_days": len(group) - len(eligible),
                     "mean_daily_integral_estimate_mwh": energy.mean(), "median_daily_integral_estimate_mwh": energy.median(),
                     "p10_daily_integral_estimate_mwh": energy.quantile(0.1), "p90_daily_integral_estimate_mwh": energy.quantile(0.9),
                     "reference_mean_daily_integral_same_days_mwh": eligible["reference_daily_integral_same_day_mwh"].mean(),
                     "raw_mean_daily_integral_all_observed_days_mwh": group["raw_daily_integral_estimate_mwh"].mean(),
                     "partial_calendar_month": len(group) != calendar.monthrange(year, number)[1]})
    return pd.DataFrame(rows)


def seasonal_profiles(data, daily):
    eligible_dates = set(daily.loc[daily["complete_power_day"], "date_local"])
    eligible = data.loc[data["time_local"].dt.strftime("%Y-%m-%d").isin(eligible_dates)].copy()
    eligible["season"] = eligible["time_local"].dt.month.map(SEASONS)
    eligible["quarter_hour"] = eligible["time_local"].dt.hour * 4 + eligible["time_local"].dt.minute // 15
    profiles = eligible.groupby(["season", "quarter_hour"]).agg(
        samples=("power_clean", "count"), actual_mean_mw=("power_clean", "mean"),
        actual_p25_mw=("power_clean", lambda x: x.quantile(0.25)),
        actual_p75_mw=("power_clean", lambda x: x.quantile(0.75)),
        reference_mean_mw=("reference_ac_loss0_mw", "mean")).reset_index()
    profiles["clock_local"] = profiles["quarter_hour"].map(lambda q: f"{q // 4:02d}:{q % 4 * 15:02d}")
    season_rows = []
    for season, group in daily.groupby("season"):
        valid = group.loc[group["complete_power_day"]]
        profile = profiles.loc[profiles["season"].eq(season)]
        peak = profile.loc[profile["actual_mean_mw"].idxmax()] if len(profile) else None
        season_rows.append({"season": season, "included_year_months": ", ".join(group["year_month"].unique()),
                            "observed_days": len(group), "complete_power_days": len(valid),
                            "mean_daily_integral_estimate_mwh": valid["actual_daily_integral_estimate_mwh"].mean(),
                            "average_profile_peak_mw": peak["actual_mean_mw"] if peak is not None else np.nan,
                            "average_profile_peak_clock": peak["clock_local"] if peak is not None else None,
                            "season_coverage_note": "夏季合并2018年7/8月与2019年6月1—13日；不是单一完整夏季" if season == "summer"
                            else "仅描述本数据观测时段；不据此推广多年季节规律"})
    return profiles, pd.DataFrame(season_rows)


def plot_results(monthly, profiles, ramps, season_summary, figures, station="station01"):
    fonts = {font.name for font in font_manager.fontManager.ttflist}
    chinese = next((name for name in ("PingFang HK", "Songti SC", "Heiti TC", "SimHei", "Noto Sans CJK SC")
                    if name in fonts), None)
    plt.rcParams["font.family"] = chinese or "DejaVu Sans"
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(13, 5.5))
    x = np.arange(len(monthly))
    ax.bar(x, monthly["mean_daily_integral_estimate_mwh"], width=0.55, color="#2563a6",
           label="实际日积分估计均值" if chinese else "Mean actual daily integral estimate")
    ax.vlines(x, monthly["p10_daily_integral_estimate_mwh"], monthly["p90_daily_integral_estimate_mwh"],
              color="#153759", linewidth=1.2, label="不同日期P10—P90范围" if chinese else "Across-day P10-P90")
    ax.plot(x, monthly["reference_mean_daily_integral_same_days_mwh"], color="#555555", linestyle="--", marker="s",
            markersize=4, label="同一批完整日的晴空参考" if chinese else "Clear-sky reference on the same complete days")
    ax.set_xticks(x, [f"{r.year_month}\nn={r.complete_power_days}" for r in monthly.itertuples()])
    ax.set_ylim(bottom=0)
    ax.set_ylabel("日积分估计（MWh）" if chinese else "Daily integral estimate (MWh)")
    ax.set_title(f"{station} 月度日积分估计（完整功率日）" if chinese else f"{station}: monthly daily integral estimates (complete days)")
    ax.legend(frameon=False, fontsize=9, ncol=3)
    ax.grid(axis="y", color="#e4e7eb")
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.06, 0.015, "Σ采样功率×0.25小时；采样口径待确认，非精确实测电量。P10—P90为不同日期分布，不是置信区间；2019年6月仅到13日。" if chinese else
             "Sum(samples) × 0.25 h; sampling convention unconfirmed. P10-P90 is spread, not confidence; June ends on the 13th.", fontsize=9)
    fig.tight_layout(rect=(0, 0.065, 1, 1))
    fig.savefig(figures / f"{station}_monthly_integral.png", dpi=300)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
    for ax, season in zip(axes.flat, ("spring", "summer", "autumn", "winter")):
        frame = profiles.loc[profiles["season"].eq(season)]
        q = frame["quarter_hour"].to_numpy() / 4
        ax.plot(q, frame["actual_mean_mw"], color="#2563a6", linewidth=1.7, label="实际平均" if chinese else "Actual mean")
        ax.fill_between(q, frame["actual_p25_mw"], frame["actual_p75_mw"], color="#2563a6", alpha=0.15,
                        label="实际P25—P75" if chinese else "Actual P25-P75")
        ax.plot(q, frame["reference_mean_mw"], color="#555555", linestyle="--", linewidth=1.3,
                label="晴空参考平均" if chinese else "Mean clear-sky reference")
        days = int(season_summary.loc[season_summary["season"].eq(season), "complete_power_days"].iloc[0])
        ax.set_title(f"{SEASON_LABELS[season] if chinese else season}: n={days}日" if chinese else f"{season}: n={days} days")
        ax.set_xlim(0, 23.75)
        ax.set_ylim(0, 21)
        ax.set_xticks([0, 6, 12, 18, 23.75], ["00:00", "06:00", "12:00", "18:00", "23:45"])
        ax.grid(axis="y", color="#e4e7eb")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0, 0].legend(frameon=False, fontsize=9)
    for ax in axes[:, 0]: ax.set_ylabel("功率（MW）" if chinese else "Power (MW)")
    fig.suptitle(f"{station} 各季节平均日内形状（完整日，北京时间）" if chinese else f"{station}: seasonal diurnal profiles (complete days, Asia/Shanghai)")
    fig.text(0.06, 0.017, "同一季节各时刻使用同一批完整日；阴影为不同日期P25—P75，不是置信区间。夏季为跨年且不完整的观测时段。" if chinese else
             "Each season uses the same complete days at all times; shading is P25-P75, not confidence. Summer is partial and spans years.", fontsize=9)
    fig.tight_layout(rect=(0, 0.065, 1, 0.96))
    fig.savefig(figures / f"{station}_seasonal_diurnal.png", dpi=300)
    plt.close(fig)

    daylight = ramps.loc[ramps["valid_power_pair"] & ramps["both_points_daylight"]]
    paired = ramps.loc[ramps["valid_daylight_weather_power_pair"]]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].hist(daylight["power_change_15min_mw"], bins=50, color="#2563a6", rwidth=0.98)
    axes[0].set_xlabel("15分钟功率变化（MW）" if chinese else "15-minute power change (MW)")
    axes[0].set_ylabel("点数" if chinese else "Count")
    axes[0].set_title(f"白昼相邻变化分布（n={len(daylight)}）" if chinese else f"Daylight ramp distribution (n={len(daylight)})")
    axes[1].scatter(paired["irradiance_change_15min_wm2"], paired["power_change_15min_mw"],
                    color="#2563a6", s=6, alpha=0.15, rasterized=True)
    axes[1].set_xlabel("15分钟现场总辐照变化（W/m²）" if chinese else "15-minute local irradiance change (W/m²)")
    axes[1].set_ylabel("15分钟功率变化（MW）" if chinese else "15-minute power change (MW)")
    axes[1].set_title(f"共同有效白昼点（n={len(paired)}）" if chinese else f"Common valid daylight pairs (n={len(paired)})")
    for ax in axes:
        ax.axvline(0, color="#555555", linewidth=0.8)
        ax.grid(axis="y", color="#e4e7eb")
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.06, 0.018, "只计算连续15分钟且两端有效的点；两端太阳高度角均>0。散点呈现相关性，不能确认单一原因。" if chinese else
             "Only contiguous 15-min pairs with valid endpoints above the horizon; association does not establish a unique cause.", fontsize=9)
    fig.tight_layout(rect=(0, 0.065, 1, 1))
    fig.savefig(figures / f"{station}_daylight_fluctuation.png", dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default="station01")
    args = parser.parse_args()
    station = args.station
    folder = ROOT / "results/q1" / station
    clean_path = ROOT / "data/processed" / f"{station}_q1_clean.csv"
    reference_path = folder / "reference_power.csv"
    provenance = json.loads((folder / "reference_summary.json").read_text())
    if hashlib.sha256(clean_path.read_bytes()).hexdigest() != provenance["cleaned_data_sha256"]:
        raise ValueError("清洗数据已变化，先重跑q1_reference_power.py，避免混用版本")
    cleaned = pd.read_csv(clean_path)
    reference = pd.read_csv(reference_path)
    cols = ["source_csv_row", "time_utc", "is_daylight", "reference_ac_loss0_mw", "deviation_actual_minus_reference_mw"]
    data = cleaned.merge(reference[cols], on=["source_csv_row", "time_utc"], how="left", validate="one_to_one", suffixes=("", "_reference"))
    if len(data) != len(reference) or data["reference_ac_loss0_mw"].isna().any():
        raise ValueError("清洗数据与参考曲线不完整对应")
    data["time_local"] = pd.to_datetime(data["time_utc"], utc=True).dt.tz_convert("Asia/Shanghai")
    data = data.sort_values("time_local").reset_index(drop=True)
    if data["time_local"].duplicated().any(): raise ValueError("重复时间戳不能静默汇总")
    if not data["is_daylight"].eq(data["is_daylight_reference"]).all(): raise ValueError("两步骤白昼规则不一致")
    daily = complete_daily_integrals(data)
    monthly = aggregate_months(daily)
    profiles, seasonal = seasonal_profiles(data, daily)
    ramps = continuous_changes(data)
    daylight_ramps = ramps.loc[ramps["valid_power_pair"] & ramps["both_points_daylight"]]
    paired = ramps.loc[ramps["valid_daylight_weather_power_pair"]]
    abs_ramp = daylight_ramps["power_change_15min_mw"].abs()
    common = data.loc[data["is_daylight"] & data["power_clean"].notna()].copy()
    common["year_month"] = common["time_local"].dt.strftime("%Y-%m")
    deviation = common.groupby("year_month").agg(points=("power_clean", "count"),
        mean_actual_minus_reference_mw=("deviation_actual_minus_reference_mw", "mean"),
        mean_abs_deviation_mw=("deviation_actual_minus_reference_mw", lambda x: x.abs().mean()),
        actual_above_reference_fraction=("deviation_actual_minus_reference_mw", lambda x: x.gt(0).mean())).reset_index()
    extreme = daylight_ramps.assign(abs_change_mw=abs_ramp).sort_values("abs_change_mw", ascending=False).head(10)
    zero_events = daylight_ramps.loc[(daylight_ramps["power_clean"] <= 0.01)
        & (daylight_ramps["lmd_totalirrad_clean"] > 200)].copy()
    zero_events["abs_change_mw"] = zero_events["power_change_15min_mw"].abs()
    zero_events = zero_events.sort_values("abs_change_mw", ascending=False).head(5)
    corr = paired["power_change_15min_mw"].corr(paired["irradiance_change_15min_wm2"])
    for frame, name in [(daily, "daily_characteristics.csv"), (monthly, "monthly_characteristics.csv"),
                        (profiles, "seasonal_diurnal_profiles.csv"), (seasonal, "seasonal_characteristics.csv"),
                        (ramps, "continuous_15min_changes.csv"), (extreme, "largest_daylight_changes.csv"),
                        (deviation, "monthly_daylight_deviation.csv"),
                        (zero_events, "zero_power_daylight_events.csv")]: save_csv(frame, folder / name)
    summary = {"station": station, "analysis_version": "q1-characteristics-v1", "rows": len(data),
               "cleaned_data_sha256": hashlib.sha256(clean_path.read_bytes()).hexdigest(),
               "reference_data_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
               "reference_model_version": provenance["model_version"], "observed_days": len(daily),
               "complete_power_days": int(daily["complete_power_day"].sum()),
               "daylight_power_pairs": len(daylight_ramps), "daylight_weather_power_pairs": len(paired),
               "median_abs_15min_change_mw": float(abs_ramp.median()),
               "p95_abs_15min_change_mw": float(abs_ramp.quantile(0.95)),
               "max_abs_15min_change_mw": float(abs_ramp.max()),
               "power_irradiance_change_correlation": float(corr) if np.isfinite(corr) else None,
               "energy_method": "每个完整本地日的96个采样功率求和×0.25h；矩形积分近似，不宣称精确实测电量",
               "monthly_highest": monthly.loc[monthly["mean_daily_integral_estimate_mwh"].idxmax()].to_dict(),
               "monthly_lowest": monthly.loc[monthly["mean_daily_integral_estimate_mwh"].idxmin()].to_dict(),
               "largest_change": extreme.iloc[0].astype(str).to_dict(),
               "limits": ["功率采样与时间戳区间口径仍未确认，电量为积分估计",
                          "首尾月份覆盖及夏季跨年情况须结合逐日覆盖表复核",
                          "参考功率参数含明确假设；实际/参考差异不是预测误差或唯一故障证据",
                          "保留的可疑零功率、近地平线正功率和持值首点仍可能影响统计",
                          "月度与季节均为描述性比较，没有对天气、设备状态和采样日期作因果控制"]}
    # pandas标量转为标准JSON类型，保持输入行与所有计算表可追溯。
    (folder / "characteristics_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    plot_results(monthly, profiles, ramps, seasonal, ROOT / "figures/q1", station)
    highest, lowest = summary["monthly_highest"], summary["monthly_lowest"]
    lines = ["# 第一问月度、日内与波动分析（v1）", "", "本文件由src/q1_characteristics.py生成；观察与原因解释分开记录。", "",
             "## 计算口径", "", f"- {summary['observed_days']}个观测日中，月度与日内曲线使用{summary['complete_power_days']}个完整96点功率日。",
             "- 日积分估计=Σ采样功率×0.25小时，单位MWh；功率采样口径未确认，这不是精确实测电量。",
             "- 月度参考和实际使用同一批完整日。偏差与波动另使用共同有效白昼点，数量单独报告。",
             "- 日内阴影是不同日期的P25—P75分布，月度范围是P10—P90，均不是置信区间。", "",
             "## 月度结果", "", "| 月份 | 观测天数 | 完整功率日 | 日积分估计均值（MWh） | 同日参考均值（MWh） |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {r.year_month} | {r.observed_days} | {r.complete_power_days} | {r.mean_daily_integral_estimate_mwh:.2f} | {r.reference_mean_daily_integral_same_days_mwh:.2f} |" for r in monthly.itertuples()]
    lines += ["", f"在本次有效日和积分近似下，最高月份为{highest['year_month']}，均值{highest['mean_daily_integral_estimate_mwh']:.2f} MWh，完整日{highest['complete_power_days']}天；",
              f"最低为{lowest['year_month']}，均值{lowest['mean_daily_integral_estimate_mwh']:.2f} MWh，完整日{lowest['complete_power_days']}天。",
              "不能据此认定单一气象原因或长期季节规律。2019年6月不完整，不能把其均值直接推广到整个6月。",
              "原始全观测日均值另存在monthly_characteristics.csv，供检查清洗敏感性；它与清洗均值的日集合不同，不是同样本对照。", "",
              "## 平均日内形状", "", "| 季节分组 | 完整日 | 平均曲线峰值（MW） | 峰值时刻（北京时间） | 包含月份 |", "|---|---:|---:|---|---|"]
    lines += [f"| {SEASON_LABELS[r.season]} | {r.complete_power_days} | {r.average_profile_peak_mw:.2f} | {r.average_profile_peak_clock} | {r.included_year_months} |" for r in seasonal.itertuples()]
    lines += ["", "夏季含2018年7/8月和2019年6月1—13日，不是一个完整连续夏季。平均曲线的峰值时刻是观测统计结果，不等于每天的太阳正午或最大发电时刻。", "",
              "## 连续15分钟变化", "", f"- 两端均在白昼且功率有效的连续点对：{len(daylight_ramps)}；同时有有效辐照变化的点对：{len(paired)}。",
              f"- 绝对功率变化中位数{summary['median_abs_15min_change_mw']:.3f} MW，P95为{summary['p95_abs_15min_change_mw']:.3f} MW，最大{summary['max_abs_15min_change_mw']:.3f} MW。",
              f"- 最大变化位于{summary['largest_change']['time_local']}，带符号变化{float(summary['largest_change']['power_change_15min_mw']):.3f} MW，见largest_daylight_changes.csv。",
              f"- 同期功率变化与现场总辐照变化的Pearson相关系数为{corr:.3f}；相关性不能确认单一原因。",
              "- 有辐照但功率为零的真实记录仍在样本中；最大突降应结合原始记录、辐照和运维信息解释，不直接认定云遮挡或故障。", "",
              "## 保留的零功率事件", "",
              "zero_power_daylight_events.csv列出白昼总辐照>200 W/m²、功率≤0.01 MW时绝对变化最大的5个记录；没有根据事后解释删除。", "",
              "| 目标时刻（北京时间） | 15分钟功率变化（MW） | 同期辐照变化（W/m²） |", "|---|---:|---:|"]
    lines += [f"| {r.time_local} | {r.power_change_15min_mw:.3f} | {r.irradiance_change_15min_wm2:.1f} |" for r in zero_events.itertuples()]
    lines += ["", "功率降到零而辐照仍为正或上升，说明仅用辐照变化无法解释所有事件；尚缺故障、限电、测量状态等记录，原因不能确认。", "",
              "## 实际与参考偏差", "", "monthly_daylight_deviation.csv按月保留白昼有效点数、平均实际减参考、平均绝对差及超过参考的比例。",
              "这些量是对简化物理参考的描述，不是日前预测评测；缺测实际值不填补。", "",
              "## 图与结果位置", "", f"- figures/q1/{station}_monthly_integral.png：月度均值、日间范围与同日参考。",
              f"- figures/q1/{station}_seasonal_diurnal.png：各季节平均日内形状。",
              f"- figures/q1/{station}_daylight_fluctuation.png：白昼变化分布与辐照变化散点。",
              f"- 计算表保存在results/q1/{station}，摘要数字可逐项追溯。", "",
              "## 局限与下一步", "", *[f"- {item}" for item in summary["limits"]], "",
              "下一步由A、B、C结合结果写第一问解释草稿，并用损耗、清洗与积分口径敏感性讨论限制；获得测量或设备说明后再修订。"]
    (folder / "特性分析摘要.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ["complete_power_days", "monthly_highest", "monthly_lowest",
                     "daylight_power_pairs", "p95_abs_15min_change_mw", "power_irradiance_change_correlation"]}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
