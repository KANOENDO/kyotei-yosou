#!/usr/bin/env python3
"""モデルv2による運用予想(仮想購入用。実際の購入はしない)。
  python3 tools/predict_v2.py morning YYYYMMDD 場コード [--out DIR]
      出走表(boatrace.jp racelist)を取得し、展示なし・想定進入=枠番で各艇の1着確率と3連単確率を計算。
      data/pred_YYYYMMDD.json と data/schedule_YYYYMMDD.json を作り、レポート4章用のMarkdownと
      kyotei_log.csv に追記する行(「LOG:」で始まる行)を表示する。
  python3 tools/predict_v2.py final YYYYMMDD R [--apply] [--out DIR]
      直前情報(展示タイム・スタート展示の進入・風・波)とオッズを取得し、展示込みで再計算して最終予想と買い目を出す。
      オッズ120通りを data/odds/ に保存。展示タイムが未掲載なら締切6分前まで待って取り直す。--apply で kyotei_log.csv の該当行(買い目・購入額・最終予想・変更理由)を更新。
自信度: 本命の1着確率 高(≥65%)・中(≥45%)・低。買い目: 3連単の確率上位から、各点「オッズ×金額≧1,500円」を満たす最大6点・合計1,000円。
オッズは買い目の金額調整(取りガミ回避)にだけ使い、予想(確率)には使わない。
"""
import sys, os, re, csv, json, math, subprocess, datetime, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from model_v2 import Data, FEATS, softmax, trifecta_probs, BASE
import numpy as np
ROOT = os.path.dirname(HERE)
VENUE = {'24': '大村', '18': '徳山', '19': '下関'}
URL = 'https://www.boatrace.jp/owpc/pc/race/{}?rno={}&jcd={}&hd={}'

def get(page, r, jcd, ymd):
    p = subprocess.run(['curl', '-sS', '-f', '--max-time', '30', URL.format(page, r, jcd, ymd)], capture_output=True)
    return p.stdout.decode('utf-8', 'replace') if p.returncode == 0 else ''

def T(s): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)).replace('&nbsp;', '').strip()

def parse_racelist(h):
    k = h.find('締切予定時刻'); dl = re.findall(r'<td class="[^"]*">(\d\d:\d\d)</td>', h[k:k + 3000])[:12]
    t = h.find('title16_titleDetail__add2020'); title = T(h[t + 30:h.find('</h3>', t)]) if t >= 0 else ''
    boats = []
    for p in h.split('<tbody class=" is-fs12">')[1:7]:
        w = re.search(r'is-boatColor(\d)', p); tb = re.search(r'toban=(\d{4})', p)
        if not (w and tb): continue
        cls = re.search(r'/\s*<span class="[^"]*">\s*([AB][12])\s*</span>', p)
        name = T(re.search(r'is-fs18 is-fBold">(.*?)</div>', p, re.S).group(1)).replace('　', ' ')
        c = [T(x).split() for x in re.findall(r'<td class=" ?is-lineH2" rowspan="4">(.*?)</td>', p, re.S)]
        if len(c) < 5 or len(c[3]) < 2: continue
        boats.append({'枠': int(w.group(1)), '登番': tb.group(1), '級': cls.group(1) if cls else '取得不可', '選手': name,
                      'F': c[0][0], 'L': c[0][1], '平均ST': c[0][2], '全国勝率': c[1][0], '当地勝率': c[2][0],
                      'モーター': c[3][0], 'モーター2連率': c[3][1], 'ボート': c[4][0], 'ボート2連率': c[4][1]})
    return dl, title, boats

def parse_before(h):
    """→ {'展示': {枠: float}, 'コース': {枠: コース}, 'ST': {枠: str}, '風速': int|None, '波': int|None, '気象': str}"""
    ex = {}
    for p in h.split('<tbody class="is-fs12')[1:7]:
        w = re.search(r'is-boatColor(\d)', p); td = re.findall(r'<td rowspan="4">([^<]*)</td>', p)
        if w and td:
            try: ex[int(w.group(1))] = float(td[0])
            except ValueError: pass
    se = re.findall(r'table1_boatImage1Number is-type(\d)">\d</span>.*?table1_boatImage1Time[^>]*>([^<]*)<', h, re.S)
    course = {int(b): i + 1 for i, (b, _) in enumerate(se)}; st = {int(b): s.strip() for b, s in se}
    lab = re.findall(r'weather1_bodyUnitLabelData">([^<]*)<', h)
    def num(s):
        m = re.match(r'(\d+)', s or ''); return int(m.group(1)) if m else None
    wind = num(lab[1]) if len(lab) > 1 else None; wave = num(lab[3]) if len(lab) > 3 else None
    m = re.search(r'水面気象情報.*?波高\s*\d+cm', T(h))
    return {'展示': ex, 'コース': course, 'ST': st, '風速': wind, '波': wave, '気象': m.group(0) if m else '気象:取得不可'}

