# 彙整 kronos_eval.py 各幣結果，依事前登錄標準判定過不過
import glob, sys, numpy as np, pandas as pd
d = sys.argv[1] if len(sys.argv) > 1 else 'kronos_out'
COST = 0.001
R = pd.concat([pd.read_csv(f).assign(coin=f.split('/')[-1][:-4]) for f in sorted(glob.glob(f'{d}/*.csv'))])
L = ['# Kronos-small 保留期實測（2025-01 ~ 2026-09，零樣本）', '']
t1 = R[R.test == 'T1'].copy()
t1['dir'] = np.sign(t1.pred); t1['pnl'] = t1.dir * t1.real - COST
tt = lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan
ic = t1[['pred', 'real']].corr('spearman').iloc[0, 1]
byc = t1.groupby('coin').pnl.mean()
hit = (np.sign(t1.pred) == np.sign(t1.real)).mean()
L += ['## T1 單獨用（照預測方向做，持 1 小時，扣 0.10%）',
      f'- 樣本 {len(t1)}；方向命中率 {hit*100:.1f}%；Spearman IC {ic:+.4f}',
      f'- 每筆平均 {t1.pnl.mean()*100:+.3f}%（t {tt(t1.pnl):.2f}）；為正的幣 {(byc>0).sum()}/{len(byc)}',
      f'- 不扣成本平均 {(t1.pnl+COST).mean()*100:+.3f}%']
q = t1.pred.abs().quantile(0.8); top = t1[t1.pred.abs() >= q]
L += [f'- 參考（非登錄標準）：預測幅度前 20% 的 {len(top)} 筆，每筆 {top.pnl.mean()*100:+.3f}%（t {tt(top.pnl):.2f}）']
p1 = t1.pnl.mean() > 0 and tt(t1.pnl) >= 2 and (byc > 0).sum() >= 6
L += [f'- **判定：{"過關" if p1 else "未過"}**', '']
t2 = R[R.test == 'T2'].copy(); t2['pnl'] = t2.real - COST
if len(t2):
    up, dn = t2[t2.pred > 0].pnl, t2[t2.pred <= 0].pnl
    w = (up.mean() - dn.mean()) / np.sqrt(up.var(ddof=1) / len(up) + dn.var(ddof=1) / len(dn)) if len(up) > 2 and len(dn) > 2 else np.nan
    L += ['## T2 當爆倉做多的濾網（A 版，持 1 小時，扣 0.10%）',
          f'- 全部訊號 {len(t2)} 筆，每筆 {t2.pnl.mean()*100:+.3f}%',
          f'- Kronos 預測漲 {len(up)} 筆，每筆 {up.mean()*100:+.3f}%；預測跌 {len(dn)} 筆，每筆 {dn.mean()*100:+.3f}%；差異 Welch t {w:.2f}']
    p2 = up.mean() > t2.pnl.mean() and w >= 2
    L += [f'- **判定：{"過關" if p2 else "未過"}**']
open(f'{d}/summary.md', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
