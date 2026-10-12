"""第一问步骤3：计算明确假设下的晴空参考功率，保留DC和AC口径。"""

import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
import pvlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager

from q1_check_data import ROOT, STEP, read_station, save_csv


def reference_from_poa(poa, dc_capacity_w, ac_limit_w, efficiency, extra_loss=0):
    """固定组件温度25°C，直流输出线性随板面辐照变化；逆变器独立定义DC输入限制。"""
    if dc_capacity_w <= 0 or ac_limit_w <= 0 or not 0 < efficiency <= 1 or not 0 <= extra_loss < 1:
        raise ValueError("容量、额定效率及额外损耗参数不合法")
    pdc_w = np.maximum(np.asarray(poa, dtype=float), 0) / 1000 * dc_capacity_w * (1 - extra_loss)
    # inverter.pdc0是逆变器DC输入限制，不能直接拿组件额定DC容量代入。
    pac_w = pvlib.inverter.pvwatts(pdc_w, pdc0=ac_limit_w / efficiency, eta_inv_nom=efficiency)
    return pdc_w / 1e6, np.asarray(pac_w) / 1e6


def clear_sky_poa(times, metadata, assumptions, altitude):
    location = pvlib.location.Location(float(metadata["Latitude"]), float(metadata["Longitude"]),
                                      tz="Asia/Shanghai", altitude=altitude)
    solar = location.get_solarposition(times)
    radiation = location.get_clearsky(times, model=assumptions["clear_sky_model"], solar_position=solar)
    poa = pvlib.irradiance.get_total_irradiance(
        assumptions["tilt_deg"], assumptions["azimuth_deg"], solar["apparent_zenith"], solar["azimuth"],
        radiation["dni"], radiation["ghi"], radiation["dhi"], albedo=assumptions["albedo_assumed"],
        model=assumptions["transposition_model"])
    # 所有步骤统一几何太阳高度角>0为白昼；夜间参考置0，不改实测功率。
    daylight = solar["elevation"] > 0
    return solar, radiation, poa["poa_global"].where(daylight, 0).clip(lower=0)


def plot_day(table, assumptions, path):
    fonts = {font.name for font in font_manager.fontManager.ttflist}
    chinese = next((name for name in ("PingFang HK", "Songti SC", "Heiti TC", "SimHei", "Noto Sans CJK SC")
                    if name in fonts), None)
    plt.rcParams["font.family"] = chinese or "DejaVu Sans"
    plt.rcParams["axes.unicode_minus"] = False
    start = pd.Timestamp(assumptions["plot_day_local"], tz="Asia/Shanghai")
    end = start + pd.Timedelta(days=1) - STEP
    frame = table.loc[table["time_local"].between(start, end)]
    if len(frame) != 96:
        raise ValueError("固定诊断日应有96条时间记录")
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    axes[0].plot(frame["time_local"], frame["power_clean"], color="#2563a6", linewidth=1.8,
                 label="实际功率（清洗列）" if chinese else "Measured power (clean column)")
    for loss, color, style in [(0, "#555555", "--"), (10, "#be751a", ":"), (20, "#6d7947", "-.")]:
        axes[0].plot(frame["time_local"], frame[f"reference_ac_loss{loss}_mw"], color=color, linestyle=style,
                     linewidth=1.3, label=f"晴空参考，额外损耗{loss}%" if chinese else f"Clear-sky reference, extra loss {loss}%")
    axes[0].set_ylim(0, max(assumptions["ac_limit_mw_assumed"], frame["power_clean"].max()) * 1.08)
    axes[0].set_ylabel("功率（MW）" if chinese else "Power (MW)")
    axes[0].legend(frameon=False, ncol=2, fontsize=9)
    axes[1].plot(frame["time_local"], frame["deviation_actual_minus_reference_mw"], color="#2563a6", linewidth=1.5)
    axes[1].axhline(0, color="#555555", linewidth=1)
    axes[1].set_ylabel("实际－0%损耗参考（MW）" if chinese else "Actual minus 0%-loss reference (MW)")
    ticks = pd.date_range(start, end, freq="4h").union(pd.DatetimeIndex([end]))
    axes[1].set_xticks(ticks)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=start.tzinfo))
    axes[1].set_xlim(start, end)
    for ax in axes:
        ax.grid(axis="y", color="#e4e7eb", linewidth=0.7)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"station01 {start:%Y-%m-%d}：实际与假设工况晴空参考" if chinese else
                 f"station01 {start:%Y-%m-%d}: actual vs assumed clear-sky reference", fontsize=14)
    fig.text(0.08, 0.018, "北京时间；固定组件温度25°C、假设交流限制20MW；固定诊断日，不代表全年；参考不是严格上限。" if chinese else
             "Asia/Shanghai; fixed cell temperature 25°C; assumed AC limit 20 MW; diagnostic day, not a strict upper bound.", fontsize=9)
    fig.tight_layout(rect=(0, 0.055, 1, 0.95))
    fig.savefig(path, dpi=300)
    plt.close(fig)


