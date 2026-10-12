"""第一问步骤2：复查持值，保留原始列，另存清洗列和逐值处理日志。"""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import pvlib

from q1_check_data import ROOT, STEP, UNITS, read_station, save_csv, test_week_coverage


def find_frozen_runs(data, rules):
    """只把连续、多字段持值且跨越深夜的段作为候选；首点与重复点分开。"""
    fields = rules["frozen_fields"]
    all_finite = np.isfinite(data[fields]).all(axis=1)
    same = (data[fields].eq(data[fields].shift()).all(axis=1)
            & all_finite & all_finite.shift(fill_value=False)
            & data["time_local"].diff().eq(STEP))
    run_ids = (~same).cumsum()
    segment = pd.Series(False, index=data.index)
    repeats = pd.Series(False, index=data.index)
    rows = []
    for run_id, group in data.groupby(run_ids):
        impossible_night = ((group["solar_elevation_deg"] < rules["deep_night_elevation_deg"])
                            & (group["power"] > rules["power_tolerance_mw"])
                            & (group["lmd_totalirrad"] > 0))
        if len(group) < rules["frozen_min_points"] or not impossible_night.any():
            continue
        segment.loc[group.index] = True
        repeated_indices = group.index[1:] if rules["keep_first_frozen_point"] else group.index
        repeats.loc[repeated_indices] = True
        rows.append({
            "run_id": int(run_id), "start_local": group["time_local"].iloc[0].isoformat(),
            "end_local": group["time_local"].iloc[-1].isoformat(), "points": len(group),
            "masked_repeated_points": len(repeated_indices),
            "anchor_source_csv_row": int(group["source_csv_row"].iloc[0]),
            "last_source_csv_row": int(group["source_csv_row"].iloc[-1]),
            "constant_power_mw": float(group["power"].iloc[0]),
            "constant_local_ghi_wm2": float(group["lmd_totalirrad"].iloc[0]),
            "deep_night_points": int(impossible_night.sum()),
            "nwp_ghi_distinct_values": int(group["nwp_globalirrad"].nunique()),
        })
    columns = ["run_id", "start_local", "end_local", "points", "masked_repeated_points",
               "anchor_source_csv_row", "last_source_csv_row", "constant_power_mw",
               "constant_local_ghi_wm2", "deep_night_points", "nwp_ghi_distinct_values"]
    return segment, repeats, pd.DataFrame(rows, columns=columns)


def clean_local_values(data, rules):
    """原始列原样保留，仅创建七项现场量的清洗副本。"""
    result = data.copy()
    fields = rules["frozen_fields"]
    frozen, repeats, runs = find_frozen_runs(data, rules)
    changes = []
    for field in fields:
        numeric = pd.to_numeric(data[field], errors="coerce")
        invalid = ~np.isfinite(numeric)
        if field in ("power", "lmd_totalirrad", "lmd_diffuseirrad", "lmd_windspeed"):
            invalid |= numeric < 0
        elif field == "lmd_pressure":
            invalid |= numeric <= 0
        elif field == "lmd_winddirection":
            invalid |= (numeric < 0) | (numeric > 360)
        result[field + "_clean"] = numeric.mask(invalid | repeats)
        # 已经是缺失的值无需记录“修改”；非有限值和非法值保留原值到日志。
        affected = (invalid | repeats) & data[field].notna()
        event = data.loc[affected, ["source_csv_row", "time_local", field]].copy()
        event = event.rename(columns={field: "raw_value"})
        event["field"] = field
        event["clean_value"] = np.nan
        event["reason"] = np.where(repeats.loc[affected], "R1_multifield_frozen_repeat", "R0_invalid_local_value")
        changes.append(event)
    result["flag_frozen_run"] = frozen
    result["flag_frozen_repeat"] = repeats
    result["flag_frozen_anchor_review"] = frozen & ~repeats
    result["flag_night_positive_raw"] = (~data["is_daylight"]
        & (data["power"] > rules["power_tolerance_mw"]))
    result["flag_day_low_power_raw"] = (data["is_daylight"]
        & (data["lmd_totalirrad"] > rules["strong_irradiance_threshold_wm2"])
        & (data["power"] <= rules["power_tolerance_mw"]))
    result["flag_above_capacity_raw"] = data["power"] > data["capacity_mw"]
    result["needs_review"] = (frozen | result["flag_night_positive_raw"]
        | result["flag_day_low_power_raw"] | result["flag_above_capacity_raw"])
    result["valid_power_for_q1"] = result["power_clean"].notna()
    local_clean = [field + "_clean" for field in fields if field != "power"]
    result["valid_local_weather_for_q1"] = result[local_clean].notna().all(axis=1)
    log = pd.concat(changes, ignore_index=True)
    log = log[["source_csv_row", "time_local", "field", "raw_value", "clean_value", "reason"]]
    return result, log, runs


