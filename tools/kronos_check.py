# 在自己電腦上即時問 Kronos：TradingView 跳出「爆倉做多」L 標記時，跑這支看 Kronos 的意見。
# 用法：python3 kronos_check.py ETH        （幣名可用 ETH / ETHUSDT）
# 規則（2026-11-01 實測，3 個亂數種子都過、2025 下半年後也成立）：
#   爆倉做多訊號 ＋ Kronos 看漲 → 保留（回測每筆 +0.22%）；Kronos 看跌 → 跳過（回測每筆 −0.05%）
#   Kronos 單獨拿來猜方向沒有用（扣成本每筆 −0.085%），沒有 L 標記時不要看它做決定。
# 只讀 Binance 公開行情，不需要帳號或金鑰；不下單。
import sys, os, json, argparse, urllib.request
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kronos_lib as K

ap = argparse.ArgumentParser()
ap.add_argument('coin'); ap.add_argument('--kronos', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Kronos'))
ap.add_argument('--csv', help='離線測試用：data 分支的 5 分 K 檔'); ap.add_argument('--at', help='離線測試用：輸入最後一根的開盤時間 UTC')
a = ap.parse_args()
sym = a.coin.upper(); sym = sym if sym.endswith('USDT') else sym + 'USDT'

if a.csv:
    k = pd.read_csv(a.csv); k['t'] = pd.to_datetime(k.open_time, unit='ms')
    p = k.drop_duplicates('t').set_index('t').sort_index()[['open', 'high', 'low', 'close', 'volume']].astype(float)
    if a.at: p = p[p.index <= pd.Timestamp(a.at)]
else:
    url = f'https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=5m&limit={K.LB + 1}'
    raw = json.load(urllib.request.urlopen(url, timeout=15))
    p = pd.DataFrame([r[:6] for r in raw[:-1]], columns=['t', 'open', 'high', 'low', 'close', 'volume'])   # 丟掉還沒收完的那根
    p['t'] = pd.to_datetime(p.t, unit='ms'); p = p.set_index('t').astype(float)
p = p.asfreq('5min').ffill()
p['amount'] = p.volume * p[['open', 'high', 'low', 'close']].mean(axis=1)
i = len(p) - 1
if i + 1 < K.LB: sys.exit('資料不足 240 根')

print(f'{sym}｜最後一根收盤 {p.index[i] + pd.Timedelta("8h5min"):%m-%d %H:%M}（台北）｜價格 {p.close.iloc[i]:g}｜過去 1 小時 {(p.close.iloc[i] / p.close.iloc[i - 12] - 1) * 100:+.2f}%')
print('Kronos 計算中（約 10–30 秒）…', flush=True)
r = K.opinions(K.load(a.kronos), p, [i])[0]
print(f'Kronos 預測未來 1 小時：{r * 100:+.3f}% → {"看漲：這筆 L 訊號保留" if r > 0 else "看跌：這筆 L 訊號跳過"}')
print('（只在 TradingView 出現 L 標記時才有意義；前測滿 30 筆前只做紙上記錄、不下真單）')
