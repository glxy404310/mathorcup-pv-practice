# B题数据来源与检查记录

负责人：角色A提供数据，角色B核验

最后更新日期：2026-10-12（北京时间）

当前状态：第一问选用station01；已完成基础计算与正文审阅稿，待A/C复核；真实物理口径及部分敏感性仍待完善

本记录依据本地 ZIP、数据作者论文和作者仓库填写。尚未验证的信息保留“待确认”；“当前 ZIP 未提供”仅描述本次收到的文件，不代表其他来源不存在该资料。原始数据保持不修改。

## 1. 候选来源

优先检查PVOD：

- 数据发布页：https://www.scidb.cn/en/detail?dataSetId=f8f3d7af144f441795c5781497e56b62
- 作者仓库：https://github.com/yaotc/PVODataset
- 数据集DOI：10.11922/sciencedb.01094

备用来源：

- PVDAQ：https://catalog.data.gov/dataset/photovoltaic-data-acquisition-pvdaq-public-datasets
- DKA Solar Centre：https://www.dkasolarcentre.com.au/

## 2. 选定数据集

| 检查项 | 实际记录 | 依据：说明文件或数据字段 |
|---|---|---|
| 数据集名称和版本 | PVOD v1.0 | ZIP文件名、作者仓库[2] |
| 原始发布者 | Tiechui Yao等，PVOD数据集作者 | 数据作者论文[1]、作者仓库[2] |
| 下载页面和实际文件链接 | 发布页：https://www.scidb.cn/en/detail?dataSetId=f8f3d7af144f441795c5781497e56b62；本次实际下载文件的直链未记录 | 项目已有来源链接；发布页与文件直链分开记录 |
| 原始文件 | docs/PVODdatasets_v1.0.zip 内的 station01.csv、metadata.csv | 本地ZIP目录 |
| 下载日期 | 2026-10-12（按角色B填写，未独立核验下载日志） | 角色B原记录“10.12”及本次日期上下文 |
| 使用许可与引用要求 | 作者仓库标注MIT，并要求仅用于科学研究、引用数据论文；发布页数据文件的具体许可待确认 | 作者仓库[2]；不直接将代码许可等同于数据文件许可 |
| 电站编号 | station01 | metadata.csv：Station_ID；station01.csv文件名 |
| 经度、纬度、海拔 | 117.45722°E、38.18306°N；海拔待确认 | metadata.csv：station01行Longitude、Latitude；表中无海拔字段 |
| 组件倾角、方位角 | 倾角33°，朝南；若采用从正北顺时针的方位角约定，对应180° | metadata.csv：station01行Array_Tilt = South 33° |
| 装机容量及单位 | 20000 kW，即20 MW；AC/DC口径待确认 | metadata.csv：Capacity = 20000；单位见论文[1]表1 |
| 是否有开机容量记录 | 当前ZIP未提供随时间变化的开机容量记录；装机容量不能直接视为已核实的开机容量 | ZIP目录、metadata.csv和station01.csv字段 |
| 功率字段名称和单位 | power，MW | station01.csv：power；单位见论文[1]表1 |
| 功率是实测还是模拟 | 实测 | 论文[1]的数据说明及作者仓库[2]对LMD的说明 |
| 功率是瞬时值还是区间均值 | 待确认 | 已核对的资料尚不能明确；需补充测量口径说明 |
| 原始采样间隔 | 15分钟；station01共有33408条，时间连续且无重复时间戳 | station01.csv：date_time列逐点检查 |
| 起止日期 | UTC：2018-06-30 16:00至2019-06-13 15:45；北京时间：2018-07-01 00:00至2019-06-13 23:45 | station01.csv：date_time最小值和最大值；UTC依据论文[1] |
| 时区与时间戳含义 | 原始时间为UTC；分析时先赋予UTC时区，再转换为Asia/Shanghai。时间戳位于区间头、区间尾或采样瞬时的口径待确认 | 论文[1]说明时间为UTC；CSV时间字符串不自带时区 |
| 是否覆盖完整一年 | **不满足**：覆盖348个北京时间日，少于完整一年 | station01.csv时间范围及33408 ÷ 96 = 348 |
| 指定测试月份最后一周是否完整 | 按北京时间和“月末向前数7个日历日”的练习口径，2018年8月25—31日、11月24—30日，2019年2月22—28日、5月25—31日各有672条；这是时间记录覆盖检查，尚未完成异常值筛查 | station01.csv：date_time转换后逐周计数；口径见B题三人新手备赛指南.md |
| NWP字段与单位 | nwp_globalirrad、nwp_directirrad：W/m²；nwp_temperature：°C；nwp_humidity：%；nwp_windspeed：m/s；nwp_winddirection：度；nwp_pressure：hPa | station01.csv字段；论文[1]表1 |
| 现场气象观测字段与单位 | lmd_totalirrad、lmd_diffuseirrad：W/m²；lmd_temperature：°C；lmd_pressure：hPa；lmd_winddirection：度；lmd_windspeed：m/s | station01.csv字段；论文[1]表1 |
| NWP起报、发布时间和有效时间 | CSV未单列起报时间、发布时间和预报版本；NWP与date_time逐行对齐，但其有效时间含义和在起报时的可用性待确认 | station01.csv字段检查；整段数据的起止日期不等于预报发布时间 |
| 预测提前量 | 数据中NWP的实际提前量待确认；本练习计划采用D-1日00:00起报、预测D日，目标提前量24小时至47小时45分钟，不能据此推定现有NWP满足要求 | NWP元信息未完整提供；练习起报口径见B题三人新手备赛指南.md |
| 是否有邻近网格、网格坐标和空间间距 | 当前ZIP未提供明确的邻近NWP网格及其坐标、间距 | ZIP目录及站点表字段；电站坐标不等于NWP网格坐标 |
| 是否有其他站点及位置 | 有，共10个站点station00—station09，位置见元数据；各站时间覆盖和质量不同 | ZIP内10个站点CSV；metadata.csv：Station_ID、Longitude、Latitude |