def main():
    config_path = ROOT / "docs/q1_reference_assumptions.json"
    assumptions = json.loads(config_path.read_text())
    archive = ROOT / "docs/PVODdatasets_v1.0.zip"
    _, metadata = read_station(archive, assumptions["station"])
    match = re.search(r"Pmax:\s*([\d.]+)\s*Wp", metadata["Module"])
    if not match:
        raise ValueError("无法从组件信息读取Pmax，不猜测额定功率")
    panel_w = float(match.group(1))
    dc_w = int(metadata["Panel_Number"]) * panel_w
    source = ROOT / "data/processed/station01_q1_clean.csv"
    cleaned = pd.read_csv(source)
    times = pd.DatetimeIndex(pd.to_datetime(cleaned["time_utc"], utc=True))
    if times.hasnans or not times.is_unique:
        raise ValueError("清洗数据时间必须有效且唯一")
    solar, radiation, poa = clear_sky_poa(times, metadata, assumptions, assumptions["altitude_m_assumed"])
    table = cleaned[["source_csv_row", "power_clean", "valid_power_for_q1", "needs_review"]].copy()
    table["time_utc"] = times
    table["time_local"] = times.tz_convert("Asia/Shanghai")
    table["solar_elevation_deg"] = solar["elevation"].to_numpy()
    table["is_daylight"] = table["solar_elevation_deg"] > 0
    for column in ("ghi", "dni", "dhi"):
        table[f"clear_sky_{column}_wm2"] = radiation[column].to_numpy()
    table["clear_sky_poa_wm2"] = poa.to_numpy()
    for loss in assumptions["extra_loss_fraction_scenarios"]:
        pdc, pac = reference_from_poa(poa, dc_w, assumptions["ac_limit_mw_assumed"] * 1e6,
                                     assumptions["inverter_nominal_efficiency_assumed"], loss)
        suffix = f"loss{round(loss * 100)}_mw"
        table["reference_dc_" + suffix] = pdc
        table["reference_ac_" + suffix] = pac
    _, _, high_poa = clear_sky_poa(times, metadata, assumptions, assumptions["altitude_sensitivity_m_assumed"])
    _, high_ac = reference_from_poa(high_poa, dc_w, assumptions["ac_limit_mw_assumed"] * 1e6,
                                    assumptions["inverter_nominal_efficiency_assumed"])
    table["reference_ac_altitude200_loss0_mw"] = high_ac
    table["deviation_actual_minus_reference_mw"] = table["power_clean"] - table["reference_ac_loss0_mw"]
    reference_columns = list(table.filter(regex="^reference_ac_").columns)
    assert np.isfinite(table[reference_columns].to_numpy()).all()
    assert (table[reference_columns] >= 0).all().all()
    assert (table[reference_columns] <= assumptions["ac_limit_mw_assumed"] + 1e-10).all().all()
    assert table.loc[~table["is_daylight"], "reference_ac_loss0_mw"].eq(0).all()
    assert (table["reference_ac_loss0_mw"] >= table["reference_ac_loss10_mw"] - 1e-10).all()
    assert (table["reference_ac_loss10_mw"] >= table["reference_ac_loss20_mw"] - 1e-10).all()
    folder = ROOT / "results/q1/station01"
    save_csv(table, folder / "reference_power.csv")
    common = table.loc[table["is_daylight"] & table["valid_power_for_q1"]]
    rows = []
    for column in reference_columns:
        delta = common["power_clean"] - common[column]
        rows.append({"scenario": column, "common_daylight_points": len(common),
                     "reference_peak_mw": float(table[column].max()),
                     "mean_actual_minus_reference_mw": float(delta.mean()),
                     "mae_to_reference_mw": float(delta.abs().mean()),
                     "actual_exceeds_reference_points": int(delta.gt(0).sum())})
    save_csv(pd.DataFrame(rows), folder / "reference_sensitivity.csv")
    summary = {"model_version": assumptions["version"], "assumptions": assumptions,
               "cleaned_data_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "source_zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
               "assumptions_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
               "pvlib_version": pvlib.__version__, "rows": len(table),
               "panel_number": int(metadata["Panel_Number"]), "panel_pmax_wp": panel_w,
               "derived_dc_capacity_mwp": dc_w / 1e6, "assumed_ac_limit_mw": assumptions["ac_limit_mw_assumed"],
               "common_daylight_points": len(common), "scenarios": rows,
               "comparison_is_forecast_evaluation": False,
               "no_parameters_fitted_from_power": True}
    (folder / "reference_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_day(table, assumptions, ROOT / "figures/q1/station01_reference_day.png")
    print(json.dumps({key: summary[key] for key in ("model_version", "rows", "derived_dc_capacity_mwp", "scenarios")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
