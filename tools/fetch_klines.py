# 從 Binance 公開資料庫抓 USDT 永續 5 分 K（月檔），存成壓縮 csv
import urllib.request,zipfile,io,os,sys,datetime as dt
syms=sys.argv[1].split(',');start=sys.argv[2];out='klines';os.makedirs(out,exist_ok=True)
y,m=map(int,start.split('-'));today=dt.date.today()
for s in syms:
    rows=[]
    yy,mm=y,m
    while (yy,mm)<(today.year,today.month):
        u=f'https://data.binance.vision/data/futures/um/monthly/klines/{s}/5m/{s}-5m-{yy}-{mm:02d}.zip'
        try:
            z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(u,timeout=60).read()))
            txt=z.read(z.namelist()[0]).decode().splitlines()
            rows+= [l for l in txt if l and l[0].isdigit()]
        except Exception as e:
            # 月初時上個月的月檔常還沒出（2026-11-01 事故：10 月整月消失）→ 改用日檔補
            print('monthly missing, fallback to daily',u,e)
            d=dt.date(yy,mm,1)
            while d.month==mm and d<today:
                du=f'https://data.binance.vision/data/futures/um/daily/klines/{s}/5m/{s}-5m-{d}.zip'
                try:
                    z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(du,timeout=60).read()));rows+=[l for l in z.read(z.namelist()[0]).decode().splitlines() if l and l[0].isdigit()]
                except Exception: pass
                d+=dt.timedelta(days=1)
        mm+=1
        if mm>12: yy,mm=yy+1,1
    # 本月用日檔補
    d=dt.date(today.year,today.month,1)
    while d<today:
        u=f'https://data.binance.vision/data/futures/um/daily/klines/{s}/5m/{s}-5m-{d}.zip'
        try:
            z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(u,timeout=60).read()));rows+=[l for l in z.read(z.namelist()[0]).decode().splitlines() if l and l[0].isdigit()]
        except Exception as e: pass
        d+=dt.timedelta(days=1)
    import gzip
    with gzip.open(f'{out}/{s}_5m.csv.gz','wt') as f:
        f.write('open_time,open,high,low,close,volume\n')
        for l in rows:
            p=l.split(',');f.write(','.join(p[:6])+'\n')
    print(s,len(rows))
