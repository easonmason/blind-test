# 前測加註 Kronos 意見（2026-11-01 起）：每筆爆倉做多訊號，記下 Kronos 在訊號那根的預測（看漲／看跌）
# 只記錄、不改任何進出場規則。用來在前瞻期驗證「只做 Kronos 看漲的」是否仍比全做好。
import os, sys, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import kronos_lib as K

T = pd.read_csv('paper/trades.csv')
pr = K.load(sys.argv[1] if len(sys.argv) > 1 else 'kronos_src')
pred = {}
for c, g in T.groupby('幣'):
    k = pd.read_csv(f'klines/{c}_5m.csv.gz'); k['t'] = pd.to_datetime(k.open_time, unit='ms')
    p = k.drop_duplicates('t').set_index('t').sort_index()[['open', 'high', 'low', 'close', 'volume']].astype(float).asfreq('5min').ffill()
    p['amount'] = p.volume * p[['open', 'high', 'low', 'close']].mean(axis=1)
    ts = sorted(set(g.訊號時間_台北))
    ends = [p.index.get_indexer([pd.Timestamp(t) - pd.Timedelta('8h')])[0] - 1 for t in ts]   # 進場那根的前一根＝訊號那根
    ok = [(t, i) for t, i in zip(ts, ends) if i >= K.LB]
    for (t, _), r in zip(ok, K.opinions(pr, p, [i for _, i in ok])):
        pred[(c, t)] = r
T['Kronos預測1h'] = [round(pred.get((c, t), np.nan) * 100, 3) for c, t in zip(T.幣, T.訊號時間_台北)]
T['Kronos意見'] = np.where(T.Kronos預測1h > 0, '看漲', np.where(T.Kronos預測1h <= 0, '看跌', ''))
T.to_csv('paper/trades.csv', index=False)

L = ['', '## 加註 Kronos 意見（2026-11-01 起記錄；回溯補到 10-04 起所有訊號）']
for nm, g in T[T.狀態 == '已結算'].groupby('版本'):
    for op, h in g.groupby('Kronos意見'):
        if op:
            L.append(f'- {nm}｜Kronos {op}：{len(h)} 筆，平均 {h.報酬pct.mean():+.3f}%，勝率 {(h.報酬pct > 0).mean()*100:.0f}%')
open('paper/summary.md', 'a').write('\n'.join(L) + '\n'); print('\n'.join(L))
