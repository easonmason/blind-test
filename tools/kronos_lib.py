# Kronos 共用：安全載入（鎖版本＋檔案白名單）與單點預測。設定與 2026-11-01 實測完全相同，不准改。
import os, sys
import numpy as np, pandas as pd

KRONOS_COMMIT = '67b630e67f6a18c9e9be918d9b4337c960db1e9a'
MODELS = {'NeoQuasar/Kronos-small': '901c26c1332695a2a8f243eb2f37243a37bea320',
          'NeoQuasar/Kronos-Tokenizer-base': '0e0117387f39004a9016484a186a908917e22426'}
ALLOWED = {'config.json', 'model.safetensors', 'README.md', '.gitattributes'}
LB, PL, SEED, SAMPLES = 240, 12, 7, 3
COLS = ['open', 'high', 'low', 'close', 'volume', 'amount']


def load(kronos_dir):
    """先檢查 HuggingFace 檔案清單（鎖定版本、只准 safetensors），再載入模型。"""
    from huggingface_hub import HfApi
    for repo, rev in MODELS.items():
        names = {s.rfilename for s in HfApi().model_info(repo, revision=rev).siblings}
        if names - ALLOWED or 'model.safetensors' not in names:
            sys.exit(f'安全檢查失敗：{repo} 出現非預期檔案 {names - ALLOWED}，停止。')
    sys.path.insert(0, kronos_dir)
    import torch
    from model import Kronos, KronosTokenizer, KronosPredictor
    torch.manual_seed(SEED)
    tok = KronosTokenizer.from_pretrained('NeoQuasar/Kronos-Tokenizer-base', revision=MODELS['NeoQuasar/Kronos-Tokenizer-base'])
    mdl = Kronos.from_pretrained('NeoQuasar/Kronos-small', revision=MODELS['NeoQuasar/Kronos-small'])
    return KronosPredictor(mdl, tok, device='cpu', max_context=512)


def opinions(pr, p, ends):
    """p：5 分 K（index＝開盤時間 UTC，欄位含 COLS）；ends：輸入最後一根的位置清單。回傳預測 1 小時報酬。"""
    if not len(ends):
        return []
    dfs = [p.iloc[i - LB + 1:i + 1][COLS].reset_index(drop=True) for i in ends]
    xts = [pd.Series(p.index[i - LB + 1:i + 1]) for i in ends]
    yts = [pd.Series(p.index[i] + pd.to_timedelta(np.arange(1, PL + 1) * 5, 'min')) for i in ends]
    out = pr.predict_batch(dfs, xts, yts, pred_len=PL, T=1.0, top_p=0.9, sample_count=SAMPLES, verbose=False)
    return [float(o['close'].iloc[-1]) / float(p.close.iloc[i]) - 1 for o, i in zip(out, ends)]