### 第一问的初步检查结果与待确认项

- station01的33408条时间记录均唯一、连续，相邻间隔为15分钟；CSV未发现空单元格。这不代表已经完成异常值、哨兵值或物理合理性检查。
- 组件型号LW6P60-270、单组件额定功率270 Wp、组件数74000；逆变器型号TC500KH、单台额定功率500 kW，均来自metadata.csv的station01行。逆变器总台数及电站交流容量限制尚未核实。
- 第一问仍需明确：海拔、功率采样口径、时间戳区间含义、容量AC/DC口径、温度处理和系统损耗假设。缺失参数应记录来源或明确假设。
- 已运行src/q1_check_data.py进行原始数据检查，并运行src/q1_clean_data.py生成第一版清洗数据data/processed/station01_q1_clean.csv。检查与清洗摘要分别保存在results/q1/station01/检查摘要.md、清洗摘要.md。
- 用户确认目前只有ZIP，允许先采用明确假设。已运行src/q1_reference_power.py生成results/q1/station01/reference_power.csv；组件额定直流容量按74000×270 Wp得到19.98 MWp，交流限制20 MW、海拔0m、固定组件温度25°C及额定逆变器效率96%为假设。参数与限制见docs/第一问_参考功率方案.md。尚未训练预测模型。
- 已运行src/q1_characteristics.py生成月度、季节平均日内、白昼偏差和连续15分钟变化统计，见results/q1/station01/特性分析摘要.md。日积分估计用Σ采样功率×0.25h，采样口径未确认，不能称为精确实测电量；夏季样本跨年且覆盖不完整。
- 已将方法、结果、解释边界、参数敏感性与局限整理到paper/第一问_正文初稿.md，并同步论文骨架的第一问章节。数字索引与稿件/结果哈希见results/q1/station01/q1_evidence_index.csv、q1_draft_manifest.json。尚未由A/C独立复核，不能标为正式定稿。
- 以几何太阳高度角≤0识别夜间、以0.01 MW作为正功率筛查阈值，标记68个夜间非零点；其中太阳高度角<-6°的点为55个。另有65个白昼点在现场总辐照>200 W/m²时功率≤0.01 MW。标记可能重叠，不等于已确认异常。
- 多字段持值复查定位到两段：2018-12-08 14:00至2018-12-09 14:30（99点），以及2019-06-10 10:15至20:15（41点）。两段功率和六项现场量均逐点相同，且持续至深夜，具体原因未确认。
- 第一版规则q1-station01-v1保留两段首点并标注边界待复查，将后续138个重复点的七项现场清洗值设为缺失；原始列和NWP保持不变。65个白昼较强辐照下零/低功率点保留并标记，没有插值、补零或裁剪。
- 清洗后有345个完整96点功率日，3日功率不完整。四个测试周各672条记录保持完整，测试功率未因本规则产生缺失。规则见docs/q1_cleaning_rules.json，逐值变更见results/q1/station01/cleaning_log.csv。

## 3. 下载文件清单

文件大小为实际字节数。ZIP内部CSV大小为解压后的文件大小，本次通过直接读取ZIP核验，尚未解压到data/raw/。原始文件保持不修改，清洗结果另存。

