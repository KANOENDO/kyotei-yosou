# 予想モデル v2: 段階別プラケット=ルース(条件付きロジット)モデル
#  1着・2着・3着それぞれの選ばれやすさを、選手のコース別成績・直近10走・ST・展示・モーター・水面から推定する。
#  学習・検証には公式Kファイル(競走成績)と公式ファン手帳を使う。オッズは使わない(買い目選択で市場オッズと合成)。
import os, csv, math, bisect, json, itertools, sys
import numpy as np
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
FEATS = ['コース1着', 'コース2連', 'コース3連', '場コース', '直近着順', '直近ST', '全国勝率', 'モーター', '展示', '1C×風速', '1C×波高']

def logit(p): p = min(max(p, 1e-4), 1 - 1e-4); return math.log(p / (1 - p))

def load_fan():
    fn = sorted(f for f in os.listdir(BASE) if f.startswith('course_stats_') and f.endswith('.csv'))[-1]
    fan = {r['登番']: r for r in csv.DictReader(open(os.path.join(BASE, fn), encoding='utf-8-sig'))}
    tot = {c: [0, 0, 0, 0] for c in range(1, 7)}
    for r in fan.values():
        for c in range(1, 7):
            n = int(r[f'{c}C進入']); a, b, d = int(r[f'{c}C1着']), int(r[f'{c}C2着']), int(r[f'{c}C3着'])
            tot[c][0] += n; tot[c][1] += a; tot[c][2] += a + b; tot[c][3] += a + b + d
    prior = {c: (tot[c][1] / tot[c][0], tot[c][2] / tot[c][0], tot[c][3] / tot[c][0]) for c in range(1, 7)}
    return fan, prior, fn

class Data:
    def __init__(self, train_end='99999999'):
        self.fan, self.prior, self.fanfile = load_fan()
        H = list(csv.DictReader(open(os.path.join(BASE, 'race_history.csv'), encoding='utf-8-sig')))
        self.races = {}
        for x in H: self.races.setdefault((x['日付'], x['場'], int(x['R'])), []).append(x)
        self.rinfo = {(r['日付'], r['場'], int(r['R'])): r for r in csv.DictReader(open(os.path.join(BASE, 'races.csv'), encoding='utf-8-sig'))}
        self.by_racer = {}; self.by_motor = {}
        for k in sorted(self.races):
            for x in self.races[k]:
                fin = int(x['着']) if x['着'].isdigit() else 6.5
                st = float(x['ST']) if x['ST'][:2] == '0.' else None
                self.by_racer.setdefault(x['登番'], []).append((k[0], k[2], fin, st))
                self.by_motor.setdefault((k[1], x['モーター']), []).append((k[0], 1 if fin <= 2 else 0))
        # 場×コースの1着率(学習期間のみ)
        cnt = {}
        for k, xs in self.races.items():
            if k[0] > train_end: continue
            for x in xs:
                if x['進入'].isdigit():
                    c = cnt.setdefault((k[1], int(x['進入'])), [0, 0]); c[0] += 1; c[1] += x['着'] == '01'
        self.venue = {k: (v[1] + 20 * self.prior[k[1]][0]) / (v[0] + 20) for k, v in cnt.items()}

    def recent(self, toban, date, n=10):
        L = self.by_racer.get(toban, []); i = bisect.bisect_left(L, (date, 0, 0, 0))
        return L[max(0, i - n):i]

    def motor(self, jcd, mno, date):
        # その場・そのモーター番号の直近60走の2連対率(平均1/3へ縮約)
        L = self.by_motor.get((jcd, mno), []); i = bisect.bisect_left(L, (date, 0))
        y = [v for d, v in L[max(0, i - 60):i]]
        return (sum(y) + 10 / 3) / (len(y) + 10)

    def features(self, date, jcd, boats, wind=0, wave=0):
        """boats: [{'登番','コース','モーター','展示'(float or None)}] → (n_boat, n_feat)"""
        F = []
        ex = [b['展示'] for b in boats if b.get('展示')]; exm = sum(ex) / len(ex) if ex else None
        rec = [self.recent(b['登番'], date) for b in boats]
        sts = [[s for *_, s in r if s is not None] for r in rec]
        stm = [sum(s) / len(s) if s else 0.17 for s in sts]; stmean = sum(stm) / len(stm)
        rates = []
        for b in boats:
            f = self.fan.get(b['登番']); rates.append(float(f['全体勝率']) if f and f['全体勝率'] else 4.0)
        rmean = sum(rates) / len(rates)
        for b, r, sm, rt in zip(boats, rec, stm, rates):
            c = b['コース']; f = self.fan.get(b['登番']); p1, p2, p3 = self.prior[c]; k = 8
            if f:
                n = int(f[f'{c}C進入']); a = int(f[f'{c}C1着']); a2 = a + int(f[f'{c}C2着']); a3 = a2 + int(f[f'{c}C3着'])
            else: n = a = a2 = a3 = 0
            fins = [x[2] for x in r]; form = 3.5 - (sum(fins) / len(fins) if fins else 3.5)
            vr = self.venue.get((jcd, c), p1)
            F.append([logit((a + k * p1) / (n + k)), logit((a2 + k * p2) / (n + k)), logit((a3 + k * p3) / (n + k)),
                      logit(vr), form, (stmean - sm) * 10, rt - rmean, logit(self.motor(jcd, b['モーター'], date)),
                      ((exm - b['展示']) * 10 if (exm and b.get('展示')) else 0.0), (c == 1) * wind, (c == 1) * wave])
        return np.array(F)

    def race_rows(self, key):
        xs = self.races[key]; ri = self.rinfo.get(key, {})
        boats = []; order = {}
        for x in xs:
            if not x['進入'].isdigit(): return None
            try: ex = float(x['展示'])
            except: ex = None
            boats.append({'登番': x['登番'], 'コース': int(x['進入']), 'モーター': x['モーター'], '展示': ex, '枠': int(x['枠'])})
            if x['着'] in ('01', '02', '03'): order[int(x['着'])] = len(boats) - 1
        if len(order) < 3 or len(boats) < 4: return None
        w = int(ri.get('風速') or 0); v = int(ri.get('波') or 0)
        return self.features(key[0], key[1], boats, w, v), [order[1], order[2], order[3]], boats, ri

