# Binance 公開資料：期貨 5 分鐘指標（未平倉量、大戶多空比、主動買賣比）＋資金費率
import urllib.request,zipfile,io,os,sys,datetime as dt,gzip
syms=sys.argv[1].split(',');start=dt.date.fromisoformat(sys.argv[2]);out='metrics';os.makedirs(out,exist_ok=True)
from concurrent.futures import ThreadPoolExecutor
def get(u):
    try:
        z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(u,timeout=60).read()));return z.read(z.namelist()[0]).decode().splitlines()
    except Exception: return []
today=dt.date.today()
for s in syms:
    days=[start+dt.timedelta(d) for d in range((today-start).days)]
    urls=[f'https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip' for d in days]
    with ThreadPoolExecutor(16) as ex: parts=list(ex.map(get,urls))
    with gzip.open(f'{out}/{s}_metrics.csv.gz','wt') as f:
        hdr=False
        for p in parts:
            for l in p:
                if l.startswith('create_time'):
                    if not hdr: f.write(l+'\n');hdr=True
                elif l: f.write(l+'\n')
    # 資金費率（月檔）
    rows=[];y,m=2021,1
    while (y,m)<(today.year,today.month):
        rows+= [l for l in get(f'https://data.binance.vision/data/futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{y}-{m:02d}.zip') if l and l[0].isdigit()]
        m+=1
        if m>12:y,m=y+1,1
    with gzip.open(f'{out}/{s}_funding.csv.gz','wt') as f:
        f.write('calc_time,interval,rate\n');f.write('\n'.join(rows)+'\n')
    print(s,sum(len(p) for p in parts),len(rows))
