import sys, os, pickle, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_v2 import *
S = pickle.load(open(os.path.join(BASE, 'v2_samples.pkl'), 'rb'))
TR1 = '20261007'
tr = [(v[0], v[1]) for k, v in S.items() if k[0] <= TR1]
te = {k: v for k, v in S.items() if k[0] > TR1}
def run(cols, name):
    W = fit([(x[:, cols], o) for x, o in tr], iters=300)
    ll1 = ll3 = 0; acc = 0; n = 0; top = {1: 0, 5: 0, 10: 0, 20: 0}; roi = {}
    for k, (x, o, ri) in te.items():
        P = trifecta_probs(x[:, cols], W); s0 = softmax(x[:, cols] @ W[0])
        ll1 += -math.log(s0[o[0]]); acc += s0.argmax() == o[0]
        ll3 += -math.log(max(P[tuple(o)], 1e-9)); n += 1
        rk = sorted(P, key=lambda c: -P[c])
        for t in top: top[t] += tuple(o) in rk[:t]
        pay = int(ri.get('払戻') or 0)
        for t in (5, 10, 20):
            roi.setdefault(t, [0, 0]); roi[t][0] += t * 100; roi[t][1] += pay if tuple(o) in rk[:t] else 0
    print(f'[{name}] 検証{n}R 1着logloss={ll1/n:.3f} 1着的中率={acc/n:.3f} 3連単logloss={ll3/n:.3f} '
          + ' '.join(f'上位{t}点内={top[t]/n:.3f}' for t in top) + ' | 上位N点均等買いの回収率 ' + ' '.join(f'{t}点:{100*roi[t][1]/roi[t][0]:.1f}%' for t in roi))
    return W
cols_all = list(range(len(FEATS)))
run([3], 'ベースライン(場×コースのみ)')
run([0, 1, 2, 3], 'コース別成績のみ')
W = run(cols_all, 'v2 全特徴量')
json.dump({'feats': FEATS, 'W': W.tolist(), 'train': ['20260815', TR1]}, open(os.path.join(BASE, 'model_v2_weights.json'), 'w'), ensure_ascii=False, indent=1)
for s in range(3): print(f'{s+1}着の重み', {f: round(w, 3) for f, w in zip(FEATS, W[s])})