def softmax(z): z = z - z.max(); e = np.exp(z); return e / e.sum()

def pack(samples):
    N = len(samples); d = samples[0][0].shape[1]
    X = np.zeros((N, 6, d)); M = np.zeros((N, 6), bool); O = np.zeros((N, 3), int)
    for i, (x, o) in enumerate(samples): X[i, :len(x)] = x; M[i, :len(x)] = True; O[i] = o
    return X, M, O

def fit(samples, l2=0.01, iters=400, lr=0.05):
    """samples: list of (X, [i1,i2,i3]) → 段階別の重み W (3, n_feat)。ベクトル化した勾配上昇(Adam)"""
    X, M, O = pack(samples); N, _, d = X.shape; ar = np.arange(N)
    W = np.zeros((3, d)); m = np.zeros_like(W); v = np.zeros_like(W)
    for t in range(1, iters + 1):
        G = np.zeros_like(W); avail = M.copy()
        for s in range(3):
            z = X @ W[s]; z = np.where(avail, z, -1e9); z -= z.max(1, keepdims=True)
            p = np.exp(z) * avail; p /= p.sum(1, keepdims=True)
            G[s] = (X[ar, O[:, s]] - (p[:, :, None] * X).sum(1)).mean(0)
            avail[ar, O[:, s]] = False
        G = G - l2 * W
        m = 0.9 * m + 0.1 * G; v = 0.999 * v + 0.001 * G * G
        W += lr * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return W

def trifecta_probs(X, W):
    n = len(X); s = [X @ W[k] for k in range(3)]; P = {}
    for a, b, c in itertools.permutations(range(n), 3):
        pa = softmax(s[0])[a]
        r1 = [i for i in range(n) if i != a]; pb = softmax(s[1][r1])[r1.index(b)]
        r2 = [i for i in r1 if i != b]; pc = softmax(s[2][r2])[r2.index(c)]
        P[(a, b, c)] = pa * pb * pc
    return P
