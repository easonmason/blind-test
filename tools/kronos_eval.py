# Kronos 保留期實測（事前登錄，2026-11-01；跑之前寫死，跑完不准改參數再跑）
# 問題：開源 K 線基礎模型 Kronos-small（零樣本、不微調）能不能在我們的資料上帶來扣成本後的優勢？
# 資料：data 分支 10 幣 USDT 永續 5 分 K；保留期 2025-01-01 ~ 2026-09-30（UTC）
# T1 單獨用：每幣隨機抽 300 個時點（台北 08–20），前 240 根 5 分 K 當輸入，預測後 12 根（1 小時）
#     方向＝預測 1h 報酬正負；實際＝下一根開盤進場、持有 12 根收盤出場；成本來回 0.10%
#     過關＝10 幣合併平均 > 0 且 t ≥ 2、且 ≥ 6/10 幣為正（與策略工廠同標準）
# T2 當濾網：保留期內所有「爆倉做多」訊號（同 paper.py 規則），Kronos 預測漲 vs 跌兩組的 A 版報酬
#     過關＝「預測漲」組平均 > 全體平均，且兩組差異 Welch t ≥ 2
# 模型參數：Kronos-small + Tokenizer-base，T=1.0，top_p=0.9，sample_count=3（取平均），seed 固定
import sys, os, json, time, argparse
import numpy as np, pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('coin'); ap.add_argument('--dry', action='store_true'); ap.add_argument('--n', type=int, default=300)
ap.add_argument('--seed', type=int, default=7); ap.add_argument('--kronos', default='kronos_src'); ap.add_argument('--out', default='kronos_out')
a = ap.parse_args()
H0, H1 = pd.Timestamp('2025-01-01'), pd.Timestamp('2026-09-30 23:55')
LB, PL, COST, BS = 240, 12, 0.001, 25

k = pd.read_csv(f'klines/{a.coin}_5m.csv.gz'); k['t'] = pd.to_datetime(k.open_time, unit='ms')
p = k.drop_duplicates('t').set_index('t').sort_index()[['open', 'high', 'low', 'close', 'volume']].astype(float).asfreq('5min').ffill()
p['amount'] = p.volume * p[['open', 'high', 'low', 'close']].mean(axis=1)
O, C = p.open.values, p.close.values; idx = p.index

# 爆倉做多訊號（與 tools/paper.py 相同，期間換成保留期）
sig = []
mf = f'metrics/{a.coin}_metrics.csv.gz'
if os.path.exists(mf):
    m = pd.read_csv(mf); m['t'] = pd.to_datetime(m.create_time); m = m.drop_duplicates('t').set_index('t').sort_index()
    oi = pd.to_numeric(m.sum_open_interest, errors='coerce').resample('5min').last().ffill().reindex(idx).ffill()
    z = lambda s, w=288 * 30: (s - s.rolling(w, min_periods=w // 2).mean()) / s.rolling(w, min_periods=w // 2).std()
    zr, zo = z(p.close.pct_change(12)), z(oi.pct_change(12))
    ev = ((zr < -1) & (zo < -3) & (idx.hour < 12)).fillna(False).values
    ts = pd.Series(idx[ev]); ts = ts[(ts >= H0) & (ts <= H1)]
    if len(ts):
        ts = pd.DatetimeIndex(ts.groupby(ts.dt.floor('4h')).first().values) + pd.Timedelta('5min')
        sig = [idx.get_indexer([t])[0] for t in ts]
        sig = [i - 1 for i in sig if i > LB]   # i-1 = 訊號那根（輸入最後一根）

# 隨機時點（台北 08–20 = UTC 0–11）
rng = np.random.default_rng(sum(map(ord, a.coin)) * 7919)
pool = np.where((idx >= H0) & (idx <= H1) & (idx.hour < 12))[0]
pool = pool[(pool > LB) & (pool + PL + 1 < len(p))]
rnd = np.sort(rng.choice(pool, size=a.n, replace=False)) if a.n else np.array([], dtype=int)

jobs = [('T1', int(i)) for i in rnd] + [('T2', int(i)) for i in sig if i + PL + 1 < len(p)]
print(a.coin, 'T1', len(rnd), 'T2', len(jobs) - len(rnd), flush=True)

if not a.dry:
    sys.path.insert(0, a.kronos)
    import torch
    from model import Kronos, KronosTokenizer, KronosPredictor
    torch.manual_seed(a.seed); torch.set_num_threads(os.cpu_count())
    tok = KronosTokenizer.from_pretrained('NeoQuasar/Kronos-Tokenizer-base', revision=os.environ.get('TOK_REV'))
    mdl = Kronos.from_pretrained('NeoQuasar/Kronos-small', revision=os.environ.get('MDL_REV'))
    pr = KronosPredictor(mdl, tok, device='cpu', max_context=512)

cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
res = []; t0 = time.time()
for b in range(0, len(jobs), BS):
    chunk = jobs[b:b + BS]
    if a.dry:
        preds = [C[i] * (1 + np.random.default_rng(i).normal(0, 0.005)) for _, i in chunk]
    else:
        dfs = [p.iloc[i - LB + 1:i + 1][cols].reset_index(drop=True) for _, i in chunk]
        xts = [pd.Series(idx[i - LB + 1:i + 1]) for _, i in chunk]
        yts = [pd.Series(idx[i + 1:i + 1 + PL]) for _, i in chunk]
        out = pr.predict_batch(dfs, xts, yts, pred_len=PL, T=1.0, top_p=0.9, sample_count=3, verbose=False)
        preds = [float(o['close'].iloc[-1]) for o in out]
    for (tag, i), pc in zip(chunk, preds):
        pred_r = pc / C[i] - 1
        real = C[i + PL] / O[i + 1] - 1          # 下一根開盤進、第 12 根收盤出
        res.append(dict(test=tag, t=str(idx[i]), pred=pred_r, real=real))
    print(f'{b + len(chunk)}/{len(jobs)}  {time.time() - t0:.0f}s', flush=True)

os.makedirs(a.out, exist_ok=True)
pd.DataFrame(res).to_csv(f'{a.out}/{a.coin}.csv', index=False)
print('done', a.coin)