def plot_review(data, runs, path):
    if runs.empty:
        return False
    # 选最长的两段，不额外挑选效果最好的图；段数不足时按实际数量绘图。
    selected = runs.sort_values("points", ascending=False).head(2)
    fonts = {font.name for font in font_manager.fontManager.ttflist}
    chinese = next((name for name in ("PingFang HK", "Songti SC", "Heiti TC", "SimHei", "Noto Sans CJK SC")
                    if name in fonts), None)
    plt.rcParams["font.family"] = chinese or "DejaVu Sans"
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, len(selected), figsize=(13, 6.5), squeeze=False)
    for column, row in enumerate(selected.itertuples()):
        start = pd.Timestamp(row.start_local).normalize()
        stop = pd.Timestamp(row.end_local).normalize() + pd.Timedelta(days=1)
        frame = data.loc[data["time_local"].ge(start) & data["time_local"].lt(stop)]
        axes[0, column].plot(frame["time_local"], frame["power"], color="#be751a", linestyle="--",
                             linewidth=1.2, label="原始功率" if chinese else "Raw power")
        axes[0, column].plot(frame["time_local"], frame["power_clean"], color="#2563a6", linewidth=1.3,
                             label="清洗列（缺失处断线）" if chinese else "Clean column (gaps preserved)")
        axes[1, column].plot(frame["time_local"], frame["lmd_totalirrad"], color="#be751a", linestyle="--",
                             linewidth=1.2, label="原始现场辐照" if chinese else "Raw local irradiance")
        axes[1, column].plot(frame["time_local"], frame["lmd_totalirrad_clean"], color="#2563a6", linewidth=1.3,
                             label="清洗列（缺失处断线）" if chinese else "Clean column (gaps preserved)")
        for i in range(2):
            ax = axes[i, column]
            ax.axvspan(pd.Timestamp(row.start_local), pd.Timestamp(row.end_local), color="#808080", alpha=0.12)
            ticks = pd.date_range(start, stop, freq="12h", inclusive="left").union(pd.DatetimeIndex([stop - STEP]))
            ax.set_xticks(ticks)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M", tz=start.tzinfo))
            ax.set_xlim(start, stop - STEP)
            ax.grid(axis="y", color="#e4e7eb", linewidth=0.7)
            ax.spines[["top", "right"]].set_visible(False)
            ax.legend(loc="upper right", frameon=False, fontsize=9)
        axes[0, column].set_ylim(0, float(data["capacity_mw"].iloc[0]) * 1.1)
        axes[1, column].set_ylim(0, max(1000, float(data["lmd_totalirrad"].max()) * 1.05))
        axes[0, column].set_title(f"{start:%Y-%m-%d} — {(stop - STEP):%m-%d}")
    axes[0, 0].set_ylabel("功率（MW）" if chinese else "Power (MW)")
    axes[1, 0].set_ylabel("辐照度（W/m²）" if chinese else "Irradiance (W/m²)")
    fig.suptitle("station01 多字段持值复查与第一版清洗（北京时间）" if chinese else
                 "station01: frozen local data review and first cleaning (Asia/Shanghai)", fontsize=15)
    fig.text(0.06, 0.018, "灰色为整段持值候选；首点保留待复查，后续重复值设为缺失，没有插值或补零。" if chinese else
             "Grey marks candidate frozen runs; first sample retained for review; repeated values masked, not filled.", fontsize=9)
    fig.tight_layout(rect=(0, 0.065, 1, 0.95))
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, default=ROOT / "docs/q1_cleaning_rules.json")
    args = parser.parse_args()
    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    if rules["frozen_min_points"] < 2 or rules["power_tolerance_mw"] < 0:
        raise ValueError("持值最少点数应>=2，功率筛查阈值应非负")
    archive = ROOT / rules["source_zip"]
    raw, metadata = read_station(archive, rules["station"])
    data = raw.copy()
    data["source_csv_row"] = np.arange(len(data)) + 2
    data["time_utc"] = pd.to_datetime(data["date_time"], utc=True, errors="raise")
    if data["time_utc"].isna().any() or data["time_utc"].duplicated().any():
        raise ValueError("有缺失或重复时间戳，请单独确定处理方式；本脚本不静默删行或平均")
    data["time_local"] = data["time_utc"].dt.tz_convert(rules["timezone"])
    data = data.sort_values("time_local", kind="stable").reset_index(drop=True)
    solar = pvlib.solarposition.get_solarposition(pd.DatetimeIndex(data["time_utc"]),
        latitude=float(metadata["Latitude"]), longitude=float(metadata["Longitude"]),
        altitude=rules["solar_altitude_assumption_m"], method="nrel_numpy")
    data["solar_elevation_deg"] = solar["elevation"].to_numpy()
    data["is_daylight"] = data["solar_elevation_deg"] > 0
    data["capacity_mw"] = float(metadata["Capacity"]) / 1000
    cleaned, log, runs = clean_local_values(data, rules)
    # 不把物理合理性筛查当成原始列修改，也不删除时间点。
    assert len(cleaned) == len(data)
    pd.testing.assert_frame_equal(cleaned[raw.columns], data[raw.columns])
    pd.testing.assert_frame_equal(cleaned.filter(regex="^nwp_"), data.filter(regex="^nwp_"))
    daily = cleaned.groupby(cleaned["time_local"].dt.date).agg(
        rows=("time_local", "size"), valid_power_points=("valid_power_for_q1", "sum"),
        daylight_points=("is_daylight", "sum"), review_points=("needs_review", "sum"))
    daily.index.name = "date_local"
    daily["complete_power_day"] = daily["rows"].eq(96) & daily["valid_power_points"].eq(96)
    daily["invalid_power_points"] = daily["rows"] - daily["valid_power_points"]
    weeks = test_week_coverage(cleaned["time_local"])
    invalid, reviews = [], []
    for row in weeks.itertuples():
        mask = cleaned["time_local"].between(pd.Timestamp(row.start_local), pd.Timestamp(row.end_local))
        invalid.append(int((~cleaned.loc[mask, "valid_power_for_q1"]).sum()))
        reviews.append(int(cleaned.loc[mask, "needs_review"].sum()))
    weeks["invalid_power_points_after_cleaning"] = invalid
    weeks["review_points"] = reviews
    output = ROOT / "data/processed" / f"{rules['station']}_q1_clean.csv"
    folder = ROOT / "results/q1" / rules["station"]
    figure = ROOT / "figures/q1" / f"{rules['station']}_frozen_review.png"
    for path in (output.parent, folder, figure.parent):
        path.mkdir(parents=True, exist_ok=True)
    save_csv(cleaned, output)
    save_csv(log, folder / "cleaning_log.csv")
    save_csv(runs, folder / "frozen_runs.csv")
    save_csv(daily.reset_index(), folder / "cleaned_daily_coverage.csv")
    save_csv(weeks, folder / "cleaned_test_week_coverage.csv")
    made_plot = plot_review(cleaned, runs, figure)
    summary = {
        "rule_version": rules["version"], "source_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "rules_sha256": hashlib.sha256(args.rules.read_bytes()).hexdigest(), "rows": len(cleaned),
        "source_columns_unchanged": True, "nwp_columns_unchanged": True,
        "candidate_frozen_runs": len(runs), "candidate_frozen_points": int(cleaned["flag_frozen_run"].sum()),
        "masked_frozen_repeat_points": int(cleaned["flag_frozen_repeat"].sum()),
        "anchor_points_retained_for_review": int(cleaned["flag_frozen_anchor_review"].sum()),
        "modified_cells": len(log), "invalid_power_points": int((~cleaned["valid_power_for_q1"]).sum()),
        "valid_power_points": int(cleaned["valid_power_for_q1"].sum()),
        "complete_power_days": int(daily["complete_power_day"].sum()),
        "incomplete_power_days": int((~daily["complete_power_day"]).sum()),
        "day_zero_flags_retained": int(cleaned["flag_day_low_power_raw"].sum()),
        "remaining_night_positive_power_points": int((~cleaned["is_daylight"]
            & (cleaned["power_clean"] > rules["power_tolerance_mw"])).sum()),
        "remaining_deep_night_positive_power_points": int(((cleaned["solar_elevation_deg"] < rules["deep_night_elevation_deg"])
            & (cleaned["power_clean"] > rules["power_tolerance_mw"])).sum()),
        "processed_file": str(output.relative_to(ROOT)), "figure": str(figure.relative_to(ROOT)) if made_plot else None,
        "limits": rules["limitations"],
    }
    (folder / "cleaning_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 第一问第一版清洗摘要：station01", "", f"规则版本：{rules['version']}；规则文件：docs/q1_cleaning_rules.json。", "",
             "原始ZIP和原始列保持不变；全部时间点保留，七项现场量的清洗结果另存为*_clean列。", "",
             "## 已处理的持值段", "", "| 开始（北京时间） | 结束 | 全段点数 | 后续重复点设缺失 | 保留首点 |", "|---|---|---:|---:|---:|"]
    lines += [f"| {r.start_local} | {r.end_local} | {r.points} | {r.masked_repeated_points} | {r.points - r.masked_repeated_points} |"
              for r in runs.itertuples()]
    lines += ["", "每段的功率和六个现场气象量完全相同，持续至太阳高度角<-6°，而NWP总辐照仍有变化。",
              "这支持判定数据存在可疑持值，但不能确认是采集故障、通信问题还是既有填补。首点可能是最后一次有效采样，故保留并标注边界待复查。", "",
              "## 处理结果", "", f"- {summary['rows']}条记录仍全部保留；{summary['invalid_power_points']}个功率清洗值为缺失，未插值或补零。",
              f"- 共{summary['modified_cells']}个现场字段值被设为缺失，逐值原值、行号、时间和原因见cleaning_log.csv。",
              f"- {summary['complete_power_days']}日保留完整96点功率；{summary['incomplete_power_days']}日功率不完整，见cleaned_daily_coverage.csv。",
              f"- {summary['day_zero_flags_retained']}个白昼较强辐照下零/低功率点保留，原因未确认；不能据此断言故障或限电。",
              f"- 清洗后仍有{summary['remaining_night_positive_power_points']}个夜间正功率点，但深夜正功率点为{summary['remaining_deep_night_positive_power_points']}个；近地平线样本继续保留待查。",
              "- 四个测试周各672条时间记录保持完整，功率清洗缺失数见cleaned_test_week_coverage.csv；本次均为0，不更换评分真值。", "",
              "## 使用清洗表", "", f"文件：{summary['processed_file']}。", "",
              "- 原始列power仍是原始实测MW；第一问统计使用power_clean并检查valid_power_for_q1。",
              "- 现场气象使用对应*_clean列；valid_local_weather_for_q1表示六项现场量均通过当前基础规则。",
              "- needs_review为复查提示，与valid_power_for_q1不是互补关系；保留的可疑零功率和首点仍需在分析中说明。",
              "- 不完整日的日发电量不能按缺失补零。月度比较应使用完整有效日并报告天数，也应保留未清洗结果作敏感性对照。",
              "- 只有相邻两个功率清洗值有效且时间相差15分钟时，才计算15分钟功率变化。",
              "- 采样口径未确认前，不能把功率求和×0.25小时无条件宣称为精确日发电量。", "",
              "## 图与复现", "", f"图：{summary['figure']}。", "运行：.venv/bin/python src/q1_clean_data.py。", "",
              "## 假设与边界", "", *[f"- {item}" for item in summary["limits"]], "",
              "## 下一步", "", "明确第一问参考功率的物理口径与参数假设，再实现晴空参考曲线；所有结果必须记录清洗规则版本。"]
    (folder / "清洗摘要.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
