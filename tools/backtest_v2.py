import sys, os, pickle, math, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_v2 import *
TR0, TR1, TE0, TE1 = '20260815', '20261007', '20261008', '20261015'
t0 = time.time(); D = Data(train_end=TR1)
keys = sorted(k for k in D.races if TR0 <= k[0] <= TE1)
S = {}
for k in keys:
    r = D.race_rows(k)
    if r: S[k] = r
print('races', len(S), 'feat sec', round(time.time() - t0))
pickle.dump({k: (v[0], v[1], v[3]) for k, v in S.items()}, open(os.path.join(BASE, 'v2_samples.pkl'), 'wb'))
