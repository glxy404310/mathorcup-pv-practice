"""第一问第一个步骤：读取原始ZIP，检查station01并保存诊断结果。

不填补、不删行、不裁剪功率；可疑值仅作标记。运行方法见README.md。
"""

import argparse
import calendar
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import zipfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import pvlib


ROOT = Path(__file__).resolve().parents[1]
LOCAL_TZ = "Asia/Shanghai"
STEP = pd.Timedelta(minutes=15)
UNITS = {
    "power": "MW",
    "nwp_globalirrad": "W/m²", "nwp_directirrad": "W/m²",
    "nwp_temperature": "°C", "nwp_humidity": "%",
    "nwp_windspeed": "m/s", "nwp_winddirection": "degree", "nwp_pressure": "hPa",
    "lmd_totalirrad": "W/m²", "lmd_diffuseirrad": "W/m²",
    "lmd_temperature": "°C", "lmd_pressure": "hPa",
    "lmd_winddirection": "degree", "lmd_windspeed": "m/s",
}
FLAG_LABELS = {
    "duplicate_timestamp": "重复时间戳",
    "missing_or_invalid_numeric": "数值缺失、解析失败或无穷值",
    "power_negative": "负功率",
    "power_above_installed_capacity": "功率超过装机容量",
    "night_positive_power": "夜间功率超过筛查阈值",
    "deep_night_positive_power": "太阳高度角低于-6°时功率超过筛查阈值",
    "irradiance_negative": "负辐照",
    "humidity_outside_0_100": "NWP湿度不在0—100%",
    "windspeed_negative": "负风速",
    "day_low_power_with_irradiance": "白昼较强辐照下功率接近零",
}


def save_csv(frame, path):
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def read_station(archive, station):
    archive = Path(archive)
    if archive.is_dir():
        metadata = pd.read_csv(archive / "metadata.csv")
        raw = pd.read_csv(archive / f"{station}.csv")
    else:
        with zipfile.ZipFile(archive) as bundle:
            with bundle.open("metadata.csv") as stream:
                metadata = pd.read_csv(stream)
            with bundle.open(f"{station}.csv") as stream:
                raw = pd.read_csv(stream)
    selected = metadata.loc[metadata["Station_ID"].eq(station)]
    if len(selected) != 1:
        raise ValueError(f"元数据中应恰好有一条{station}记录")
    missing = {"date_time", *UNITS} - set(raw.columns)
    if missing:
        raise ValueError(f"缺少必需字段：{sorted(missing)}")
    if raw.empty:
        raise ValueError("站点数据为空")
    return raw, selected.iloc[0]


def source_sha256(source, station):
    """ZIP按原口径哈希；目录按元数据和站点CSV的命名及字节哈希。"""
    source = Path(source)
    if source.is_file():
        return hashlib.sha256(source.read_bytes()).hexdigest()
    digest = hashlib.sha256()
    for name in ("metadata.csv", f"{station}.csv"):
        digest.update(name.encode())
        digest.update(hashlib.sha256((source / name).read_bytes()).digest())
    return digest.hexdigest()


def check_fields(raw):
    rows = []
    numeric = pd.DataFrame(index=raw.index)
    for column in raw.columns:
        record = {"field": column, "raw_dtype": str(raw[column].dtype),
                  "missing_count": int(raw[column].isna().sum()),
                  "missing_fraction": float(raw[column].isna().mean()),
                  "unit": UNITS.get(column, "UTC timestamp")}
        if column != "date_time":
            values = pd.to_numeric(raw[column], errors="coerce")
            record["parse_failure_count"] = int((raw[column].notna() & values.isna()).sum())
            record["infinite_count"] = int(np.isinf(values).sum())
            finite = values.where(np.isfinite(values))
            record.update({"min": finite.min(), "median": finite.median(),
                           "p99": finite.quantile(0.99), "max": finite.max()})
            numeric[column] = finite
        rows.append(record)
    return pd.DataFrame(rows), numeric


def test_week_coverage(times):
    unique = pd.DatetimeIndex(times).unique().sort_values()
    rows = []
    for year in range(unique.min().year, unique.max().year + 1):
        for month in (2, 5, 8, 11):
            last = calendar.monthrange(year, month)[1]
            start = pd.Timestamp(year=year, month=month, day=last - 6, tz=LOCAL_TZ)
            stop = pd.Timestamp(year=year, month=month, day=last, tz=LOCAL_TZ) + pd.Timedelta(days=1)
            if start > unique.max() or stop <= unique.min():
                continue
            expected = pd.date_range(start, stop, freq="15min", inclusive="left")
            observed = unique[(unique >= start) & (unique < stop)]
            rows.append({"start_local": start.isoformat(),
                         "end_local": (stop - STEP).isoformat(),
                         "expected_points": len(expected), "observed_unique_points": len(observed),
                         "missing_points": len(expected.difference(observed)),
                         "complete_time_grid": expected.equals(observed)})
    return pd.DataFrame(rows, columns=["start_local", "end_local", "expected_points",
                                      "observed_unique_points", "missing_points", "complete_time_grid"])