| 文件名 | 内容 | 大小 | 本地存放位置 | 是否能读入 |
|---|---|---|---|---|
| PVODdatasets_v1.0.zip | 元数据、10个站点数据及部分McClear样例 | 7983824字节 | docs/PVODdatasets_v1.0.zip | 能打开并读取目录 |
| metadata.csv | 站点坐标、容量、倾角和设备信息 | 7222字节 | 上述ZIP内metadata.csv | 能通过CSV解析器读入 |
| station01.csv | station01功率、NWP和现场气象观测 | 3872299字节 | 上述ZIP内station01.csv | 能通过CSV解析器读入 |

## 4. 交给角色B的检查任务

- [x] 成功读入一个站点数据表，输出字段名称和前几行（summary.json、preview.csv）。
- [x] 按时间排序，检查重复时间戳和缺失时间点（summary.json、missing_timestamps.csv）。
- [x] 统计各字段缺失比例（field_profile.csv；本次未发现数值缺失、解析失败或无穷值）。
- [x] 核对功率和容量的单位，记录换算方法（功率已为MW，容量由kW除以1000；AC/DC口径仍待确认）。
- [x] 确认时区，避免重复进行时区转换（原始UTC→Asia/Shanghai）。
- [x] 画连续几天的功率曲线，检查夜间和异常值（station01_week.png、flagged_rows.csv；标记尚未清洗）。
- [x] 列出起止日期以及各指定测试周的覆盖情况（test_week_coverage.csv）。
- [x] 将天气预报与现场观测字段区分清楚（nwp_*与lmd_*）。
- [ ] 检查预测时采用的天气和历史功率是否在起报时已经可获得。

## 5. 与原题要求的差距

| 要求 | 状态：满足/不满足/待确认 | 缺口和下一步 |
|---|---|---|
| 公开可追溯数据来源 | 满足：已找到作者论文、仓库和数据DOI | 实际文件直链及数据文件具体许可仍需补记 |
| 完整一年功率数据 | 不满足 | station01仅348天；作为练习明确限制，完整解题仍需补齐 |
| 15分钟时间分辨率 | 满足 | station01时间戳连续，相邻间隔15分钟；采样物理含义待确认 |
| 地理与容量信息 | 部分满足 | 有经纬度、倾角朝向和装机容量；海拔与AC/DC口径待确认 |
| 与功率配套的历史NWP | 部分满足 | 表中有同时间行的NWP字段；来源细节、预报版本与发布时间待核实 |
| NWP起报可用性 | 待确认 | 需补充发布时间、有效时间与提前量说明，不能仅按date_time合并后认定可用 |
| 指定测试周完整覆盖 | 满足时间记录覆盖（跨年练习口径） | 四周各672条，共2688条；异常值与评分有效性尚未检查，全年覆盖仍不满足 |
| 第4问所需的空间或局地气象信息 | 部分满足 | 有站点局地观测；未提供邻近NWP网格及坐标，尚不足以直接做最近网格与空间插值对照 |

## 6. 本次选择结论

选择该数据集的理由：同时提供电站元数据、15分钟实测功率、现场气象和NWP字段；station01记录连续，适合先完成单站练习。

目前可以开展哪些问题：先做第一问的数据检查、月度和日内统计；参考功率需在明确参数与假设后计算。随后可开展第二问的历史功率基线与模型。第三问的实际日前预报验证需先核实NWP起报可用性。

目前无法验证哪些要求：完整一年覆盖不满足；NWP发布与版本信息、部分物理口径尚不明确；第四问的邻近网格空间处理资料不足。

下一步任务、负责人和完成时间：角色B核查正文与结果表；角色A审核假设和解释边界，角色C依据数字索引抽查、统一引用并合并正文。清洗/积分方法敏感性及真实设备口径仍待补充。具体完成时间由团队确定。

## 7. 参考文献

[1] Yao, T., Wang, J., Wu, H., et al. A photovoltaic power output dataset: Multi-source photovoltaic power output dataset with Python toolkit. Solar Energy, 2021, 230: 122–130. DOI：[10.1016/j.solener.2021.09.050](https://doi.org/10.1016/j.solener.2021.09.050)。本次核验使用[作者上传全文](https://www.researchgate.net/publication/355389908_A_photovoltaic_power_output_dataset_Multi-source_photovoltaic_power_output_dataset_with_Python_toolkit)，访问日期：2026-10-12。

[2] yaotc. [PVODataset作者仓库](https://github.com/yaotc/PVODataset)。用于核验数据结构、作者引用要求和仓库许可说明；访问日期：2026-10-12。

数据集：Yao, T., Wang, J., Wu, H., et al. PVOD v1.0: A photovoltaic power output dataset. Science Data Bank, 2021. DOI：[10.11922/sciencedb.01094](https://doi.org/10.11922/sciencedb.01094)。本地接收文件：PVODdatasets_v1.0.zip；具体发布修订版本待确认。