def parse_odds(h):
    v = re.findall(r'class="oddsPoint[^"]*">([^<]*)<', h)
    if len(v) != 120: return {}, ''
    odds = {}
    for i, s in enumerate(v):
        row, col = divmod(i, 6); a = col + 1; oth = [x for x in range(1, 7) if x != a]
        b = oth[row // 4]; c = [x for x in oth if x != b][row % 4]
        try: odds[f'{a}-{b}-{c}'] = float(s)
        except ValueError: pass
    m = re.search(r'オッズ更新時間\s*(\d{1,2}:\d\d)', T(h))
    return odds, (m.group(1) if m else ('締切時オッズ' if '締切時オッズ' in h else '不明'))

def model():
    return Data(), json.load(open(os.path.join(BASE, 'model_v2_live.json'), encoding='utf-8'))

def probs(D, M, ymd, jcd, boats, before=None):
    """boats: racelist の艇。before があり全艇の展示タイムが取れていれば全特徴量、無ければ朝用の重み。"""
    full = bool(before) and all(b['枠'] in before['展示'] for b in boats)
    cs = before['コース'] if before and len(before['コース']) == len(boats) else {}
    bs = [{'登番': b['登番'], 'コース': cs.get(b['枠'], b['枠']), 'モーター': b['モーター'],
           '展示': before['展示'][b['枠']] if full else None} for b in boats]
    X = D.features(ymd, jcd, bs, (before or {}).get('風速') or 0 if full else 0, (before or {}).get('波') or 0 if full else 0)
    if full: W = np.array(M['W_final'])
    else: X = X[:, M['cols_morning']]; W = np.array(M['W_morning'])
    P = trifecta_probs(X, W); wk = [b['枠'] for b in boats]
    tri = {f'{wk[a]}-{wk[b]}-{wk[c]}': float(p) for (a, b, c), p in P.items()}
    p1 = {w: 0.0 for w in wk}
    for k, p in tri.items(): p1[int(k[0])] += p
    hon = max(p1, key=p1.get); p2 = {}
    for k, p in tri.items():
        if int(k[0]) == hon: p2[int(k[2])] = p2.get(int(k[2]), 0) + p
    tai = max(p2, key=p2.get)
    conf = '高' if p1[hon] >= 0.65 else '中' if p1[hon] >= 0.45 else '低'
    return {'p1': {str(w): round(p1[w], 4) for w in wk}, '本命': hon, '対抗': tai, '自信度': conf, '展示込み': full,
            'コース': {str(b['枠']): cs.get(b['枠'], b['枠']) for b in boats},
            'top': sorted(tri.items(), key=lambda x: -x[1])[:20]}

def provisional(top):
    return '仮 3連単 ' + '/'.join(f'{k}({m})' for (k, _), m in zip(top[:5], (300, 200, 200, 200, 100)))

def choose(top, odds, budget=1000, max_pts=6, gami=1500):
    picks = []; tot = 0
    for k, p in top:
        o = odds.get(k)
        if not o: continue
        need = max(100, math.ceil(gami / o / 100) * 100)
        if tot + need > budget: continue
        picks.append([k, p, o, need]); tot += need
        if len(picks) >= max_pts or tot >= budget: break
    i = 0
    while picks and tot < budget: picks[i % len(picks)][3] += 100; tot += 100; i += 1
    return picks

def recent_txt(D, tb, ymd):
    r = D.recent(tb, ymd); fins = [x[2] for x in r if x[2] <= 6]
    return f"近{len(r)}走平均{sum(fins) / len(fins):.1f}着" if fins else '直近走:データなし'

def course_txt(D, tb, c):
    f = D.fan.get(tb)
    if not f or int(f[f'{c}C進入']) == 0: return 'コース別:データなし'
    return f"コース{c}:{f[f'{c}C進入']}回/1着{f[f'{c}C1着率']}%/2連{f[f'{c}C2連率']}%/3連{f[f'{c}C3連率']}%/ST{f[f'{c}C平均ST']}"

def boat_txt(D, b, ymd):
    return (f"{b['枠']}号艇 {b['選手']}({b['級']}・全国{b['全国勝率']}・当地{b['当地勝率']}・平均ST{b['平均ST']}・{b['F']}{b['L']}"
            f"・M{b['モーター']}号2連{b['モーター2連率']}・{recent_txt(D, b['登番'], ymd)}・{course_txt(D, b['登番'], b['枠'])})")

def morning(ymd, jcd, out):
    D, M = model(); races = []; dl = []
    for r in range(1, 13):
        d, title, boats = parse_racelist(get('racelist', r, jcd, ymd))
        if d: dl = d
        if len(boats) < 4: print(f'{r}R: 出走表 取得不可'); continue
        pr = probs(D, M, ymd, jcd, boats)
        races.append({'r': r, 'title': title, 'deadline': dl[r - 1] if len(dl) >= r else '', 'boats': boats, **pr, '仮買い目': provisional(pr['top'])})
    if not races: print('出走表を取得できませんでした'); sys.exit(1)
    date = f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}'; venue = VENUE.get(jcd, jcd)
    os.makedirs(out, exist_ok=True)
    json.dump({'date': date, 'venue': venue, 'jcd': jcd, 'model': M['train'], 'races': races},
              open(os.path.join(out, f'pred_{ymd}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'date': date, 'venue': venue, 'jcd': jcd, 'races': [{'r': x['r'], 'deadline': x['deadline']} for x in races]},
              open(os.path.join(out, f'schedule_{ymd}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"<!-- モデルv2(学習 {M['train'][0]}〜{M['train'][1]}・{M['races']}R)。朝は展示なし・想定進入=枠番 -->")
    for x in races:
        bs = {b['枠']: b for b in x['boats']}; h, t = x['本命'], x['対抗']
        miss = [str(b['枠']) for b in x['boats'] if len(D.recent(b['登番'], ymd)) < 10 or 'データなし' in course_txt(D, b['登番'], b['枠'])]
        print(f"### {x['r']}R {x['title']}(締切 {x['deadline']})")
        print(f"- 本命 {h}・対抗 {t} 自信度 **{x['自信度']}**(本命の1着確率 {x['p1'][str(h)]:.0%})")
        print('- 1着確率: ' + ' '.join(f"{w}:{p:.0%}" for w, p in x['p1'].items()))
        print(f"- 根拠: {boat_txt(D, bs[h], ymd)} / {boat_txt(D, bs[t], ymd)}")
        print('- 3連単の確率上位: ' + ' '.join(f"{k}({p:.1%})" for k, p in x['top'][:8]))
        print('- データ欠け: ' + ('なし' if not miss else ','.join(miss) + '号艇(直近10走未満またはコース別データなし)'))
        print(f"- {x['仮買い目']}\n")
    for x in races:
        print('LOG:' + ','.join([date, venue, str(x['r']), f"{x['本命']}-{x['対抗']}", x['自信度'], x['仮買い目'], '0', '', '', '', '']))

def final(ymd, r, apply, out):
    pj = json.load(open(os.path.join(out, f'pred_{ymd}.json'), encoding='utf-8'))
    jcd = pj['jcd']; x = [q for q in pj['races'] if q['r'] == r][0]; boats = x['boats']
    D, M = model(); bh = get('beforeinfo', r, jcd, ymd); be = parse_before(bh) if bh else None
    # 展示タイムが未掲載なら、締切6分前まで45秒おきに取り直す(10分間隔の起動で各Rの機会は1回のため)
    hh, mm = (int(v) for v in x['deadline'].split(':')) if x.get('deadline') else (0, 0)
    def left():
        t = datetime.datetime.utcnow() + datetime.timedelta(hours=9); return hh * 60 + mm - (t.hour * 60 + t.minute)
    while not (be and len(be['展示']) >= len(boats)) and 6 < left() <= 20:
        time.sleep(45); bh = get('beforeinfo', r, jcd, ymd); be = parse_before(bh) if bh else None
    pr = probs(D, M, ymd, jcd, boats, be)
    odds, upd = parse_odds(get('odds3t', r, jcd, ymd))
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime('%H:%M')
    if odds:
        od = os.path.join(out, 'odds'); os.makedirs(od, exist_ok=True)
        json.dump({'date': pj['date'], 'jcd': jcd, 'r': r, '取得時刻': now, 'オッズ更新時間': upd, 'odds': odds,
                   'p1_final': pr['p1'], '展示込み': pr['展示込み']},
                  open(os.path.join(od, f'{ymd}_{jcd}_{r:02d}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    am = f"{x['本命']}-{x['対抗']}"; fm = f"{pr['本命']}-{pr['対抗']}"; reason = ''
    if not pr['展示込み']: fm = am; pr['本命'], pr['対抗'] = x['本命'], x['対抗']   # 展示が無ければ朝の予想のまま(修正根拠なし)
    elif fm != am:
        ch = [f"{w}号艇 展示{be['展示'][int(w)]:.2f}・{pr['コース'][w]}コース 1着確率{x['p1'][w]:.0%}→{pr['p1'][w]:.0%}" for w in sorted({am[0], fm[0], am[2], fm[2]})]
        reason = '展示タイム・進入・風波を反映した再計算: ' + ' / '.join(ch)
    picks = choose(pr['top'], odds) if odds else []
    amt = sum(p[3] for p in picks)
    if not odds: bet = '購入なし(オッズ取得不可)'
    elif not picks: bet = '購入なし(取りガミ基準を満たす買い目なし)'
    else: bet = '3連単 ' + '/'.join(f'{k}({m})' for k, _, _, m in picks)
    print(f"### {pj['venue']} {r}R(締切 {x['deadline']})")
    print(f"- 朝の予想 {am} → 最終予想 **{fm}**(" + (reason if reason else ('修正なし' + ('' if pr['展示込み'] else '。展示タイム未掲載のため朝の確率のまま'))) + ')')
    if be and be['展示']:
        print('- 直前情報: 展示タイム ' + ' '.join(f"{w}:{t:.2f}" for w, t in sorted(be['展示'].items()))
              + ' / スタート展示 ' + (' '.join(f"{c}コース{w}号艇({be['ST'].get(w, '')})" for w, c in sorted(be['コース'].items(), key=lambda z: z[1])) or '未掲載')
              + f" / {be['気象']}")
    else: print('- 直前情報: 展示タイム未掲載(直前情報は未反映)' + (f" / {be['気象']}" if be else ''))
    print('- 1着確率(最終): ' + ' '.join(f"{w}:{p:.0%}" for w, p in pr['p1'].items()) + ('' if pr['展示込み'] else '(朝と同じ計算)'))
    print(f"- オッズ取得時刻: {now}(公式ページ記載のオッズ更新時間 {upd})" if odds else '- オッズ: 取得不可')
    if picks:
        print(f"- 買い目(3連単・合計{amt:,}円):\n\n| 買い目 | 金額 | モデル確率 | オッズ | オッズ×金額 |\n|---|---|---|---|---|")
        for k, p, o, m in picks: print(f"| {k} | {m} | {p:.1%} | {o} | {round(o * m):,} |")
        skip = [k for k, _ in pr['top'][:len(picks) + 3] if k not in [p[0] for p in picks]]
        print(f"\n- 確率上位で見送った目(取りガミ基準 オッズ×金額≧1,500円 と予算の都合): {' '.join(skip) if skip else 'なし'}")
    print(f"- ログ: 買い目「{bet}」 購入額 {amt} 最終予想 {fm}")
    if apply:
        p = os.path.join(ROOT, 'kyotei_log.csv'); rows = list(csv.reader(open(p, encoding='utf-8-sig'))); hit = False
        for row in rows:
            if row and row[0] == pj['date'] and row[1] == pj['venue'] and row[2] == str(r) and (row[5].startswith('仮') or row[5].startswith('未確定')):
                row += [''] * (11 - len(row)); row[5] = bet; row[6] = str(amt); row[9] = fm; row[10] = reason; hit = True
        if hit:
            with open(p, 'w', newline='', encoding='utf-8-sig') as f: csv.writer(f, lineterminator='\n').writerows(rows)
        print('- kyotei_log.csv: ' + ('更新済み' if hit else '該当する未確定行なし(更新せず)'))

if __name__ == '__main__':
    a = sys.argv; out = a[a.index('--out') + 1] if '--out' in a else BASE
    if a[1] == 'morning': morning(a[2], a[3], out)
    elif a[1] == 'final': final(a[2], int(a[3]), '--apply' in a, out)
