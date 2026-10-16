from pathlib import Path
import re
root=Path.cwd(); p=root/'paper/论文初稿.md'; s=p.read_text()
s=s[s.index('## 一、问题重述'):s.index('## 参考文献')]
s=s.replace('本次建模采用的数据为 PVOD v1.0 数据集。','本次建模采用 PVOD v1.0 公开数据集[1–3]。')
s=s.replace('根据题目与附件 1（误差分析方法）的要求','根据题目与附件 1（误差分析方法）[4]的要求')
s=s.replace('不使用任何气象信息、仅使用历史功率','不使用现场逐时气象和 NWP 预报字段、以历史功率为主要输入')
s=s.replace('在完全不含气象信息的条件下','在不使用现场逐时气象和 NWP 预报字段的条件下')
s=s.replace('严格的空间降尺度要求把粗分辨率 NWP 网格映射到电站所在的局地尺度，需要网格间距、原始格点坐标与邻域场。当前数据只提供单站 NWP 序列与对应现场测量，**没有网格间距、原始格点坐标与邻域场**，因此无法进行双线性/反距离插值，也无法展示真实的 1 km→100 m 分辨率提升。','空间降尺度的目标是描述粗尺度预报未能直接表达的局地气象差异。站点统计回归可作为候选方法，但其空间解释仍需要原始 NWP 分辨率及站点提取关系。当前文件只有单站预报和现场测量，未记录上述信息，也没有可用于插值的邻域格点，故本文仅检验局地统计订正的预测效果。')
s=s.replace('**严格细网格空间降尺度仍未完成**，正文与摘要均保留此边界。','本实验未验证空间尺度提升。')
s=s.replace('严格空间降尺度未完成','空间尺度提升未获验证').replace('完整的空间降尺度未能完成','空间尺度提升未获验证').replace('严格的空间降尺度未能完成','空间尺度提升未获验证')
s=s.replace('海拔 0 m（另设 200 m 作敏感性）、地面反照率 0.25、组件温度固定 25 ℃、逆变器额定效率 0.96（PVWatts 默认值）、组件朝南倾角 33°。除组件数量与规格取自元数据外，其余均为工作假设。','海拔 0 m（另设 200 m 作敏感性）、地面反照率 0.25、组件温度固定 25 ℃、逆变器额定效率 0.96。组件数量、规格及朝南 33° 倾角来自元数据，其余为参考模型的工作假设。')
s=s.replace('题目所给数据真实可靠，能够反映电站的实际运行情况。','在数据质量核查与异常标记之后，保留观测用于刻画样本期运行状态；未记录的停机、限电等因素不作独立识别。')
s=s.replace('且段内存在深夜正功率或正辐照时','且段内至少一个点同时满足太阳高度角低于 −6°、功率大于 0.01 MW、现场总辐照大于 0 时')
s=s.replace('为刻画确定性的出力上界形态，建立晴空参考功率模型。','为刻画晴空条件下的参考出力形态，采用 pvlib 实现物理计算链[5–6]。')
s=s.replace('不含义严格的物理必然性','不代表逐日峰值时刻的范围')
s=s.replace('问题二不含任何气象信息，考虑三类方法与一个回归模型：','问题二不读取现场逐时气象或 NWP 字段，但采用太阳几何和预先计算的晴空参考；后者含 pvlib 的气候浑浊度资料，不等同于完全没有气象先验。考虑三类基线与一个回归模型：')
s=s.replace('t<o','t\\in H(o)')
s=s.replace('标定比例系数\n','标定比例系数。其中 H(o) 为起报前 28 天内的非测试、白昼、实测功率有效且参考功率大于 0.5 MW 的时刻集合。\n')
s=s.replace('其中 $f_2$ 为直方图梯度提升树','其中 $f_2$ 为直方图梯度提升树[7]')
s=s.replace('一个目标日可能对应多个起报提前量，属直接多步训练。','同一目标时刻可对应 1—3 个起报提前量，训练按起报—目标对等权，因此不同真实时刻的总训练权重并不相同。')
s=s.replace('**验证选优是必要的**。','**验证选优固定了主方案的选择规则**。')
s=s.replace('说明"哪种历史基线更好"本身随季节变化。','说明各验证周偏好的历史模型不同。该规则避免由测试误差倒推方案，但本次并未优于固定晴空比例基线。')
s=s.replace('其余结构一致，用于检验非辐照信息是否带来额外收益。','其余建模流程一致，两套特征方案分别选择叶节点数。因此，这属于各自调参后的特征方案比较，不能把全部误差差异单独归因于新增字段。')
s=s.replace('若某类验证白昼点不足 20，则沿用总体最优权重。','若某类验证白昼点不足 20，则沿用总体最优权重。该规则没有最低日期数约束：2018 年 8 月验证周中辐照档虽有 53 点，却只有 1 天；2018 年 11 月无低辐照日，2019 年 2 月无中辐照日，2019 年 5 月只有高辐照日，缺失场景均回退总体权重。')
s=s.replace('低辐照档样本仅 52 点，其结论限于本次测试。','低、中、高辐照档分别覆盖 1、6、21 个日期。低辐照档的 52 点全部来自 2018-08-25，因此该退化只能说明这一测试日的表现，尚不足以推断低辐照天气的一般规律。')
s=s.replace('**加入 NWP 总体有效**。','**加入 NWP 在固定样本上降低了总体误差**。')
s=s.replace('相对下降 10.28%。','相对下降 10.28%。相对固定晴空比例和气候态基线，降幅分别为 8.33% 和 9.45%。')
s=s.replace('两者均采用 15 叶、180 轮的固定提升树。','令辐照树的无量纲输出为 gθ，则 D_G=max(1000gθ,0)，单位为 W/m²；D_T 输出温度残差，单位为 ℃。两者均采用 15 叶、180 轮的固定提升树。')
s=s.replace('学习相同的功率映射 $F$：','学习相同的功率映射 $F$。树拟合的标签为 P/C；下式中 F 已包含乘以 C 的反缩放、白昼 [0,C] 裁剪及夜间置零：')
s=s.replace('G_{NWP}+\\overline{G_{obs}-G_{NWP}},','\\max(0,G_{NWP}+\\overline{G_{obs}-G_{NWP}}),')
s=s.replace('只用训练时段的现场辐照与气温作为标签','只用训练时段的现场辐照与气温作为标签')
s=s.replace('同一 $F$ 用于三组对照：','偏差均值仅由对应训练样本计算。同一 $F$ 用于三组对照：')
s=s.replace('独立单元是 28 个日期，而非大量相互相关的 15 分钟点。','以 28 个日期作为重抽单位，避免把相邻 15 分钟点视为独立重复；周内相邻日期仍可能相关，区间仅条件于这四个固定测试周。')
s=s.replace('逐日 nRMSE','按目标日序号汇总的 nRMSE')
s=s.replace('RMSE 的下降可能只是删除了低太阳高度角样本，不能称为模型改进。','筛除低太阳高度角样本后三者 nRMSE 均略升。样本组成发生变化，不能据此认定模型能力改变。')
s=s.replace('作为补充，采用整段非测试日期训练的离线协议（第二问方案与融合权重仍保留对应起报前的验证选择）得到：','作为补充，采用整段非测试日期训练的离线协议。树模型统一采用最后一周（2019 年 5 月）的验证选参结果，第二问方案与场景权重仍沿用各周前置验证选择。其训练范围与部分选参设置均不同于向前协议，结果如下：')
s=s.replace('这是因为离线训练使用了包括部分早期测试周之后在内的更多日期，分布覆盖不同。','离线训练纳入了部分早期测试周之后的日期，训练规模、季节覆盖及部分选参设置均有变化；现有对照未单独分离各因素的影响。')
s=s.replace('本文场景融合显示分场景权重有效但总体未必最优','场景融合相对第二问的点估计误差较低，但弱于全字段第三问模型且日期重抽区间跨零')
s=s.replace('基于 station08 电站数据完成了四个问题的建模与验证','基于 station08 电站数据完成出力特性分析、功率预测对照和局地气象订正的有限验证')
s=s.replace('**总体判断**：在所给数据与假设下，加入 NWP 能带来可观测的预测改善，但改善的统计稳定性尚不充分，气象空间降尺度也未能完成。因此，本文的结论是"在给定条件下有效、在未证实条件下设限"，而非对真实业务运行能力的断言。','加入 NWP 的收益主要体现在中、高预报辐照档，且依赖目标时刻预报在起报时已经可用的假设。将这一结果用于调度前，仍需补齐发行档案、完整年度观测及逐日 24—48 小时回测；单站订正的负结果也不能推广为所有空间降尺度方法均无效。')
s=s.replace('数据规格。','数据规格。')
s=s.replace('但观测时段不足完整一年。','观测跨度为 348 个日历日，未达到题目要求的完整一年；缺测与未覆盖时段均未用其他站点数据拼接。')
s=s.replace('该表与证据包中的逐点预测一一对应。','该表与证据包中的逐点预测一一对应。这里将“预测时间范围 7 天”解释为固定起报多步预测；仅第一个目标日处于题目所述 24—48 小时日前窗口，后六日是延伸预测，不能把总体指标全部称为日前精度。')
s=s.replace('需要先界定可验证范围。当前数据只提供单站的 NWP 序列与对应的现场测量，没有网格间距、原始格点坐标与邻域场，因此无法进行真正的双线性/反距离插值，也就无法展示分辨率提升。可实现的仅是','当前数据只提供单站 NWP 与现场测量，未说明原始网格尺度及站点提取关系，无法验证分辨率提升。本文采用')
s=s.replace('因此，**不能称为空间降尺度成功**。','因此，本次局地订正未取得功率预测收益，也未验证空间尺度提升。')
s=s.replace('若要完成严格的第四问，下一步需要同期邻近格点 NWP 坐标、空间分辨率与发行版本，且不能把其他电站的站点 NWP 冒充为规则网格。','进一步检验需补充原始 NWP 尺度、站点提取关系及发行版本；若开展空间插值，还需同期邻近格点及其坐标。')
s=s.replace('RMSE','nRMSE').replace('nnRMSE','nRMSE').replace('归一化 nRMSE','nRMSE').replace('归一 nRMSE','nRMSE')
s=s.replace('nRMSE（原单位）','RMSE（原单位）').replace('辐照的 MAE 略降（106.86 → 104.85 W/m²）但 nRMSE','辐照的 MAE 略降（106.86 → 104.85 W/m²）但 RMSE').replace('GHI 的 MAE 变小而 nRMSE','GHI 的 MAE 变小而 RMSE')
s=s.replace('**','')
s=s.replace('---\n','')
# Preserve equations; table borders are repaired separately below.
# Remove manually supplied captions and generate complete sequential table captions.
s=s.replace('表 1 光伏电站历史发电功率与 NWP 数据规格及要求\n\n','')
titles=['主要符号与单位','光伏电站及数据规格','月度日积分估计','季节平均日内曲线特征','晴空参考参数敏感性','两站数据质量比较','两站共同完整日对比','向前协议下各方法总体指标','预报辐照分档结果','测试月份的功率预测误差','局地气象订正误差','按日期分层重抽的误差差区间','目标日序号与预测误差','白昼判定阈值敏感性','离线协议补充结果','向前训练与历史输入时序核对']
lines=s.splitlines(); out=[]; ti=0
for i,line in enumerate(lines):
 if line.startswith('|') and (i==0 or not lines[i-1].startswith('|')):
  ti+=1; out.extend([f'表 {ti} {titles[ti-1]}',''])
 out.append(line)
