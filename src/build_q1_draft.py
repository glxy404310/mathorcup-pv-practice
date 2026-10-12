"""用已落盘结果生成第一问审阅稿与数字索引，更新论文骨架的第一问章节。"""

import hashlib
import json

import pandas as pd

from q1_check_data import ROOT, save_csv


FOLDER = ROOT / "results/q1/station01"


def load_json(name):
    return json.loads((FOLDER / name).read_text(encoding="utf-8"))


def main():
    audit = load_json("summary.json")
    cleaning = load_json("cleaning_summary.json")
    reference = load_json("reference_summary.json")
    characteristics = load_json("characteristics_summary.json")
    rule_path = ROOT / "docs/q1_cleaning_rules.json"
    if hashlib.sha256(rule_path.read_bytes()).hexdigest() != cleaning["rules_sha256"]:
        raise ValueError("清洗规则已修改但清洗结果尚未重跑")
    rules = json.loads(rule_path.read_text(encoding="utf-8"))
    (FOLDER / "q1_cleaning_rules_snapshot.json").write_bytes(rule_path.read_bytes())
    paths = {"cleaned_data_sha256": ROOT / "data/processed/station01_q1_clean.csv",
             "reference_data_sha256": FOLDER / "reference_power.csv"}
    for key, path in paths.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != characteristics[key]:
            raise ValueError("分析结果与当前数据版本不一致，请先重跑前置步骤")
    if audit["source_sha256"] != cleaning["source_sha256"] or cleaning["source_sha256"] != reference["source_zip_sha256"]:
        raise ValueError("检查、清洗和参考模型引用的原始数据不一致")
    if hashlib.sha256((ROOT / "docs/q1_reference_assumptions.json").read_bytes()).hexdigest() != reference["assumptions_sha256"]:
        raise ValueError("参考假设已修改但模型尚未重跑")
    monthly = pd.read_csv(FOLDER / "monthly_characteristics.csv")
    seasonal = pd.read_csv(FOLDER / "seasonal_characteristics.csv").set_index("season")
    deviations = pd.read_csv(FOLDER / "monthly_daylight_deviation.csv")
    sensitivity = pd.read_csv(FOLDER / "reference_sensitivity.csv")
    events = pd.read_csv(FOLDER / "zero_power_daylight_events.csv")
    frozen = pd.read_csv(FOLDER / "frozen_runs.csv")
    baseline = reference["scenarios"][0]
    h, low = characteristics["monthly_highest"], characteristics["monthly_lowest"]
    actual_high = monthly.loc[monthly["mean_daily_integral_estimate_mwh"].idxmax()]
    actual_low = monthly.loc[monthly["mean_daily_integral_estimate_mwh"].idxmin()]
    if actual_high.year_month != h["year_month"] or actual_low.year_month != low["year_month"]:
        raise ValueError("月度表与摘要排名不一致，先重跑特性分析")
    if int(deviations["points"].sum()) != baseline["common_daylight_points"]:
        raise ValueError("月度偏差表与参考摘要样本数不一致")
    season_names = {"spring": "春季", "summer": "夏季（跨年、不完整）", "autumn": "秋季", "winter": "冬季"}
    sensitivity_names = {"reference_ac_loss0_mw": "海拔0m，额外损耗0%（基准）",
                         "reference_ac_loss10_mw": "海拔0m，额外损耗10%",
                         "reference_ac_loss20_mw": "海拔0m，额外损耗20%",
                         "reference_ac_altitude200_loss0_mw": "海拔200m，额外损耗0%"}
    lines = ["## 4 问题1：参考功率与时序特性", "",
             "> 本节为第一版审阅稿。所有统计来自本项目实际运行结果；真实测量口径和设备参数尚不完整，以下结论限定于当前观测、清洗规则及明确假设。第一问仍待A、C复核后定稿。", "",
             "### 4.1 数据与分析口径", "",
             f"选取PVOD v1.0的station01电站进行分析[Q1-1]。数据按UTC解析并转换为北京时间，覆盖2018年7月1日至2019年6月13日，共{audit['observed_days']}个观测日、{audit['rows']:,}条记录，采样间隔为15分钟。时间戳连续且唯一，原始功率列单位为MW。该站没有覆盖完整一年，因此本节属于现有观测时段的特性分析。",
             "",
             "在质量复查中，两段功率及六项现场气象量逐点相同的记录持续至深夜，而同期NWP仍在变化。对此保留原始列及每段首点，将后续重复点的现场清洗值设为缺失，未插值或补零。具体段边界和逐值处理原因均保留，数据异常的真实采集或填补原因尚不能确认。", "",
             f"清洗版本为{cleaning['rule_version']}。持值候选要求至少{rules['frozen_min_points']}个连续15分钟点、七项现场量完全相同，且段内包含太阳高度角低于{rules['deep_night_elevation_deg']}°、功率大于{rules['power_tolerance_mw']:g} MW、总辐照为正的样本。保留每段首点是“可能为最后一次有效采样”的工作假设，不表示首点已获独立验证。白昼低功率复查阈值为现场总辐照大于{rules['strong_irradiance_threshold_wm2']} W/m²且功率不大于{rules['power_tolerance_mw']:g} MW；这类点只标记。", "",
             f"第一版清洗产生{cleaning['invalid_power_points']}个功率缺失值，保留{cleaning['complete_power_days']}个完整功率日用于月度和平均日内分析。完整日要求北京时间当天的96个15分钟时间点全部存在且功率清洗值有效。另有{cleaning['day_zero_flags_retained']}个白昼有较强辐照却功率接近零的点，以及{cleaning['remaining_night_positive_power_points']}个近地平线夜间小正功率点被保留并标记；缺少运维及测量状态资料时，不将它们直接判为故障或删除。",
             "",
             "功率是瞬时样本还是区间平均值、时间戳对应区间头还是尾，当前均未确认。本节采用矩形积分近似：", "",
             r"$$\widetilde E_d=0.25\sum_{k=1}^{96}P^{\mathrm{clean}}_{d,k}\quad(\mathrm{MWh}).$$", "",
             "这里的日积分是发电量估计。只有在功率为对应15分钟区间均值且区间归属正确时，上式才可直接解释为日发电量；若为瞬时样本，则是数值积分近似。不完整日不补零，也不进入月度完整日均值。每月实际和参考使用同一批完整日，避免样本集合不同造成比较偏差。",
             "",
             "白昼统一定义为几何太阳高度角大于0。偏差统计使用实际与参考均有效的白昼点；15分钟变化进一步要求两个端点均有效、均在白昼且时间差恰为15分钟。这些样本集合与完整日集合不同，以下分别报告数量。",
             "",
             "结果依据：`summary.json`、`cleaning_summary.json`、`frozen_runs.csv`、`cleaning_log.csv`、`daily_characteristics.csv`。", "",
             "### 4.2 晴空参考功率模型", "",
             "依据站点经纬度计算太阳位置，再采用Ineichen晴空模型生成GHI、DNI及DHI[Q1-2]。结合组件朝向和倾角，以各向同性散射模型计算板面总辐照[Q1-3]。站点坐标、组件配置和倾角来自metadata.csv，其他暂缺参数按表4-1明示假设，不利用实际功率拟合。", "",
             "表4-1 参考模型参数及来源", "",
             "| 项目 | 第一版取值 | 属性与依据 |", "|---|---|---|",
             "| 经度、纬度 | 117.45722°E、38.18306°N | station01元数据 |",
             "| 倾角、方位角 | 33°、180°（朝南） | 元数据South 33°；正北0°顺时针方位约定 |",
             f"| 组件数、单组件Pmax | {reference['panel_number']}块、{reference['panel_pmax_wp']:g} Wp | 元数据Panel_Number及Module |",
             f"| 组件额定直流容量 | {reference['derived_dc_capacity_mwp']:.2f} MWp | 组件数与Pmax相乘，非已核实交流容量 |",
             "| 海拔 | 基准0m，敏感性200m | 均为假设，不是实测海拔 |",
             "| 组件温度 | 固定25°C | 参考工况；现场气温不是组件温度 |",
             "| 交流功率限制 | 暂设20 MW | 实测输出及装机容量的AC/DC口径尚未核实 |",
             "| 逆变器额定效率 | 0.96 | 通用PVWatts模型默认假设，非站点逆变器实测值 |",
             "| 散射、地面反射 | isotropic、反射率0.25 | 通用参考条件；未核实地表和积雪变化 |",
             "| 额外损耗 | 基准0%，另设10%、20% | 只作敏感性情景，不认定为真实损耗 |", "",
             "固定组件温度为参考温度时，采用简化的辐照比例功率关系[Q1-4]：", "",
             r"$$P_{\mathrm{dc,ref}}(t)=19.98\frac{G_{\mathrm{poa}}(t)}{1000}(1-L)\quad(\mathrm{MW}),$$", "",
             r"其中板面辐照$G_{\mathrm{poa}}$的单位为W/m²，$L$为额外损耗率。该关系把板面辐照近似作为有效辐照，未加入入射角、光谱和遮挡细节。随后使用PVWatts逆变器模型，将直流功率映射为参考交流功率，并限制于假设的交流容量[Q1-5]。逆变器DC输入限制采用交流限制除以额定效率，与组件额定直流容量分开定义，避免混用。额外损耗和逆变器损耗也分别计算。",
             "",
             "基准定义为海拔0m、额外损耗0%的晴空参考，夜间参考功率置0。所有实测与参考按同一时间戳作点值对齐。由于实测AC/DC及区间口径仍待确认，这是一种工作假设下的近似比较，不能声称已完成真实设备口径核验。参考曲线既不是任何天气下的严格发电上限，也不是未来功率预测。",
             "",
             "结果依据：`reference_summary.json`、`reference_power.csv`；参数详见`docs/q1_reference_assumptions.json`。", "",
             "### 4.3 月度变化与平均日内形状", "",
             "表4-2列出各月完整日的日积分估计均值。图4-1同时显示实际均值、不同日期的P10—P90范围及同日参考均值，范围反映样本日期之间的分布，不是置信区间。", "",
             "表4-2 各月完整日的日积分估计", "",
             "| 月份 | 观测日 | 完整功率日 | 实际日积分估计均值（MWh） | 同日参考均值（MWh） |",
             "|---|---:|---:|---:|---:|"]
    lines += [f"| {r.year_month} | {r.observed_days} | {r.complete_power_days} | {r.mean_daily_integral_estimate_mwh:.2f} | {r.reference_mean_daily_integral_same_days_mwh:.2f} |" for r in monthly.itertuples()]
    lines += ["", "![图4-1 月度日积分估计](../figures/q1/station01_monthly_integral.png)", "",
              "图4-1 月度日积分估计与同日晴空参考；仅使用完整功率日，采样口径待确认。", "",
              f"在当前样本与积分近似口径下，{h['year_month']}的日均估计最高，为{h['mean_daily_integral_estimate_mwh']:.2f} MWh，来自{h['complete_power_days']}个完整日；{low['year_month']}最低，为{low['mean_daily_integral_estimate_mwh']:.2f} MWh，来自{low['complete_power_days']}个完整日。实际月度排序与“夏季必然最高”的预设不一致。晴空参考冬季较低、春夏较高，体现了该物理模型中的太阳几何和气候大气参数变化；实际曲线同时受真实天气、运行状态与测量因素影响，当前不能分离各因素的贡献。",
              "",
              "2019年6月仅覆盖1—13日，且一个日期因清洗缺失未进入完整日统计；该月均值不能推广到整个6月。清洗前全观测日均值另存于monthly_characteristics.csv，但与完整日均值的日期集合不同，不应把二者差异当作同样本清洗效果。",
              "",
              "按3—5月、6—8月、9—11月、12—2月分别归为春、夏、秋、冬。每个季节的所有日内时刻使用同一批完整日，图4-2阴影为不同日期的P25—P75范围。表4-3的峰值是平均曲线峰值，不是每日最大功率或太阳正午。", "",
              "表4-3 观测时段各季节平均日内曲线", "",
              "| 分组 | 完整日 | 平均曲线峰值（MW） | 峰值时刻（北京时间） | 实际包含月份 |",
              "|---|---:|---:|---|---|"]
    for season in ("spring", "summer", "autumn", "winter"):
        row = seasonal.loc[season]
        lines.append(f"| {season_names[season]} | {row.complete_power_days} | {row.average_profile_peak_mw:.2f} | {row.average_profile_peak_clock} | {row.included_year_months} |")
    lines += ["", "![图4-2 季节平均日内曲线](../figures/q1/station01_seasonal_diurnal.png)", "",
              "图4-2 平均日内形状及不同日期的P25—P75范围；各面板使用相同功率尺度。", "",
              "各组平均曲线均呈现从早晨上升、在中午附近达到峰值、傍晚下降的日内结构。春季样本平均峰值较高，但夏季合并了2018年7/8月和2019年6月1—13日，既跨年又不完整，不能据此认定完整夏季的发电水平低于其他季节。季节平均差异仍需结合气象和运行资料解释。",
              "",
              "结果依据：`monthly_characteristics.csv`、`seasonal_characteristics.csv`、`seasonal_diurnal_profiles.csv`。", "",
              "### 4.4 实际与参考偏差及短时波动", "",
              r"定义偏差为$d(t)=P_{\mathrm{actual,clean}}(t)-P_{\mathrm{ac,ref}}(t)$；负值表示实际低于该参考工况，不等同于设备损耗。",
              "",
              f"在{baseline['common_daylight_points']:,}个共同有效白昼样本上，基准平均偏差为{baseline['mean_actual_minus_reference_mw']:.3f} MW，平均绝对偏差为{baseline['mae_to_reference_mw']:.3f} MW；有{baseline['actual_exceeds_reference_points']:,}个点的实际值高于参考。这些量是对假设物理参考的偏离描述，不是第二问的预测误差或准确率。",
              "",
              "图4-3选取固定诊断日2018-08-25展示实际和各损耗情景参考。该日用于解释曲线，不因表现较好而宣称具有全年代表性。对全部月份的白昼偏差仍保留完整统计，见表4-4。", "",
              "![图4-3 实际与参考诊断日](../figures/q1/station01_reference_day.png)", "",
              "图4-3 固定诊断日实际/参考对比；固定组件温度及交流限制等均有假设。", "",
              "表4-4 按月的基准白昼偏差", "",
              "| 月份 | 有效白昼点数 | 平均实际－参考（MW） | 平均绝对偏差（MW） | 实际高于参考比例 |",
              "|---|---:|---:|---:|---:|"]
    lines += [f"| {r.year_month} | {r.points} | {r.mean_actual_minus_reference_mw:.3f} | {r.mean_abs_deviation_mw:.3f} | {r.actual_above_reference_fraction:.2%} |" for r in deviations.itertuples()]
    lines += ["", "各月平均偏差均为负，但仍有实际高于参考的时刻。温度、大气和设备参数与假设不一致，都可能影响偏差；缺少实际组件温度、运维和容量口径等资料，不能将平均偏差唯一归为云遮挡、故障或系统损耗。",
              "",
              r"相邻功率变化定义为$\Delta P(t)=P(t)-P(t-15\mathrm{min})$，仅对时间连续且两个端点有效的点计算。图4-4左侧给出白昼变化分布，右侧比较同期现场总辐照变化。",
              "",
              f"共有{characteristics['daylight_power_pairs']:,}个有效白昼点对；绝对变化中位数为{characteristics['median_abs_15min_change_mw']:.3f} MW，P95为{characteristics['p95_abs_15min_change_mw']:.3f} MW，最大为{characteristics['max_abs_15min_change_mw']:.3f} MW。功率与辐照变化的Pearson相关系数为{characteristics['power_irradiance_change_correlation']:.3f}，表明样本中存在同向变化关系，但不证明唯一因果机制。",
              "",
              "![图4-4 白昼15分钟变化](../figures/q1/station01_daylight_fluctuation.png)", "",
              "图4-4 白昼连续15分钟变化分布与现场辐照变化散点；缺失和跨时间缺口的点对不计入。",
              "",
              "两类事件说明为何不能统一归因。2019-03-30 14:15，功率相对前一采样点下降15.398 MW，现场总辐照下降684.5 W/m²，支持功率与辐照同步变化的描述。2018-12-27 11:15，功率下降14.456 MW并降为零，但同期辐照增加28.8 W/m²，此时现场总辐照仍约470.7 W/m²。后者无法仅凭辐照下降解释，停机、限电或测量问题只能列为待核实可能性，不能写为已确认原因。两类原始事件都保留，未因事后解释删除。",
              "",
              "结果依据：`reference_sensitivity.csv`、`monthly_daylight_deviation.csv`、`largest_daylight_changes.csv`、`zero_power_daylight_events.csv`。", "",
              "### 4.5 参考假设敏感性", "",
              "保持组件配置和同一批白昼样本不变，分别调整额外损耗与海拔假设。表4-5展示已有四个情景。0%、10%、20%为人为设定情景，并非真实损耗估计；200m也不是已确认海拔。", "",
              "表4-5 参考假设敏感性（共同有效白昼样本）", "",
              "| 情景 | 参考峰值（MW） | 平均实际－参考（MW） | 平均绝对偏差（MW） |",
              "|---|---:|---:|---:|"]
    lines += [f"| {sensitivity_names[r.scenario]} | {r.reference_peak_mw:.3f} | {r.mean_actual_minus_reference_mw:.3f} | {r.mae_to_reference_mw:.3f} |" for r in sensitivity.itertuples()]
    lines += ["", "增大假设额外损耗后，参考曲线下降，样本中的平均绝对偏差也减小。这说明实际/参考偏离的幅度依赖模型假设，不能因20%情景更接近实际就认定电站真实损耗为20%。当前敏感性检验只涉及少量参考参数，没有验证真实温度效应、逆变器配置，也尚未完成积分方法和清洗首点处理的敏感性。",
              "",
              "结果依据：`reference_sensitivity.csv`。", "",
              "### 4.6 本问结论与局限", "",
              f"第一，在当前完整日与积分近似下，实际发电水平具有月度差异：{h['year_month']}最高，{low['year_month']}最低。平均日内功率在中午附近较高，具体峰值随观测分组变化。",
              "",
              "第二，真实功率总体低于本次基准晴空参考，但也存在超过参考的时刻。因温度、设备和气候参数有简化，参考只用于描述条件明确的物理偏差，不能直接视为严格上限或设备损耗真值。",
              "",
              "第三，短时功率变化与现场辐照变化呈正相关，同时存在辐照未下降却功率降为零的事件。解释发电特性应同时考虑天气与运行/测量信息，当前无法确认全部事件原因。",
              "",
              "结论适用范围受以下限制：数据不足完整一年；夏季跨年且不完整；功率采样和时间戳口径未核实，电量为积分估计；真实AC/DC、海拔、组件温度和系统损耗参数未齐；持值首点和其他可疑记录保留；月度/季节比较未控制气象与运行因素。这些限制应随结论一起保留，不能只放在附录。第一问可以形成有证据的练习初稿，但真实物理口径一致性的完成条件仍未核实。",
              "",
              "### 4.7 引用与复核备注（编辑用，合并正文时统一处理）", "",
              "本章临时引用使用Q1前缀，合并全文时由C按首次出现顺序统一编号。复核状态尚未由A或C签认。", "",
              "- [Q1-1] Yao, T., Wang, J., Wu, H., et al. A photovoltaic power output dataset: Multi-source photovoltaic power output dataset with Python toolkit. Solar Energy, 2021, 230: 122–130. [DOI](https://doi.org/10.1016/j.solener.2021.09.050)。数据集DOI：[10.11922/sciencedb.01094](https://doi.org/10.11922/sciencedb.01094)。",
              "- [Q1-2] pvlib contributors. [Location.get_clearsky](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.location.Location.get_clearsky.html)。",
              "- [Q1-3] pvlib contributors. [get_total_irradiance](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.get_total_irradiance.html)。",
              "- [Q1-4] pvlib contributors. [pvwatts_dc模型公式](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.pvwatts_dc.html)。本方案采用固定参考温度的简化式，并明确忽略有效辐照中的部分损失。",
              "- [Q1-5] pvlib contributors. [pvwatts逆变器模型](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.inverter.pvwatts.html)。",
              "",
              "文献与方法资料访问日期：2026-10-12。本次运行pvlib版本见reference_summary.json。", "",
              "**数字和结果表路径约定：**上述结果文件均位于`results/q1/station01/`。`q1_evidence_index.csv`为章节数字索引；它不代替原始结果表。站点物理参数来源是ZIP内metadata.csv及参考假设文件。", "",
              "**A复核：**检查假设与解释是否匹配原题，尤其容量、采样口径、异常事件的原因边界。", "",
              "**C复核：**抽查数字索引与表格、图号与图片、样本集合、单位及引用编号；不能把本章MAE写为第二问预测精度。", ""]
    chapter = "\n".join(lines)
    draft = ROOT / "paper/第一问_正文初稿.md"
    draft.write_text("# 第一问正文初稿：station01\n\n版本：q1-draft-v1；整理日期：2026-10-12。可复现生成命令：`.venv/bin/python src/build_q1_draft.py`。\n\n" + chapter, encoding="utf-8")
    skeleton_path = ROOT / "paper/论文骨架.md"
    skeleton = skeleton_path.read_text(encoding="utf-8")
    start = skeleton.index("## 4 问题")
    end = skeleton.index("\n---\n\n## 5 问题", start)
    skeleton_path.write_text(skeleton[:start] + chapter.rstrip() + "\n" + skeleton[end:], encoding="utf-8")

    evidence = []
    def add(claim, section, value, unit, source, selector):
        evidence.append({"claim_id": claim, "section": section, "value": value, "unit": unit,
                         "source_file": source, "source_selector": selector})
    for field in ("rows", "observed_days"):
        add("data_" + field, "4.1", audit[field], "条" if field == "rows" else "日", "summary.json", field)
    for field in ("invalid_power_points", "complete_power_days", "day_zero_flags_retained", "remaining_night_positive_power_points"):
        add("clean_" + field, "4.1", cleaning[field], "日" if field == "complete_power_days" else "点", "cleaning_summary.json", field)
    for field in ("frozen_min_points", "deep_night_elevation_deg", "power_tolerance_mw", "strong_irradiance_threshold_wm2"):
        add("clean_rule_" + field, "4.1", rules[field], "见字段名", "q1_cleaning_rules_snapshot.json", field)
    for field in ("panel_number", "panel_pmax_wp", "derived_dc_capacity_mwp", "assumed_ac_limit_mw"):
        add("parameter_" + field, "4.2", reference[field], "见字段名", "reference_summary.json", field)
    for row in monthly.itertuples():
        for field in ("observed_days", "complete_power_days", "mean_daily_integral_estimate_mwh", "reference_mean_daily_integral_same_days_mwh"):
            add(f"month_{row.year_month}_{field}", "4.3", getattr(row, field), "MWh" if "mwh" in field else "日",
                "monthly_characteristics.csv", f"year_month={row.year_month}; {field}")
    for season, row in seasonal.iterrows():
        for field in ("complete_power_days", "average_profile_peak_mw", "average_profile_peak_clock", "included_year_months"):
            add(f"season_{season}_{field}", "4.3", row[field], "见字段名", "seasonal_characteristics.csv", f"season={season}; {field}")
    for row in deviations.itertuples():
        for field in ("points", "mean_actual_minus_reference_mw", "mean_abs_deviation_mw", "actual_above_reference_fraction"):
            add(f"deviation_{row.year_month}_{field}", "4.4", getattr(row, field), "原始小数比例" if "fraction" in field else "见字段名",
                "monthly_daylight_deviation.csv", f"year_month={row.year_month}; {field}")
    for field in ("common_daylight_points", "mean_actual_minus_reference_mw", "mae_to_reference_mw", "actual_exceeds_reference_points"):
        add("baseline_" + field, "4.4", baseline[field], "见字段名", "reference_sensitivity.csv", f"scenario=reference_ac_loss0_mw; {field}")
    for field in ("daylight_power_pairs", "median_abs_15min_change_mw", "p95_abs_15min_change_mw", "max_abs_15min_change_mw", "power_irradiance_change_correlation"):
        add("ramp_" + field, "4.4", characteristics[field], "见字段名", "characteristics_summary.json", field)
    for source, timestamp in [("largest_daylight_changes.csv", "2019-03-30 14:15:00+08:00"),
                              ("zero_power_daylight_events.csv", "2018-12-27 11:15:00+08:00")]:
        event = pd.read_csv(FOLDER / source).set_index("time_local").loc[timestamp]
        for field in ("power_change_15min_mw", "irradiance_change_15min_wm2", "power_clean", "lmd_totalirrad_clean"):
            add(f"event_{timestamp}_{field}", "4.4", event[field], "见字段名", source, f"time_local={timestamp}; {field}")
    for row in sensitivity.itertuples():
        for field in ("reference_peak_mw", "mean_actual_minus_reference_mw", "mae_to_reference_mw"):
            add(f"sensitivity_{row.scenario}_{field}", "4.5", getattr(row, field), "MW", "reference_sensitivity.csv", f"scenario={row.scenario}; {field}")
    save_csv(pd.DataFrame(evidence), FOLDER / "q1_evidence_index.csv")
    inputs = ["summary.json", "cleaning_summary.json", "q1_cleaning_rules_snapshot.json", "reference_summary.json", "characteristics_summary.json",
              "monthly_characteristics.csv", "seasonal_characteristics.csv", "monthly_daylight_deviation.csv",
              "reference_sensitivity.csv", "largest_daylight_changes.csv", "zero_power_daylight_events.csv"]
    manifest = {"draft_version": "q1-draft-v1", "status": "待A/C复核，不是正式定稿",
                "result_file_sha256": {name: hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() for name in inputs},
                "evidence_entries": len(evidence), "draft_sha256": hashlib.sha256(draft.read_bytes()).hexdigest(),
                "unresolved": ["实测AC/DC和采样区间口径", "真实海拔、逆变器配置及组件温度", "不完整全年/夏季覆盖",
                               "异常原因", "积分及清洗规则的进一步敏感性", "A/C独立复核和全文引用统一"]}
    (FOLDER / "q1_draft_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"draft": str(draft), "evidence_entries": len(evidence), "status": manifest["status"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
