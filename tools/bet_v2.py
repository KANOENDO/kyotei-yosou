# v2の買い目ルール(仮想購入用)
#  1) v2の確率と市場オッズから逆算した確率を半々で合成(モデルの過信を抑える)
#  2) 1着候補: 1着確率トップ。トップが50%未満なら2番手も1着候補に(1号艇の2着付けなどを拾う)
#  3) 候補の組の中から 合成確率≧1.5% かつ 期待値(合成確率×オッズ)が高い順に最大10点
#  4) ガミ回避: 各点「オッズ×金額 ≧ レース購入額×1.5」を満たす最低金額を割当て、余りは期待値上位へ
import math
def choose(P, odds, budget=1000, max_pts=10, blend=0.5, minp=0.015):
    """P: {(a,b,c) 0始まり: prob}, odds: {'1-2-3': float}"""
    inv = {k: 1 / o for k, o in odds.items() if o}; Z = sum(inv.values())
    q = {}
    for (a, b, c), p in P.items():
        k = f'{a+1}-{b+1}-{c+1}'
        if odds.get(k): q[k] = blend * p + (1 - blend) * inv[k] / Z
    w1 = {}
    for (a, b, c), p in P.items(): w1[a] = w1.get(a, 0) + p
    first = sorted(w1, key=lambda a: -w1[a]); heads = [first[0]] + ([first[1]] if w1[first[0]] < 0.5 else [])
    cand = [(k, q[k], odds[k], q[k] * odds[k]) for k in q if int(k[0]) - 1 in heads and q[k] >= minp]
    cand.sort(key=lambda x: -x[3]); picks = []; tot = 0
    for k, p, o, ev in cand:
        need = max(100, math.ceil(budget * 1.5 / o / 100) * 100)
        if tot + need > budget: continue
        picks.append([k, p, o, ev, need]); tot += need
        if len(picks) >= max_pts: break
    i = 0
    while tot < budget and picks: picks[i % len(picks)][4] += 100; tot += 100; i += 1
    return picks, {a + 1: round(100 * w1[a], 1) for a in range(len(w1))}, [h + 1 for h in heads]