assert ti==len(titles),(ti,len(titles))
s='\n'.join(out)
abstract='''# 光伏电站出力特性与融合气象信息的功率预测

摘要

光伏出力既有由太阳位置决定的日周期，也受天气变化影响。本文选取 PVOD 数据集中的 station08 电站，利用 15 分钟功率、现场气象和数值天气预报（NWP）数据，分析出力特性，比较历史功率预测、气象信息融合与局地统计订正的效果。样本覆盖 2018 年 7 月至 2019 年 6 月的 345 个完整观测日，未满一年。主实验在四个指定月末周固定起报，预测未来七天，训练标签与历史功率输入均早于起报时刻。

针对问题一，建立晴空辐照、板面转换与逆变器相结合的参考功率模型。月度日积分估计均值在 2019 年 5 月最高，为 99.23 MWh，2 月最低，为 49.56 MWh；白昼实际功率较参考平均低 5.34 MW。相邻 15 分钟功率变化绝对值的 95 分位为 2.798 MW，其变化与现场辐照变化的相关系数为 0.843。

针对问题二，比较持续性、近 14 日同时刻均值、晴空比例和残差梯度提升树，以起报前独立验证周选定主方案。四周 1346 个白昼点的容量归一化均方根误差（nRMSE）为 0.1210；固定晴空比例基线为 0.1184，表明复杂模型与验证选优均不必然优于简单基线。

针对问题三，在目标时刻 NWP 于起报时可用的假设下，加入气象字段后 nRMSE 降至 0.1086，相对第二问主方案下降 10.28%。中、高预报辐照档改善，唯一低辐照测试日退化。按日期分层重抽所得误差差的 95% 区间跨零，尚不足以确认稳定收益。

针对问题四，采用辐照、气温订正与功率映射组成的两阶段模型。非线性局地订正 nRMSE 为 0.1193，较同一功率映射的原始气象对照上升 3.94%，未取得总体改善。由于原始 NWP 空间尺度及站点提取关系缺失，本实验仅验证单站订正，未验证空间分辨率提升。

结果说明，气象信息在固定测试样本上有预测价值，但需结合场景和日期差异评价。七天固定起报的总体结果不能全部解释为 24—48 小时日前精度；实际应用仍需补齐预报发行信息并开展逐日回测。

关键词：光伏功率预测；晴空参考模型；梯度提升树；数值天气预报；局地统计订正

'''
refs='''

## 参考文献

[1] Yao T, Wang J, Wu H, et al. A photovoltaic power output dataset: Multi-source photovoltaic power output dataset with Python toolkit. Solar Energy, 230: 122–130, 2021. DOI:10.1016/j.solener.2021.09.050.

[2] Yao T, Wang J, Wu H, et al. PVOD v1.0: A photovoltaic power output dataset. Science Data Bank, 2021. DOI:10.11922/sciencedb.01094. 数据引用按作者仓库记录；本地文件修订版本未单独核实。

[3] yaotc. PVODataset. https://github.com/yaotc/PVODataset，访问时间：2026-10-16。

[4] B题 光伏电站发电功率日前预测问题；附件1 误差分析方法. 赛题材料，见支撑材料 docs 目录。

[5] Holmgren W F, Hansen C W, Mikofski M A. pvlib python: a python package for modeling solar energy systems. Journal of Open Source Software, 3(29): 884, 2018. DOI:10.21105/joss.00884.

[6] pvlib developers. Location.get_clearsky. https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.location.Location.get_clearsky.html，访问时间：2026-10-16。

[7] scikit-learn developers. HistGradientBoostingRegressor. https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html，访问时间：2026-10-16。

## 附录

### 附录 A 软件与复现命令

计算环境为 Python 3.13.15、numpy 2.5.4、pandas 3.0.6、scikit-learn 1.9.1、pvlib 0.16.1，具体依赖见 requirements-lock.txt。随机种子为 20261014。以下命令在项目根目录运行。--inspect 仅查看已有证据；完整重训会覆盖证据包、汇总图及自动生成的交接稿。论文排版采用 python-docx，PDF 由 LibreOffice 导出。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python src/q1_check_data.py --station station08 --source data/PVOD
.venv/bin/python src/q1_clean_data.py --rules docs/q1_cleaning_rules_station08.json
.venv/bin/python src/q1_reference_power.py --assumptions docs/q1_reference_assumptions_station08.json --source data/PVOD
.venv/bin/python src/q1_characteristics.py --station station08
.venv/bin/python src/build_q1_station08_report.py
OMP_NUM_THREADS=2 .venv/bin/python src/q234_forecast.py
.venv/bin/python src/q234_forecast.py --inspect
.venv/bin/python src/q234_forecast.py --export-table2 paper/表2.csv
.venv/bin/python -m unittest discover -s tests -v
```

### 附录 B 数据及结果清单

支撑材料保留主站 station08、对照站 station01 原始 CSV、完整 metadata.csv 及两站清洗表；同时保留两站的清洗规则、参考参数、第一问结果、第二至四问证据包和图件。station01 仅用于第一问共同完整日比较，不参与第二至四问训练。

逐点预测文件“表2_七天固定起报逐点预测.csv”包含 2688 条唯一目标时间记录，均使用北京时间；功率单位为 MW。四周各 672 条，白昼评价 1346 条。每周固定一个起报时刻，提前量为 24—191.75 小时，不能以修改时间列的方式将其转成逐日滚动预测。证据包同时保存主实验与补充离线预测、指标、训练审计和输入文件 SHA-256。

### 附录 C 计算源程序

以下完整列出六个计算与报告脚本及四个测试文件，内容与支撑材料中的源文件一致。长行在排版中自动换行，不改变附件中的程序内容。
'''
final=abstract+s+refs
(root/'paper/final/论文终稿.md').write_text(final)
print('tables',ti,'chars',len(final))