def make_plot(data, start, days, capacity, station, path):
    stop = start + pd.Timedelta(days=days)
    frame = data.loc[data["time_local"].ge(start) & data["time_local"].lt(stop)].copy()
    if frame.empty:
        raise ValueError("指定出图窗口没有数据，请调整--plot-start")
    # 重复时间戳不能在诊断图中被静默平均；时间缺口使用NaN断开折线。
    if frame["time_local"].duplicated().any():
        raise ValueError("出图窗口有重复时间戳，请先依据检查结果确定处理规则")
    index = pd.date_range(start, stop, freq="15min", inclusive="left")
    frame = frame.set_index("time_local").reindex(index)
    fonts = {font.name for font in font_manager.fontManager.ttflist}
    chinese = next((name for name in ("PingFang HK", "Songti SC", "Heiti TC", "SimHei", "Noto Sans CJK SC")
                    if name in fonts), None)
    plt.rcParams["font.family"] = chinese or "DejaVu Sans"
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 1, figsize=(13, 6.5), sharex=True)
    if chinese:
        power_label, ghi_label = "实测功率（MW）", "辐照度（W/m²）"
        title = f"{station} 连续{days}天数据检查（北京时间）"
        labels = ["实测功率", "装机容量（口径待确认）", "现场总辐照", "NWP总辐照"]
        note = "原始值未清洗；NWP发布时间未确认，仅作数据检查；固定窗口不代表全年。"
    else:
        power_label, ghi_label = "Measured power (MW)", "Irradiance (W/m²)"
        title = f"{station}: {days}-day data check (Asia/Shanghai)"
        labels = ["Measured power", "Installed capacity (basis unconfirmed)", "Local irradiance", "NWP irradiance"]
        note = "Uncleaned values; NWP release time unconfirmed; fixed window, not representative of the year."
    axes[0].plot(index, frame["power"], color="#2563a6", linewidth=1.1, label=labels[0])
    axes[0].axhline(capacity, color="#555555", linestyle="--", linewidth=1, label=labels[1])
    axes[0].set_ylim(min(0, frame["power"].min()), max(capacity, frame["power"].max()) * 1.08)
    axes[0].set_ylabel(power_label)
    axes[1].plot(index, frame["lmd_totalirrad"], color="#2563a6", linewidth=1.1, label=labels[2])
    axes[1].plot(index, frame["nwp_globalirrad"], color="#be751a", linestyle="--", linewidth=1, label=labels[3])
    axes[1].set_ylabel(ghi_label)
    axes[1].set_ylim(bottom=min(0, frame[["lmd_totalirrad", "nwp_globalirrad"]].min().min()))
    ticks = pd.date_range(start, stop - pd.Timedelta(days=1), freq="1D").union(pd.DatetimeIndex([stop - STEP]))
    axes[1].set_xticks(ticks)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M", tz=start.tzinfo))
    axes[1].set_xlim(start, stop - STEP)
    for ax in axes:
        ax.legend(loc="upper right", frameon=False, ncol=2)
        ax.grid(axis="y", color="#e4e7eb", linewidth=0.7)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title, fontsize=15)
    fig.text(0.08, 0.015, note, fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.055, 1, 0.96))
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return {"start_local": start.isoformat(), "end_local": (stop - STEP).isoformat(),
            "observed_rows": int((data["time_local"].ge(start) & data["time_local"].lt(stop)).sum()),
            "selection_reason": "固定诊断窗口；默认选第一个测试周，不声称具有全年代表性"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default="station01")
    parser.add_argument("--source", "--zip", dest="zip", type=Path, default=ROOT / "docs/PVODdatasets_v1.0.zip")
    parser.add_argument("--plot-start", default="2018-08-25", help="北京时间日期")
    parser.add_argument("--plot-days", type=int, default=7)
    parser.add_argument("--power-tolerance", type=float, default=0.01, help="筛查阈值MW，不是删除规则")
    args = parser.parse_args()
    if args.plot_days <= 0 or args.power_tolerance < 0:
        parser.error("出图天数应为正数，功率筛查阈值不得小于0")
    if not args.station.startswith("station") or not args.station[7:].isdigit():
        parser.error("站点编号应形如station01")
    raw, metadata = read_station(args.zip, args.station)
    profile, data = check_fields(raw)
    times = pd.to_datetime(raw["date_time"], utc=True, errors="coerce")
    if times.isna().any():
        raise ValueError(f"存在{times.isna().sum()}条不能解析的时间；未静默丢弃，请先检查原文件")
    data["source_csv_row"] = np.arange(len(raw)) + 2
    data["time_utc"] = times
    data["time_local"] = times.dt.tz_convert(LOCAL_TZ)
    data = data.sort_values("time_local", kind="stable").reset_index(drop=True)
    capacity = float(metadata["Capacity"]) / 1000
    if not np.isfinite(capacity) or capacity <= 0:
        raise ValueError("装机容量必须为正有限数")
    unique = pd.DatetimeIndex(data["time_local"]).unique().sort_values()
    expected = pd.date_range(unique.min(), unique.max(), freq="15min")
    # 地理信息用于昼夜筛查。海拔缺失，暂设0m；采用几何太阳高度角，不计算参考功率。
    solar = pvlib.solarposition.get_solarposition(
        pd.DatetimeIndex(data["time_utc"]), latitude=float(metadata["Latitude"]),
        longitude=float(metadata["Longitude"]), altitude=0, method="nrel_numpy")
    data["solar_elevation_deg"] = solar["elevation"].to_numpy()
    data["is_daylight"] = data["solar_elevation_deg"] > 0
    flags = {
        "duplicate_timestamp": data["time_local"].duplicated(keep=False),
        "missing_or_invalid_numeric": data[list(UNITS)].isna().any(axis=1),
        "power_negative": data["power"] < 0,
        "power_above_installed_capacity": data["power"] > capacity,
        "night_positive_power": ~data["is_daylight"] & (data["power"] > args.power_tolerance),
        "deep_night_positive_power": (data["solar_elevation_deg"] < -6) & (data["power"] > args.power_tolerance),
        "irradiance_negative": (data[["lmd_totalirrad", "lmd_diffuseirrad", "nwp_globalirrad", "nwp_directirrad"]] < 0).any(axis=1),
        "humidity_outside_0_100": (data["nwp_humidity"] < 0) | (data["nwp_humidity"] > 100),
        "windspeed_negative": (data[["nwp_windspeed", "lmd_windspeed"]] < 0).any(axis=1),
        "day_low_power_with_irradiance": data["is_daylight"] & (data["lmd_totalirrad"] > 200) & (data["power"] <= args.power_tolerance),
    }
    flag_frame = pd.DataFrame(flags)
    flagged = pd.concat([data, flag_frame], axis=1).loc[flag_frame.any(axis=1)]
    weeks = test_week_coverage(data["time_local"])
    daily = data.groupby(data["time_local"].dt.date).agg(rows=("time_local", "size"), unique_times=("time_local", "nunique"))
    daily.index.name = "date_local"
    gaps = pd.DataFrame({"missing_time_local": expected.difference(unique)})
    intervals = pd.Series(unique[1:] - unique[:-1]).value_counts().sort_index()
    interval_frame = pd.DataFrame({"interval_minutes": intervals.index.total_seconds() / 60, "count": intervals.to_numpy()})
    folder = ROOT / "results/q1" / args.station
    figures = ROOT / "figures/q1"
    folder.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(args.plot_start)
    start = start.tz_localize(LOCAL_TZ) if start.tzinfo is None else start.tz_convert(LOCAL_TZ)
    figure = figures / f"{args.station}_week.png"
    plot_info = make_plot(data, start, args.plot_days, capacity, args.station, figure)
    for frame, name in [(profile, "field_profile.csv"), (flagged, "flagged_rows.csv"),
                        (weeks, "test_week_coverage.csv"), (gaps, "missing_timestamps.csv"),
                        (interval_frame, "interval_counts.csv"), (daily.reset_index(), "daily_coverage.csv"),
                        (data.head(8), "preview.csv")]:
        save_csv(frame, folder / name)
    summary = {
        "station": args.station, "source": str(args.zip.resolve()),
        "source_sha256": source_sha256(args.zip, args.station),
        "source_columns": list(raw.columns), "rows": len(data), "unique_timestamps": len(unique),
        "source_sorted": bool(times.is_monotonic_increasing),
        "duplicate_extra_rows": int(data["time_local"].duplicated().sum()),
        "off_grid_unique_timestamps": len(unique.difference(expected)),
        "missing_timestamps": len(gaps), "start_utc": times.min().isoformat(), "end_utc": times.max().isoformat(),
        "start_local": unique.min().isoformat(), "end_local": unique.max().isoformat(),
        "observed_days": len(daily), "complete_96_point_days": int(daily["unique_times"].eq(96).sum()),
        "capacity_mw": capacity, "power_min_mw": float(data["power"].min()), "power_max_mw": float(data["power"].max()),
        "daylight_rows": int(data["is_daylight"].sum()), "night_rows": int((~data["is_daylight"]).sum()),
        "flag_counts": {name: int(mask.sum()) for name, mask in flags.items()},
        "flag_fractions": {name: float(mask.mean()) for name, mask in flags.items()},
        "flagged_unique_rows": len(flagged), "power_tolerance_mw": args.power_tolerance,
        "daylight_rule": "几何太阳高度角>0；pvlib nrel_numpy；海拔暂设0m，仅作昼夜筛查",
        "plot": plot_info, "figure": str(figure.relative_to(ROOT)),
        "versions": {"python": platform.python_version(), **{name: importlib.metadata.version(name)
                     for name in ("pandas", "numpy", "matplotlib", "pvlib")}},
        "limitations": ["未覆盖完整一年", "仅标记可疑值，未清洗或确认异常原因", "海拔、AC/DC和功率采样口径待确认",
                        "NWP发布时间待确认，不能以同时间行对齐证明日前可用", "未计算理论参考功率或预测指标"],
    }
    (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# 第一问数据检查：{args.station}", "",
             "本报告由src/q1_check_data.py生成。原始数据不修改；本次只检查和标记，不填补、不删行。", "",
             f"- 输入：{args.zip}中的{args.station}.csv及metadata.csv。",
             f"- 时间：{summary['start_local']}至{summary['end_local']}，北京时间。",
             f"- {len(data)}条记录，{len(unique)}个唯一时间戳；重复多余行{summary['duplicate_extra_rows']}条，缺失时间点{len(gaps)}个。",
             f"- 覆盖{len(daily)}日，其中{summary['complete_96_point_days']}日有96个唯一时间点。",
             f"- 功率范围{summary['power_min_mw']:.6f}至{summary['power_max_mw']:.6f} MW；装机容量{capacity:g} MW（AC/DC口径待确认）。",
             "- 字段缺失、解析失败、无穷值和分位数见field_profile.csv。", "",
             "## 筛查标记", "", "各标记可能重叠，不能直接相加；标记不等于已经确认的异常。", "",
             "| 标记 | 点数 | 占全部记录比例 |", "|---|---:|---:|"]
    lines += [f"| {FLAG_LABELS[name]}（{name}） | {count} | {count / len(data):.2%} |"
              for name, count in summary["flag_counts"].items()]
    lines += ["", "## 优先复查的日期", "",
              "下表列出两类主要标记的日期及点数。记录存在的置信度高，具体原因未确认；严重程度应结合原始曲线判断。", "",
              "| 日期（北京时间） | 夜间正功率点数 | 白昼较强辐照下低功率点数 |", "|---|---:|---:|"]
    dates = data["time_local"].dt.date
    review_days = flag_frame[["night_positive_power", "day_low_power_with_irradiance"]].groupby(dates).sum()
    review_days = review_days.loc[review_days.sum(axis=1) > 0]
    lines += [f"| {day} | {int(row.iloc[0])} | {int(row.iloc[1])} |" for day, row in review_days.iterrows()]
    deep = data.loc[flags["deep_night_positive_power"]]
    if not deep.empty:
        lines += ["", f"太阳高度角低于-6°的可疑点功率范围为{deep['power'].min():.6f}至{deep['power'].max():.6f} MW。",
                  "高夜间功率可能影响月度统计和实际/参考偏差，应优先排查重复持值、采集异常或时间口径；不依据曲线直接认定原因。"]
    lines += ["", "## 规则与解释边界", "",
              f"- 夜间：几何太阳高度角≤0；深夜筛查：高度角<-6°；正功率筛查阈值{args.power_tolerance:g} MW。海拔暂设0m。",
              "- 夜间非零可能涉及测量偏置、数据处理、时间口径等，现有数据不能唯一确定原因；不要直接归零。",
              "- day_low_power_with_irradiance：白昼现场总辐照>200 W/m²且功率≤筛查阈值；只定位待查时段，不断言故障或限电。",
              "- power_above_installed_capacity：超过元数据装机容量，需核实容量口径后再决定是否处理。",
              "- flagged_rows.csv保留原始CSV行号（含表头，从2开始），便于追溯。",
              "- 四个测试月按本地日历月末7天检查，结果见test_week_coverage.csv；跨年练习不满足完整一年要求。", "",
              "## 连续一周图", "",
              f"窗口：{plot_info['start_local']}至{plot_info['end_local']}；{plot_info['selection_reason']}。",
              f"图：{summary['figure']}。上图功率，下图现场与NWP总辐照；NWP只作数据诊断，不作预测有效性证明。", "",
              "## 下一步", "",
              "先核查flagged_rows.csv中夜间非零等可疑值，再与A确定清洗规则；补齐参考功率所需参数与明确假设。",
              "每一步的处理原因和修改点应另存记录，不能覆盖原始数据。", "",
              "## 尚未确认", "", *[f"- {item}" for item in summary["limitations"]]]
    (folder / "检查摘要.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"station": args.station, "rows": len(data), "flags": summary["flag_counts"],
                      "summary": str(folder / "检查摘要.md"), "figure": str(figure)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
