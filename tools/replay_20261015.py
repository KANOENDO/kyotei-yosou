import sys, os, json, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_v2 import *; from bet_v2 import choose
D = Data(train_end='20261007'); W = np.array(json.load(open(os.path.join(BASE, 'model_v2_weights.json')))['W'])
odds = json.load(open(os.path.join(BASE, '..', 'sim', 'sim_20261015_odds_snapshot.json')))
tb = tp = 0
for r in range(4, 13):
    X, o, boats, ri = D.race_rows(('20261015', '24', r))
    # 枠順に並んでいる前提で艇番=枠。進入が枠と違う場合も確率は艇(枠)単位
    idx = {b['枠'] - 1: i for i, b in enumerate(boats)}
    P0 = trifecta_probs(X, W); P = {(boats[a]['枠'] - 1, boats[b]['枠'] - 1, boats[c]['枠'] - 1): p for (a, b, c), p in P0.items()}
    picks, w1, heads = choose(P, odds[str(r)]['odds'])
    res = ri['三連単']; pay = int(ri['払戻']); hit = [x for x in picks if x[0] == res]
    got = sum(pay * x[4] // 100 for x in hit); tb += 1000; tp += got
    print(f'{r}R 1着確率{w1} 1着候補{heads} 結果{res}({pay}) → 払戻{got}')
    print('   ', ' '.join(f"{k}({s})" for k, p, o, ev, s in picks))
print('合計 購入', tb, '払戻', tp, '回収率', round(100 * tp / tb, 1))
