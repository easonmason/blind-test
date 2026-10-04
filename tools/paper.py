# 自動模擬前測（2026-10-04 起）：「爆倉式下跌後做多」——1 小時跌幅與未平倉減少同時異常（z<-1 且 z<-3）
# 台北 08:00–20:00 出現訊號 → 下一根 5 分 K 開盤做多；A 版持有 1 小時、B 版持有 4 小時；成本來回 0.10%；每幣每 4 小時最多一次
import pandas as pd,numpy as np,glob,os
START=pd.Timestamp('2026-10-04');COST=0.001;rows=[]
for f in sorted(glob.glob('klines/*_5m.csv.gz')):
    c=os.path.basename(f).split('_')[0]
    k=pd.read_csv(f);k['t']=pd.to_datetime(k.open_time,unit='ms');p=k.drop_duplicates('t').set_index('t').sort_index()[['open','close']].astype(float).asfreq('5min').ffill()
    m=pd.read_csv(f'metrics/{c}_metrics.csv.gz');m['t']=pd.to_datetime(m.create_time);m=m.drop_duplicates('t').set_index('t').sort_index()
    oi=pd.to_numeric(m.sum_open_interest,errors='coerce').resample('5min').last().ffill().reindex(p.index).ffill()
    z=lambda s,w=288*30:(s-s.rolling(w,min_periods=w//2).mean())/s.rolling(w,min_periods=w//2).std()
    zr,zo=z(p.close.pct_change(12)),z(oi.pct_change(12))
    ev=((zr<-1)&(zo<-3)&(p.index.hour<12)).fillna(False).values
    ts=pd.Series(p.index[ev]);ts=ts[ts>=START]
    if not len(ts):continue
    ts=pd.DatetimeIndex(ts.groupby(ts.dt.floor('4h')).first().values)+pd.Timedelta('5min')
    o=p.open;C=p.close.values
    for t in ts:
        i=o.index.get_indexer([t])[0]
        if i<0:continue
        for nm,h in [('A_1小時',12),('B_4小時',48)]:
            done=i+h<=len(o)
            r=(C[i+h-1]/o.values[i]-1-COST) if done else np.nan
            rows.append(dict(幣=c,訊號時間_台北=(t+pd.Timedelta('8h')).strftime('%Y-%m-%d %H:%M'),版本=nm,進場價=o.values[i],報酬pct=round(r*100,3) if done else None,狀態='已結算' if done else '持有中'))
os.makedirs('paper',exist_ok=True);T=pd.DataFrame(rows);T.to_csv('paper/trades.csv',index=False)
lines=['# 自動模擬前測：爆倉式下跌後做多','',f'起算：{START.date()}　更新：{pd.Timestamp.now('UTC').strftime("%Y-%m-%d %H:%M")} UTC','']
if len(T):
    for nm,g in T[T.狀態=='已結算'].groupby('版本'):
        r=g.報酬pct;lines.append(f'- {nm}：{len(r)} 筆，平均 {r.mean():+.3f}%，勝率 {(r>0).mean()*100:.0f}%，累計 {r.sum():+.2f}%')
else: lines.append('- 尚無訊號')
open('paper/summary.md','w').write('\n'.join(lines)+'\n');print('\n'.join(lines))
