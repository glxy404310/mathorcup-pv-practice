"""station08问题2—4：冻结七天预测、NWP消融、单站统计降尺度及C交接稿。

AI辅助实现；所有结论由本脚本实际运行生成。默认仅生成一个证据包、一张图、一份稿件。
运行：OMP_NUM_THREADS=2 .venv/bin/python src/q234_forecast.py
导出题目表2：.venv/bin/python src/q234_forecast.py --export-table2 /指定目录/表2.csv
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import pvlib
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from q1_check_data import ROOT, source_sha256
from q1_reference_power import clear_sky_poa, reference_from_poa

SEED = 20261014
CAPACITY = 20.0
TEST_MONTHS = (2, 5, 8, 11)
MODEL_NAMES = {
    'persistence': 'Q2持续性', 'climatology': 'Q2近14日气候态', 'physical': 'Q2晴空比例',
    'hist_tree': 'Q2历史树模型', 'q2_selected': 'Q2验证选优',
    'nwp_tree': 'Q3历史+NWP', 'nwp_radiation': 'Q3仅加辐照', 'q3_gate': 'Q3场景融合',
    'q4_raw_control': 'Q4原始气象对照', 'q4_bias': 'Q4均值偏差订正', 'q4_local': 'Q4非线性局地订正'}
CONFIGS = ({'max_leaf_nodes': 7, 'l2_regularization': 2.0},
           {'max_leaf_nodes': 15, 'l2_regularization': 2.0})


def test_mask(index):
    """最后一周定义为本地自然月最后7日，而非最后一个周一至周日。"""
    return np.asarray(index.month.isin(TEST_MONTHS) & (index.day > index.days_in_month - 7))


def metrics(actual, predicted, daylight, capacity=CAPACITY):
    a, p = np.asarray(actual, float), np.asarray(predicted, float)
    mask = np.asarray(daylight, bool) & np.isfinite(a) & np.isfinite(p)
    a, p = a[mask], p[mask]
    if not len(a):
        return {'n': 0, **{k: None for k in ('nRMSE', 'nMAE', 'nME', 'r', 'CR_pct', 'QR_pct')}}
    error = (p-a)/capacity
    rmse = float(np.sqrt(np.mean(error**2)))
    corr = float(np.corrcoef(a, p)[0, 1]) if np.std(a)>0 and np.std(p)>0 else None
    return {'n': len(a), 'nRMSE': rmse, 'nMAE': float(np.mean(np.abs(error))),
            'nME': float(np.mean(error)), 'r': corr, 'CR_pct': (1-rmse)*100,
            'QR_pct': float(np.mean(np.abs(error)<.25)*100)}


def project(prediction, daylight):
    return np.where(daylight, np.clip(prediction, 0, CAPACITY), 0.0)


def load_data():
    path = ROOT/'data/processed/station08_q1_clean.csv'
    clean = pd.read_csv(path)
    reference = json.loads((ROOT/'results/q1/station08/reference_summary.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == reference['cleaned_data_sha256'], '清洗表与第一问记录版本不一致'
    cleaning = json.loads((ROOT/'results/q1/station08/cleaning_summary.json').read_text())
    assert source_sha256(ROOT/'data/PVOD', 'station08') == cleaning['source_sha256'], '原始输入已变化，需先复核清洗版本'
    times = pd.DatetimeIndex(pd.to_datetime(clean.time_utc, utc=True)).tz_convert('Asia/Shanghai')
    assert times.is_unique and times.is_monotonic_increasing
    clean.index = times
    grid = pd.date_range(times.min().normalize(), times.max().normalize()+pd.Timedelta(hours=23, minutes=45), freq='15min')
    data = clean.reindex(grid)
    meta = pd.read_csv(ROOT/'data/PVOD/metadata.csv').set_index('Station_ID').loc['station08']
    assert float(meta.Capacity)/1000 == CAPACITY
    assumptions = json.loads((ROOT/'docs/q1_reference_assumptions_station08.json').read_text())
    solar, radiation, poa = clear_sky_poa(grid.tz_convert('UTC'), meta, assumptions, 0)
    _, pac = reference_from_poa(poa, 78042*265, CAPACITY*1e6, .96)
    data['reference_mw'] = pac
    data['clear_ghi'] = radiation.ghi.to_numpy()
    data['elevation'] = solar.elevation.to_numpy()
    data['azimuth'] = solar.azimuth.to_numpy()
    data['daylight'] = data.elevation > 0
    data['test'] = test_mask(grid)
    return data


def geometry(data):
    i = data.index
    clock = (i.hour*60+i.minute).to_numpy()/1440
    year = i.dayofyear.to_numpy()/365.25
    return pd.DataFrame({'clear_power': data.reference_mw/CAPACITY,
        'clear_ghi': data.clear_ghi/1000, 'elevation': data.elevation/90,
        'az_sin': np.sin(np.deg2rad(data.azimuth)), 'az_cos': np.cos(np.deg2rad(data.azimuth)),
        'clock_sin': np.sin(2*np.pi*clock), 'clock_cos': np.cos(2*np.pi*clock),
        'year_sin': np.sin(2*np.pi*year), 'year_cos': np.cos(2*np.pi*year)}, index=i)


def weather_features(data):
    x = geometry(data)
    for name in ('globalirrad', 'directirrad', 'temperature', 'humidity', 'windspeed', 'pressure'):
        x['nwp_'+name] = data['nwp_'+name]
    angle = np.deg2rad(data.nwp_winddirection)
    x['nwp_wind_sin'], x['nwp_wind_cos'] = np.sin(angle), np.cos(angle)
    x['nwp_clear_index'] = data.nwp_globalirrad/np.maximum(data.clear_ghi, 20)
    return x


def history_features(data, issue, targets):
    """全部功率输入严格早于issue；四个测试周的功率始终不参与历史输入。"""
    hist = data.loc[(data.index < issue) & (data.index >= issue-pd.Timedelta(days=28)) & ~data.test].copy()
    hist['slot'] = hist.index.hour*4+hist.index.minute//15
    hist['date'] = hist.index.strftime('%Y-%m-%d')
    days = hist.groupby('date').power_clean.agg(['count', 'sum'])
    complete = days.index[days['count'].eq(96)]
    if not len(complete):
        raise ValueError(f'{issue}之前没有完整历史功率日')
    last = hist.loc[hist.date.eq(complete[-1])].set_index('slot').power_clean
    slots = targets.hour*4+targets.minute//15
    recent = hist.loc[hist.index >= issue-pd.Timedelta(days=14)]
    prof = recent.groupby('slot').power_clean.agg(['mean', 'median', 'std'])
    profile = prof.reindex(slots)
    recent7 = hist.loc[hist.index >= issue-pd.Timedelta(days=7)]
    valid = hist.loc[hist.daylight & hist.power_clean.notna() & (hist.reference_mw > .5)]
    scale = np.dot(valid.power_clean, valid.reference_mw)/np.dot(valid.reference_mw, valid.reference_mw)
    x = geometry(data.loc[targets]).copy()
    x['horizon_day'] = (targets.normalize()-issue).days
    x['last_profile'] = last.reindex(slots).to_numpy()/CAPACITY
    x['recent_mean'] = profile['mean'].to_numpy()/CAPACITY
    x['recent_median'] = profile['median'].to_numpy()/CAPACITY
    x['recent_std'] = profile['std'].to_numpy()/CAPACITY
    x['recent_daily_cf'] = recent7.power_clean.mean()/CAPACITY
    x['historical_scale'] = scale
    physical = data.loc[targets].reference_mw.to_numpy()*scale
    baselines = {'persistence': last.reindex(slots).to_numpy(),
                 'climatology': profile['mean'].to_numpy(), 'physical': physical}
    # 可复核输入上界；返回值只用于审计，不作为模型特征。
    return x, baselines, hist.index.max()


def episode(data, issue):
    targets = pd.date_range(issue+pd.Timedelta(days=1), periods=672, freq='15min')
    x, base, last_history = history_features(data, issue, targets)
    weather = weather_features(data.loc[targets])
    full = x.join(weather.loc[:, weather.columns.str.startswith('nwp_')])
    radiation = x.join(weather[['nwp_globalirrad', 'nwp_directirrad', 'nwp_clear_index']])
    info = data.loc[targets, ['power_clean', 'daylight', 'test', 'elevation']].copy()
    info['issue'], info['last_history'] = issue, last_history
    info['horizon_day'] = (targets.normalize()-issue).days
    info['physical'] = base['physical']
    return x, full, radiation, info, base


def train_pool(data):
    blocks = []
    last = data.index.max().normalize()-pd.Timedelta(days=7)
    for issue in pd.date_range(data.index.min().normalize()+pd.Timedelta(days=14), last, freq='3D'):
        x, nwp, rad, info, _ = episode(data, issue)
        blocks.append((x, nwp, rad, info))
    return tuple(pd.concat([b[k] for b in blocks]) for k in range(4))


def fit_tree(x, y, config, seed=SEED):
    model = HistGradientBoostingRegressor(max_iter=180, learning_rate=.05, min_samples_leaf=30,
        early_stopping=False, random_state=seed, **config)
    model.fit(x, y)
    return model


def fit_power_models(pool, cutoff, config_by_name, exclude_dates=(), seed=SEED):
    info = pool[3]
    mask = ~info.test & info.power_clean.notna() & info.daylight
    if cutoff is not None:
        mask &= (info.index < cutoff) & (info.issue < cutoff)
    if exclude_dates:
        mask &= ~info.index.normalize().isin(exclude_dates)
    # 重叠起报使同一个目标可能出现多次：给每个目标相等总权重不在HGB接口中实现，报告重复数。
    residual = (info.power_clean-info.physical)/CAPACITY
    models = {name: fit_tree(pool[k].loc[mask], residual.loc[mask], config_by_name[name], seed)
              for k, name in enumerate(('hist_tree', 'nwp_tree', 'nwp_radiation'))}
    return models, {'training_episode_rows': int(mask.sum()), 'unique_training_times': int(info.index[mask].nunique()),
                    'max_train_target': info.index[mask].max().isoformat(), 'test_labels_in_training': int(info.loc[mask].test.sum())}


def predict_power(models, ep):
    output = {name: project(value, ep[3].daylight) for name, value in ep[4].items()}
    for k, name in enumerate(('hist_tree', 'nwp_tree', 'nwp_radiation')):
        pred = models[name].predict(ep[k])*CAPACITY + ep[3].physical.to_numpy()
        output[name] = project(pred, ep[3].daylight)
    return output


def scene_codes(data):
    """按预报日的白昼晴空指数划分；预先固定阈值，不使用测试实测值。"""
    ratio = data.nwp_globalirrad/np.maximum(data.clear_ghi, 20)
    ratio = ratio.where(data.elevation>10)
    daily = ratio.groupby(data.index.normalize()).mean()
    value = daily.reindex(data.index.normalize()).to_numpy()
    return np.select([value<=.35, value<=.65], ['low', 'medium'], default='high')


def choose_gate(actual, predictions, daylight, codes):
    q2_names = ('persistence', 'climatology', 'physical', 'hist_tree')
    selected = min(q2_names, key=lambda n: metrics(actual, predictions[n], daylight)['nRMSE'])
    weights = {}
    mask = np.asarray(daylight, bool)
    for code in ('all', 'low', 'medium', 'high'):
        valid = mask if code=='all' else mask & (codes==code)
        if valid.sum()<20:
            weights[code] = weights['all']
        else:
            weights[code] = min((0, .25, .5, .75, 1), key=lambda w:
                metrics(actual, (1-w)*predictions[selected]+w*predictions['nwp_tree'], valid)['nRMSE'])
    return selected, weights


def apply_gate(predictions, selected, weights, codes):
    output = dict(predictions)
    output['q2_selected'] = output[selected]
    w = np.array([weights[c] for c in codes])
    output['q3_gate'] = (1-w)*output[selected]+w*output['nwp_tree']
    return output


def local_power_features(data, ghi, temperature):
    x = geometry(data)
    x['local_ghi'], x['local_temperature'] = np.asarray(ghi), np.asarray(temperature)
    return x


def fit_downscaling(data, cutoff, exclude_dates=(), seed=SEED):
    mask = ~data.test & data.power_clean.notna() & data.daylight
    if cutoff is not None:
        mask &= data.index < cutoff
    if exclude_dates:
        mask &= ~data.index.normalize().isin(exclude_dates)
    mask &= data.lmd_totalirrad_clean.notna() & data.lmd_temperature_clean.notna()
    d = data.loc[mask]
    wx = weather_features(d)
    config = {'max_leaf_nodes': 15, 'l2_regularization': 2.0}
    ghi = fit_tree(wx, d.lmd_totalirrad_clean/1000, config, seed)
    temperature = fit_tree(wx, d.lmd_temperature_clean-d.nwp_temperature, config, seed)
    power = fit_tree(local_power_features(d, d.lmd_totalirrad_clean, d.lmd_temperature_clean), d.power_clean/CAPACITY, config, seed)
    bias = {'ghi': float((d.lmd_totalirrad_clean-d.nwp_globalirrad).mean()),
            'temperature': float((d.lmd_temperature_clean-d.nwp_temperature).mean())}
    return (ghi, temperature, power, bias), {'local_training_points': len(d), 'max_local_training_time': d.index.max().isoformat()}


def predict_downscaling(models, data):
    gm, tm, pm, bias = models
    wx = weather_features(data)
    ghi = np.maximum(gm.predict(wx)*1000, 0)
    temp = tm.predict(wx)+data.nwp_temperature.to_numpy()
    candidates = {'q4_raw_control': (data.nwp_globalirrad, data.nwp_temperature),
                  'q4_bias': (np.maximum(data.nwp_globalirrad+bias['ghi'], 0), data.nwp_temperature+bias['temperature']),
                  'q4_local': (ghi, temp)}
    output = {name: project(pm.predict(local_power_features(data, g, t))*CAPACITY, data.daylight)
              for name, (g, t) in candidates.items()}
    return output, ghi, temp


def validation_and_test(data, pool, start):
    issue = start-pd.Timedelta(days=1)
    val_issue = issue-pd.Timedelta(days=8)
    val = episode(data, val_issue)
    valid_target = ~val[3].test & val[3].power_clean.notna()
    val = tuple(item.loc[valid_target] if isinstance(item, pd.DataFrame) else
                {k: v[np.asarray(valid_target)] for k,v in item.items()} for item in val)
    configs = {}
    validation_rows = []
    for config in CONFIGS:
        models, _ = fit_power_models(pool, val_issue, {name: config for name in ('hist_tree', 'nwp_tree', 'nwp_radiation')})
        pred = predict_power(models, val)
        validation_rows.extend({'week': start.strftime('%Y-%m'), 'config': config, 'model': name,
            **metrics(val[3].power_clean, pred[name], val[3].daylight)} for name in ('hist_tree','nwp_tree','nwp_radiation'))
    for name in ('hist_tree','nwp_tree','nwp_radiation'):
        candidates = [r for r in validation_rows if r['model']==name]
        configs[name] = min(candidates, key=lambda r:r['nRMSE'])['config']
    models, _ = fit_power_models(pool, val_issue, configs)
    vpred = predict_power(models, val)
    codes = scene_codes(data.loc[val[3].index])
    selected, weights = choose_gate(val[3].power_clean, vpred, val[3].daylight, codes)
    # 拟合最终模型前验证集归回可用历史，保持测试标签永不参与。
    models, audit = fit_power_models(pool, issue, configs)
    ep = episode(data, issue)
    pred = apply_gate(predict_power(models, ep), selected, weights, scene_codes(data.loc[ep[3].index]))
    downs, audit_local = fit_downscaling(data, issue)
    q4, ghi, temp = predict_downscaling(downs, data.loc[ep[3].index])
    pred.update(q4)
    audit.update(audit_local)
    audit.update({'week': start.strftime('%Y-%m'), 'issue': issue.isoformat(), 'validation_issue': val_issue.isoformat(),
        'validation_points': len(val[3]), 'validation_last_target': val[3].index.max().isoformat(),
        'history_last_timestamp': ep[3].last_history.iloc[0].isoformat(), 'q2_selected': selected,
        'gate_weights': weights, 'tree_configs': configs})
    assert pd.Timestamp(audit['max_train_target']) < issue
    assert pd.Timestamp(audit['max_local_training_time']) < issue
    assert pd.Timestamp(audit['history_last_timestamp']) < issue
    assert ep[3].test.all() and len(ep[3])==672 and ep[3].power_clean.notna().all()
    return ep, pred, ghi, temp, audit, validation_rows


def result_rows(predictions, info, protocol):
    rows = []
    codes = info.scene.to_numpy()
    for model, values in predictions.items():
        groups = [('overall', 'all', np.ones(len(info), bool))]
        groups += [('month', month, (info.week==month).to_numpy()) for month in info.week.unique()]
        groups += [('horizon', str(h), (info.horizon_day==h).to_numpy()) for h in range(1,8)]
        groups += [('scene', code, codes==code) for code in ('low','medium','high')]
        for kind, group, mask in groups:
            rows.append({'protocol': protocol, 'model': model, 'group_type': kind, 'group': group,
                         **metrics(info.power_clean, values, info.daylight.to_numpy() & mask)})
    return rows


def bootstrap_improvement(info, first, second, name):
    """28个日期为独立单元，在每个7天测试周内重抽日期；不给15分钟点伪造独立性。"""
    d = pd.DataFrame({'date': info.index.strftime('%Y-%m-%d'), 'week': info.week,
        'e1': ((np.asarray(first)-info.power_clean)/CAPACITY)**2,
        'e2': ((np.asarray(second)-info.power_clean)/CAPACITY)**2,
        'daylight': info.daylight}).loc[info.daylight]
    daily = d.groupby(['week','date']).agg(e1=('e1','sum'), e2=('e2','sum'), n=('e1','size'))
    rng = np.random.default_rng(SEED)
    weeks = [g.to_numpy() for _,g in daily.groupby(level=0)]
    delta = []
    for _ in range(2000):
        sample = np.concatenate([w[rng.integers(0,len(w),len(w))] for w in weeks])
        mse1, mse2, n = sample.sum(axis=0)
        delta.append(np.sqrt(mse1/n)-np.sqrt(mse2/n))
    delta = np.array(delta)
    point = metrics(info.power_clean, first, info.daylight)['nRMSE']-metrics(info.power_clean, second, info.daylight)['nRMSE']
    return {'comparison': name, 'n_dates': len(daily), 'delta_nRMSE_first_minus_second': point,
            'ci95_low': float(np.quantile(delta,.025)), 'ci95_high': float(np.quantile(delta,.975)),
            'bootstrap_samples': 2000, 'scope': '仅四个固定测试周，按周内日期分层重抽，不代表全年或跨站推断'}


def draw_summary(info, predictions, out):
    fonts = {f.name for f in font_manager.fontManager.ttflist}
    plt.rcParams['font.family'] = next((f for f in ('PingFang HK','Songti SC','Heiti TC','SimHei') if f in fonts),'DejaVu Sans')
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(3,2,figsize=(15,12))
    for ax, week in zip(axes[:2].flat, info.week.unique()):
        mask = info.week.eq(week)
        # 显示固定周的第一日；全周逐点结果在证据包，避免挤成无法读的图。
        mask &= info.index.normalize()==info.index[mask][0].normalize()
        x = info.index[mask].hour+info.index[mask].minute/60
        ax.plot(x, info.loc[mask,'power_clean'], color='#222222',label='实测',linewidth=1.8)
        for name,color in [('q2_selected','#ac7a34'),('nwp_tree','#28689e'),('q4_local','#4c8262')]:
            ax.plot(x,np.asarray(predictions[name])[mask],label=MODEL_NAMES[name],color=color,linewidth=1.3)
        ax.set_title(f'{week}测试周首日（北京时间）')
        ax.set(xlabel='本地时刻（h）',ylabel='功率（MW）',xlim=(0,24),ylim=(0,20))
        ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=9)
    selected = ('persistence','climatology','physical','hist_tree','q2_selected','nwp_radiation','nwp_tree','q3_gate','q4_raw_control','q4_bias','q4_local')
    scores = [metrics(info.power_clean,predictions[n],info.daylight)['nRMSE'] for n in selected]
    axes[2,0].barh([MODEL_NAMES[n] for n in selected],scores,color='#28689e')
    axes[2,0].invert_yaxis();axes[2,0].set_xlabel('白昼容量归一化RMSE（越小越好）')
    for j,score in enumerate(scores): axes[2,0].text(score+.002,j,f'{score:.3f}',va='center',fontsize=8)
    axes[2,0].set_xlim(0,max(scores)*1.25)
    for name,color in [('q2_selected','#ac7a34'),('nwp_tree','#28689e'),('q4_local','#4c8262')]:
        scores = [metrics(info.power_clean,predictions[name],info.daylight & info.horizon_day.eq(h))['nRMSE'] for h in range(1,8)]
        axes[2,1].plot(range(1,8),scores,'o-',label=MODEL_NAMES[name],color=color)
    axes[2,1].set(xlabel='目标日序号（起报次日起1—7）',ylabel='白昼容量归一化RMSE')
    axes[2,1].legend(fontsize=9);axes[2,1].grid(alpha=.2)
    fig.suptitle('station08：问题2—4向前回测与局地气象订正',fontsize=17)
    fig.text(.03,.015,'固定起报七天；历史输入与训练标签早于起报。NWP版本可用性未核实；单点订正不证明细网格重建。',fontsize=10)
    fig.tight_layout(rect=(0,.04,1,.97));fig.savefig(out,dpi=300);plt.close(fig)


def md_table(records, columns, rename=None):
    frame = pd.DataFrame(records)[columns].rename(columns=rename or {})
    def fmt(value):
        if value is None or (isinstance(value,float) and not np.isfinite(value)): return '—'
        if isinstance(value,(float,np.floating)): return f'{value:.4f}'
        return str(value)
    return '\n'.join(['| '+' | '.join(frame.columns)+' |','| '+' | '.join(['---']*len(frame.columns))+' |']+
        ['| '+' | '.join(fmt(v) for v in r)+' |' for r in frame.itertuples(index=False,name=None)])


def report(info, predictions, summary, path):
    rows = summary['metrics']
    overall = [dict(r,model=MODEL_NAMES[r['model']]) for r in rows if r['protocol']=='forward' and r['group_type']=='overall']
    retrospective = [dict(r,model=MODEL_NAMES[r['model']]) for r in rows if r['protocol']=='retrospective' and r['group_type']=='overall']
    score = {r['model']:r for r in rows if r['protocol']=='forward' and r['group_type']=='overall'}
    q2, q3, q4 = [score[n]['nRMSE'] for n in ('q2_selected','nwp_tree','q4_local')]
    delta3, delta4 = (q2-q3)/q2*100, (score['q4_raw_control']['nRMSE']-q4)/score['q4_raw_control']['nRMSE']*100
    monthly = [r for r in rows if r['protocol']=='forward' and r['group_type']=='month' and r['model'] in ('q2_selected','nwp_tree','q3_gate','q4_raw_control','q4_local')]
    scenes = [dict(r, model=MODEL_NAMES[r['model']]) for r in rows if r['protocol']=='forward' and r['group_type']=='scene' and r['model'] in ('q2_selected','nwp_tree','q3_gate','q4_local')]
    horizons = [dict(r, model=MODEL_NAMES[r['model']]) for r in rows if r['protocol']=='forward' and r['group_type']=='horizon' and r['model'] in ('q2_selected','nwp_tree','q4_local')]
    rank = {'model':'模型','n':'白昼样本','nRMSE':'归一RMSE','nMAE':'归一MAE','nME':'归一ME','CR_pct':'CR(%)','QR_pct':'QR(%)'}
    table = md_table(overall,['model','n','nRMSE','nMAE','nME','r','CR_pct','QR_pct'],rank)
    checks = summary['checks']
    result3 = '降低' if delta3>=0 else '增加'
    result4 = '降低' if delta4>=0 else '增加'
    winner = min(score,key=lambda k:score[k]['nRMSE'])
    scene_lookup = {(r['group'], r['model']): r for r in rows if r['protocol']=='forward' and r['group_type']=='scene'}
    scene_lines = []
    for code in ('low', 'medium', 'high'):
        first, second = scene_lookup[(code,'q2_selected')], scene_lookup[(code,'nwp_tree')]
        if first['n']:
            gain = (first['nRMSE']-second['nRMSE'])/first['nRMSE']*100
            scene_lines.append(f"{code}档（{first['n']}点）：{first['nRMSE']:.4f}→{second['nRMSE']:.4f}，相对变化{-gain:+.2f}%")
    scene_analysis = '；'.join(scene_lines)+'。负百分数表示误差降低。场景融合总体RMSE为'+f"{score['q3_gate']['nRMSE']:.4f}"+'，没有超过直接全字段NWP模型，不能据此宣称场景门控必然更优。低档样本较少，场景结论限于本次测试。'
    month_lookup = {(r['group'], r['model']): r for r in monthly}
    month_lines = []
    for month in info.week.unique():
        first, second = month_lookup[(month,'q2_selected')], month_lookup[(month,'nwp_tree')]
        gain = (first['nRMSE']-second['nRMSE'])/first['nRMSE']*100
        month_lines.append(f"{month}相对变化{-gain:+.2f}%")
    month_analysis = '；'.join(month_lines)+'。该现象说明不能把总体改善写成各季节均改善。'
    q4_analysis = f"向前回测非线性订正RMSE={q4:.4f}，原始气象对照={score['q4_raw_control']['nRMSE']:.4f}，总体未改善；均值订正为{score['q4_bias']['nRMSE']:.4f}，同样没有改善。GHI的MAE变小但RMSE变大，说明平均绝对偏差改善不足以保证大误差尾部改善；这与早期样本少、非线性外推及两阶段输入分布变化相容，但尚未证明唯一原因。气象订正后总体功率也未超过Q3，不能称为空间降尺度成功。"
    retro_lookup = {r['model']:r for r in rows if r['protocol']=='retrospective' and r['group_type']=='overall'}
    retro_analysis = f"离线对照中，Q4原始气象RMSE={retro_lookup['q4_raw_control']['nRMSE']:.4f}，非线性订正={retro_lookup['q4_local']['nRMSE']:.4f}。离线结果与向前结果不同，更多日期用于拟合可能影响分布覆盖；它无法证明过去起报时已经可以获得这些未来训练样本，故不作为运行收益证据。"
    ci = summary['bootstrap'][0]
    significance = f"NWP相对第二问的RMSE差为{ci['delta_nRMSE_first_minus_second']:.4f}，区间[{ci['ci95_low']:.4f}, {ci['ci95_high']:.4f}]跨0。因此可以报告本次测试点估计改善，但不能声称已经在日期层面证明稳定显著收益。"
    text = rf'''# station08问题2、3、4：C交接总结与论文初稿

整理日期：2026-10-14。用途：建模练习、数字复核与正文整理；尚不能宣称完成真实NWP版本可用性及细网格空间验证。

## 给C的交接说明

本次核心交付只有`src/q234_forecast.py`和本稿。逐点预测、指标表、配置、输入与源代码哈希集中在`results/q234/station08/证据包.npz`，图集中为一张`汇总图.png`。不新增清洗表，不生成散落的模型文件和重复报告。问题1稿件保留，需由C合并已有第一问与本稿；旧报告已清理；本次建模的数字以证据包为准，C的待办统一见根目录`C剩余任务.md`。

```bash
OMP_NUM_THREADS=2 .venv/bin/python src/q234_forecast.py
.venv/bin/python src/q234_forecast.py --inspect
.venv/bin/python src/q234_forecast.py --export-table2 /指定位置/表2.csv
.venv/bin/python -m unittest discover -s tests -v
```

第三条只在需要比赛附件时生成CSV：包含四周全部2688条记录、每周固定起报时间、目标时间、实测及各方法预测。起报时间为目标周开始前一日00:00，目标范围为起报24至191.75小时，七天内不更新功率输入。表2样例存在每日不同起报，本稿采用题目文字允许的七天固定起报实验；如果团队决定每日滚动24—48小时，应单独重做该口径，不把两种实验混写。

## 摘要可用素材（与正式摘要分开）

在station08四个规定测试周、{int(info.daylight.sum())}个白昼样本上，历史功率验证选优模型归一化RMSE为{q2:.4f}；加入NWP后为{q3:.4f}，相对前者{result3}{abs(delta3):.2f}%。单站非线性局地气象订正为{q4:.4f}，相对同功率映射的原始气象对照{result4}{abs(delta4):.2f}%。所有模型按规定测试周评分；向前实验训练和历史输入早于起报，测试标签不参与训练或选参。这些结果只能用于给定数据与信息假设的回测，NWP是否在起报时覆盖全部七天仍待核验。

## 1 题目、数据与统一评价

题目第二问要求仅根据历史功率预测；第三问加入NWP并验证有效场景；第四问检验空间降尺度。数据为PVOD station08（36.70761°N、113.89999°E，朝南33°，容量20 MW），沿用已清洗的`data/processed/station08_q1_clean.csv`和第一问参考假设。原始UTC转北京时间；2018-07-01至2019-06-13，共33120个实测点、345个完整日，缺2018-11-11至11-13整3日，不补零。全部日期网格用于太阳几何计算，缺测标签始终不训练、不评分。

按本地自然月末7日，测试为2018-08-25—08-31、2018-11-24—11-30、2019-02-22—02-28、2019-05-25—05-31，各672点，共2688点；白昼采用几何太阳高度角>0，不用实际功率决定白昼。其余日期为候选训练集。第一问25°C晴空参考只提供确定性的太阳几何基线，实际温度不被冒充为未来组件温度。

**两种评价协议必须区分。** 向前协议在每个起报时刻只用此前的非测试标签训练；它少于“其余日期全部训练”，用于核对时间因果关系。补充离线协议使用整个数据范围的非测试日期训练，符合题目静态划分，但训练中可以存在晚于早期测试周的日期，所以不能当成真实向前预测能力。两者测试范围相同，均永久排除四周功率作为模型标签或历史输入。

NWP只有有效时间行，没有发行时刻、预报版本、提前量或邻域格点坐标；计算假设对应NWP列已在该次起报时可获得。因此第3/4问应称**NWP可用性假设下的回测**，不能宣称已证明完整七天运行预报。作者仓库可核实NWP与现场测量字段分类，但未提供本次输入中的版本索引[1]。

容量归一化误差定义$e_i=(\widehat P_i-P_i)/C$，$C=20$ MW：

$$E_{{rmse}}= \sqrt{{n^{{-1}}\sum_i e_i^2}},\qquad E_{{mae}}=n^{{-1}}\sum_i|e_i|,\qquad E_{{me}}=n^{{-1}}\sum_i e_i.$$

$$CR=(1-E_{{rmse}})\times100\%,\qquad QR=n^{{-1}}\sum_i\mathbf1(|e_i|<0.25)\times100\%.$$

另报告Pearson相关系数。附件1的容量符号是开机容量；当前没有开机容量记录，20 MW是装机容量代替开机容量的明确假设。原附件第一段符号解释与相关公式段对实际/预测符号有冲突，本稿明确ME正值表示预测偏高，避免符号混淆。CR和QR都按百分数报告，QR严格小于0.25。指标不能与第一问“实际相对晴空参考的偏差”混用。

## 2 第二问：仅历史功率预测

### 2.1 模型与输入

考虑三类方法：持续性与近14日同刻均值易解释，作为朴素基线；晴空比例提供确定日周期；梯度提升树学习历史状态与季节残差，复杂度可控。深度神经网络因有效观测不足一年、最早测试周训练样本少，本次不采用。

持续性重复起报前最后一个完整非测试日的96点；气候态为起报前14天非测试日同刻功率均值，缺日不加入分母；晴空比例系数由起报前28天有效白昼功率和参考功率作过原点最小二乘：

$$a(o)=\frac{{\sum_{{t<o}}P_tP_{{cs,t}}}}{{\sum_{{t<o}}P_{{cs,t}}^2}},\qquad \widehat P_{{phys,t}}=a(o)P_{{cs,t}}.$$

太阳高度角、方位角、时刻和年内周期编码、参考功率、目标日序号，加上最后完整日同刻功率、14日同刻均值/中位数/标准差、最近7日平均功率与历史晴空系数，形成特征向量$x_{{o,t}}$。历史功率全部早于$o$，七天目标日共用起报时历史，不进行真值递推。第二问没有NWP和现场气象输入。

以物理基线残差为回归目标：

$$\widehat P_{{2,t}}=\Pi_{{[0,C]}}\left[a(o)P_{{cs,t}}+C f_2(x_{{o,t}})\right].$$

其中$f_2$为直方图梯度提升树。所有模型夜间输出置0，白昼输出投影至[0,20] MW。这里只裁剪预测，没有改变真实评分功率。

### 2.2 训练与选参

候选历史起报从首日后14天开始、每3天一次，每次生成七天目标。首段历史不足的日期不作为残差树训练目标，仍可用作历史输入；“其余日期”是候选标签集，并非每个日期都能构造足够历史的七天训练样本。训练标签排除缺失、夜间及四个测试周。一个目标可能对应多个起报提前量，属于直接多步训练而非独立样本；显著性检验不把这些重复目标当独立证据。验证起报为测试起报前8天，验证目标为其后第1—7天，验证模型只用验证起报之前标签训练。

树参数：学习率0.05、180轮、叶节点候选7/15、叶子最少30样本、L2=2、随机种子{SEED}、关闭随机内部早停。各方法按独立验证周白昼RMSE选叶节点，第二问主方案由四个历史候选模型按验证RMSE选优。测试真值完全不参与选参。最终向前拟合纳入测试起报前的验证标签，仍不纳入任何测试周标签。

### 2.3 数值结果

{table}

上表同时包含第三、四问以方便交接统一复核。不能因为测试表中某个候选较好就回头替换验证选优规则；本次全表最低为{MODEL_NAMES[winner]}，这只是固定测试样本的事后描述。验证选优方案没有在总体测试中超过全部简单基线；晴空比例为{score['physical']['nRMSE']:.4f}，历史树模型为{score['hist_tree']['nRMSE']:.4f}，说明仅靠历史信息时增加非线性复杂度并不必然提高精度。

## 3 第三问：NWP融合及场景验证

### 3.1 融合与消融

在第二问相同历史特征与残差目标上增加NWP全球辐照、直射辐照、气温、湿度、风速、压力、风向正余弦和预报晴空指数，得到$f_3$。NWP原始列不是未来现场测量。辐照消融只加全球/直射辐照和预报晴空指数，其余结构一致；比较它与全字段模型可以检查非辐照信息是否带来额外收益。

### 3.2 场景划分及融合

对目标自然日太阳高度角>10°的预报点，计算$k_d=mean(G_{{NWP}}/G_{{cs}})$，分母至少20 W/m²。预先固定低辐照($k_d\le0.35$)、中辐照($0.35<k_d\le0.65$)、高辐照($k_d>0.65$)三类。场景只依赖该日预报与太阳几何，不读取当日功率或现场天气。这些名称是预报辐照档，不应直接写成已确认阴雨/云/雾类别。

场景融合为$\widehat P_s=(1-w_s)\widehat P_2+w_s\widehat P_3$，$w_s$从0、0.25、0.5、0.75、1中按验证误差选择；若某类验证白昼点不足20，则沿用总体最优权重。允许不启用NWP，避免预设融合必然有效。

{md_table(scenes,['model','group','n','nRMSE','nMAE'],dict(rank,group='预报辐照档'))}

{scene_analysis}

证据包可查看各场景权重、验证样本数与分月结果。若某类无测试样本，显示空值，不虚构验证结论；场景改善与总体改善均应按数值及下面日块重抽区间解释。

### 3.3 分月结果

{md_table([dict(r,model=MODEL_NAMES[r['model']]) for r in monthly],['group','model','n','nRMSE','QR_pct'],dict(rank,group='测试月'))}

{month_analysis}

## 4 第四问：从NWP到电站局地气象的统计映射

### 4.1 可验证范围

当前只有单站NWP序列与对应现场测量，没有NWP网格间距、原始格点坐标及邻域场，不能做双线性/IDW插值，也不能展示真实1km→100m的空间分辨率提升。这里实现单点统计降尺度的有限形式，即“模式尺度预报量→电站测点气象”的回归订正，验证其对站点功率回测的作用。严格细网格空间降尺度仍未完成，正文和摘要必须保留此边界。

### 4.2 双阶段方法和对照

只用训练时段现场辐照与气温作为标签，学习$D_G(NWP,solar)$和$D_T(NWP,solar)$；辐照目标单位按1000 W/m²缩放，温度学习现场气温减NWP气温的残差。两者采用15叶、180轮的固定提升树。随后只用训练时段真实局地辐照、气温与太阳几何学习相同的功率映射$F$：

$$\widehat P_{{raw}}=F(G_{{NWP}},T_{{NWP}},solar),\quad
\widehat P_{{bias}}=F(G_{{NWP}}+\overline{{G_{{obs}}-G_{{NWP}}}},T_{{NWP}}+\overline{{T_{{obs}}-T_{{NWP}}}},solar),$$

$$\widehat P_{{local}}=F(D_G(NWP,solar),T_{{NWP}}+D_T(NWP,solar),solar).$$

同一$F$用于三组，原始气象对照隔离映射输入订正带来的增益；均值订正隔离简单偏差修正与非线性效应。测试时没有真实局地辐照或气温作为预测输入，现场测量只在生成预测后用于独立气象误差评价。同时与第三问强基线比较，避免用弱对照掩盖两阶段模型的整体效果。

{md_table(summary['weather_metrics'],['variable','input','n','RMSE','MAE'],{'variable':'现场标签','input':'气象输入','n':'白昼点','RMSE':'RMSE(原单位)','MAE':'MAE(原单位)'})}

{q4_analysis}

气象映射可用于拟合给定样本中的条件偏差，但不产生未观测的云场空间结构；即使功率误差降低，也不能归因为恢复次网格云影位置或识别具体故障。

## 5 检验与适用边界

### 5.1 配对日期块检验

比较采用四个测试周内按日期分层重抽，共2000次，统计第一模型RMSE减第二模型RMSE的95%分位区间；正值表示第二模型较好，跨0表示证据不足。独立单元是28个日期，而非大量相互相关的15分钟点。区间条件于四个固定测试周，不能外推为全年显著性。相邻日期仍可能存在持续天气相关，且每次仅有一个验证周，区间和模型选择稳定性均需更多独立日期复核。

{md_table(summary['bootstrap'],['comparison','n_dates','delta_nRMSE_first_minus_second','ci95_low','ci95_high'],{'comparison':'第一→第二','n_dates':'日期数','delta_nRMSE_first_minus_second':'RMSE差','ci95_low':'区间下界','ci95_high':'区间上界'})}

{significance}

### 5.2 提前量与白昼口径

{md_table(horizons,['model','group','n','nRMSE'],dict(rank,group='目标日序号'))}

每个序号在四个测试周只有4个目标日，不足以证明误差必须随提前量单调增长；NWP行又未按提前量存档，因此该表也是固定目标周的样本比较。

{md_table(summary['daylight_sensitivity'],['model','solar_threshold_deg','n','nRMSE'],dict(rank,solar_threshold_deg='太阳高度阈值(°)'))}

0°为正式评分口径，5°只作敏感性。降低RMSE可能只是删除低太阳高度角样本，不能叫模型改进。

### 5.3 离线题目划分对照

{md_table(retrospective,['model','n','nRMSE','nMAE','CR_pct','QR_pct'],rank)}

离线对照训练使用整段非测试日期（包括部分早期测试之后的日期），树模型固定采用向前验证选得的末次配置，第二问方案及融合权重保留对应起报之前的验证选择。它有全时段日历信息，但没有测试功率标签/现场测量作为测试预测特征，不与向前结果混成一张准确率结论。

{retro_analysis}

### 5.4 样本与泄漏核对

{md_table(summary['audits'],['week','issue','max_train_target','unique_training_times','history_last_timestamp','q2_selected'],{'week':'测试月','issue':'起报','max_train_target':'最晚训练标签','unique_training_times':'唯一训练点','history_last_timestamp':'最晚历史输入','q2_selected':'第二问验证选择'})}

检查结果：{json.dumps(checks,ensure_ascii=False)}。

## 6 结论、未决项与C整理清单

第二问已经完成历史基线、残差树模型及验证选优；第三问已经完成NWP字段消融、预报场景划分与验证融合；第四问已经完成单站气象统计映射的有限实证，但未获得多格点空间场。是否改善只能依据上述表格和区间，不把“模型更复杂”当成结论。

向前总体结果：Q2={q2:.4f}，Q3={q3:.4f}，Q4={q4:.4f}；第3问相对Q2{result3}{abs(delta3):.2f}%，第4问相对同功率映射的原始气象对照{result4}{abs(delta4):.2f}%。第4问若未超过第三问，则应明确两阶段误差传播及映射分布变化的可能影响，而不能只报对照增益。

C整理时应保留：装机容量替代开机容量、ME符号约定、白昼定义、固定起报实验、跨年不完整观测、NWP发布时间与七天版本待核实、单点订正与细网格空间降尺度的区别。数据不足一年与3个缺日不因完成预测而消失。预报场景不能当真实天气分类；提升树重要性也不能当因果归因。本稿由AI辅助实现及起草，团队应复核方法与数字并按适用赛事要求披露。

建议正文结构：把本稿第2节整合为第二问，第3节为第三问，第4节为第四问，第1/5节作为共享评价与模型检验。不要复制旧报告中的不同样本数、旧实验或未经核实的故障解释。若要完成严格第四问，下一步需要同期邻近格点NWP坐标、空间分辨率及发行版本；不能把其他电站的站点NWP冒充规则网格。

![汇总图](../results/q234/station08/汇总图.png)

## 参考与运行信息

[1] Yao T, Wang J, Wu H, et al. A photovoltaic power output dataset: Multi-source photovoltaic power output dataset with Python toolkit. Solar Energy, 2021, 230:122–130. DOI:10.1016/j.solener.2021.09.050；[作者仓库](https://github.com/yaotc/PVODataset)。本次核实字段说明，访问日期2026-10-14。

[2] scikit-learn开发者。[HistGradientBoostingRegressor官方接口](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)。访问日期2026-10-14。

[3] 本地原题`docs/B题 光伏电站发电功率日前预测问题.pdf`与`docs/附件1 误差分析方法.pdf`；附件公式已视觉复核。

运行版本：{json.dumps(summary['versions'],ensure_ascii=False)}；固定随机种子{SEED}。源代码、清洗表、参数及题目哈希见证据包metadata，全部数字与逐点预测同包保存，可用`--inspect`复核。
'''
    path.write_text(text,encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect',action='store_true')
    parser.add_argument('--export-table2',type=Path)
    args = parser.parse_args()
    out = ROOT/'results/q234/station08'
    bundle_path = out/'证据包.npz'
    if args.inspect or args.export_table2:
        with np.load(bundle_path,allow_pickle=False) as bundle:
            summary = json.loads(str(bundle['metadata_json']))
            if args.inspect:
                print(json.dumps({k:summary[k] for k in ('versions','audits','checks','bootstrap')},ensure_ascii=False,indent=2))
            if args.export_table2:
                table = pd.DataFrame({'起报时间':bundle['issue_time'], '预报时间':bundle['target_time'],
                    '实际功率(MW)':bundle['actual_mw']})
                for name in bundle['model_names']:
                    table[MODEL_NAMES[str(name)]+'(MW)'] = bundle['forward_'+str(name)]
                args.export_table2.parent.mkdir(parents=True,exist_ok=True)
                table.to_csv(args.export_table2,index=False,encoding='utf-8-sig')
                print(f'已导出{len(table)}条预测：{args.export_table2}')
        return
    began = time.perf_counter()
    data = load_data()
    print('输入加载完成；建立严格起报历史特征。',flush=True)
    pool = train_pool(data)
    starts = data.loc[data.test].groupby(data.loc[data.test].index.strftime('%Y-%m')).apply(lambda g:g.index.min()).tolist()
    records, predictions, ghis, temps, audits, validations = [], [], [], [], [], []
    with threadpool_limits(limits=2):
        for start in starts:
            print(f'向前回测 {start:%Y-%m}：验证、选参和冻结七天预测。',flush=True)
            ep, pred, ghi, temp, audit, validation = validation_and_test(data,pool,start)
            info = ep[3].copy()
            info['week'] = start.strftime('%Y-%m')
            info['scene'] = scene_codes(data.loc[info.index])
            records.append(info);predictions.append(pred);ghis.append(ghi);temps.append(temp)
            audits.append(audit);validations.extend(validation)
        info = pd.concat(records)
        forward = {n:np.concatenate([p[n] for p in predictions]) for n in predictions[0]}
        print('向前回测完成；计算题目静态划分离线对照。',flush=True)
        configs = audits[-1]['tree_configs']
        retro_models, retro_audit = fit_power_models(pool,None,configs)
        retro_downs, retro_local_audit = fit_downscaling(data,None)
        retrospective = []
        for start, audit in zip(starts, audits):
            ep = episode(data,start-pd.Timedelta(days=1))
            pred = apply_gate(predict_power(retro_models,ep),audit['q2_selected'],audit['gate_weights'],scene_codes(data.loc[ep[3].index]))
            pred.update(predict_downscaling(retro_downs,data.loc[ep[3].index])[0])
            retrospective.append(pred)
        retro = {n:np.concatenate([p[n] for p in retrospective]) for n in retrospective[0]}
    rows = result_rows(forward,info,'forward')+result_rows(retro,info,'retrospective')
    weather_rows = []
    target = data.loc[info.index]
    for variable, raw, mapped, actual in [
        ('GHI(W/m²)',target.nwp_globalirrad,np.concatenate(ghis),target.lmd_totalirrad_clean),
        ('气温(°C)',target.nwp_temperature,np.concatenate(temps),target.lmd_temperature_clean)]:
        for name,pred in [('原始NWP',raw),('非线性局地订正',mapped)]:
            mask = target.daylight & np.isfinite(actual) & np.isfinite(pred)
            delta = np.asarray(pred)[mask]-actual[mask].to_numpy()
            weather_rows.append({'variable':variable,'input':name,'n':int(mask.sum()),'RMSE':float(np.sqrt(np.mean(delta**2))),'MAE':float(np.mean(np.abs(delta)))})
    boot = [bootstrap_improvement(info,forward[a],forward[b],f'{MODEL_NAMES[a]}→{MODEL_NAMES[b]}') for a,b in
        [('q2_selected','nwp_tree'),('q2_selected','q3_gate'),('q4_raw_control','q4_local'),('nwp_tree','q4_local')]]
    sensitivity = [{'model':MODEL_NAMES[name],'solar_threshold_deg':threshold,
        **metrics(info.power_clean,forward[name],info.elevation>threshold)}
        for name in ('q2_selected','nwp_tree','q4_local') for threshold in (0,5)]
    checks = {'test_points':len(info),'each_week_672':bool(info.groupby('week').size().eq(672).all()),
        'actual_no_missing':bool(info.power_clean.notna().all()),
        'all_forward_training_before_issue':all(pd.Timestamp(a['max_train_target'])<pd.Timestamp(a['issue']) for a in audits),
        'test_training_labels':sum(a['test_labels_in_training'] for a in audits)+retro_audit['test_labels_in_training'],
        'predictions_finite_and_in_capacity':all(np.isfinite(v).all() and (v>=0).all() and (v<=CAPACITY).all() for v in (*forward.values(),*retro.values())),
        'all_night_predictions_zero':all((v[~info.daylight.to_numpy()]==0).all() for v in (*forward.values(),*retro.values())),
        'nwp_issue_availability_verified':False,'multigrid_spatial_downscaling_verified':False}
    assert checks['test_points']==2688 and checks['each_week_672'] and checks['actual_no_missing']
    assert checks['all_forward_training_before_issue'] and checks['test_training_labels']==0
    assert checks['predictions_finite_and_in_capacity'] and checks['all_night_predictions_zero']
    inputs = [Path(__file__),ROOT/'data/processed/station08_q1_clean.csv',ROOT/'data/PVOD/metadata.csv',
        ROOT/'docs/q1_reference_assumptions_station08.json',ROOT/'docs/B题 光伏电站发电功率日前预测问题.pdf',ROOT/'docs/附件1 误差分析方法.pdf',
        ROOT/'requirements.txt',ROOT/'requirements-lock.txt',ROOT/'src/q1_check_data.py',ROOT/'src/q1_reference_power.py',
        ROOT/'results/q1/station08/cleaning_summary.json',ROOT/'results/q1/station08/reference_summary.json',
        ROOT/'docs/q1_cleaning_rules_station08.json',ROOT/'tests/test_q234_forecast.py']
    summary = {'version':'q234-station08-v1','date':'2026-10-14','station':'station08','capacity_mw':CAPACITY,
        'seed':SEED,'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__,'pvlib':pvlib.__version__},
        'metrics':rows,'audits':audits,'validation':validations,'retrospective_audit':dict(retro_audit,**retro_local_audit),
        'weather_metrics':weather_rows,'bootstrap':boot,'daylight_sensitivity':sensitivity,'checks':checks,
        'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'wall_seconds':time.perf_counter()-began}
    out.mkdir(parents=True,exist_ok=True)
    arrays = {'metadata_json':np.array(json.dumps(summary,ensure_ascii=False)),
        'model_names':np.array(list(forward)),'issue_time':info.issue.astype(str).to_numpy(dtype=str),
        'target_time':info.index.astype(str).to_numpy(dtype=str),'actual_mw':info.power_clean.to_numpy(),
        'daylight':info.daylight.to_numpy(),'scene':info.scene.to_numpy(dtype=str),'horizon_day':info.horizon_day.to_numpy(),
        'elevation_deg':info.elevation.to_numpy(), 'week':info.week.to_numpy(dtype=str),
        'actual_ghi_wm2':target.lmd_totalirrad_clean.to_numpy(), 'actual_temperature_c':target.lmd_temperature_clean.to_numpy(),
        'raw_ghi_wm2':target.nwp_globalirrad.to_numpy(), 'raw_temperature_c':target.nwp_temperature.to_numpy(),
        'mapped_ghi_wm2':np.concatenate(ghis),'mapped_temperature_c':np.concatenate(temps)}
    arrays.update({'forward_'+n:v for n,v in forward.items()})
    arrays.update({'retrospective_'+n:v for n,v in retro.items()})
    np.savez_compressed(bundle_path,**arrays)
    draw_summary(info,forward,out/'汇总图.png')
    draft = ROOT/'paper/第2至4问_station08_C交接初稿.md'
    report(info,forward,summary,draft)
    print(json.dumps({'draft':str(draft),'wall_seconds':summary['wall_seconds'],
        'overall':[r for r in rows if r['protocol']=='forward' and r['group_type']=='overall'], 'checks':checks},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
