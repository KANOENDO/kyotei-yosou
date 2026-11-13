#!/usr/bin/env python3
"""モデルv2の運用用の重みを学習し data/model_v2_live.json に保存する(月1回程度の再学習用)。
使い方: python3 tools/train_v2.py [学習開始YYYYMMDD(既定20260815)]
  事前に kfiles.py fetch / build で data/K と race_history.csv を最新にしておく。races.csv はここで作り直す。
  W_morning: 展示・風波を使わない重み(朝の回用) / W_final: 全特徴量の重み(確定の回用)
"""
import sys, os, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
subprocess.run([sys.executable, os.path.join(HERE, 'kraces.py')], check=True)
from model_v2 import *
TR0 = sys.argv[1] if len(sys.argv) > 1 else '20260815'
D = Data(); S = []; last = TR0
for k in sorted(D.races):
    if k[0] < TR0: continue
    r = D.race_rows(k)
    if r and len(r[2]) == 6: S.append((r[0], r[1])); last = k[0]
MORNING = [i for i, f in enumerate(FEATS) if f not in ('展示', '1C×風速', '1C×波高')]
Wm = fit([(x[:, MORNING], o) for x, o in S], iters=300); Wf = fit(S, iters=300)
json.dump({'feats': FEATS, 'cols_morning': MORNING, 'W_morning': Wm.tolist(), 'W_final': Wf.tolist(),
           'train': [TR0, last], 'races': len(S)}, open(os.path.join(BASE, 'model_v2_live.json'), 'w'), ensure_ascii=False, indent=1)
print('学習', len(S), 'R', TR0, '〜', last, '-> data/model_v2_live.json')
