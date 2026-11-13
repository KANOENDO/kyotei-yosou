#!/usr/bin/env python3
"""前日の検証(仮想購入)。公式Kファイルの3連単結果・払戻金を kyotei_log.csv に転記し、前日分と累計の集計を表示する。
使い方: python3 tools/verify.py YYYYMMDD [--dry]   (事前に kfiles.py fetch その日 → build)
  買い目欄が「仮」「未確定」のまま残った行は購入なし(購入額0)として扱う。仮想払戻 = 公式払戻金 × 金額 ÷ 100。
  比較基準として「常に1号艇を本命にした場合」の1着率も出す。
"""
import sys, os, re, csv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JCD = {'大村': '24', '徳山': '18', '下関': '19'}

def official(ymd, jcd):
    """→ {R: (3連単の組番, 払戻金)}, {R: 1着艇の進入コース}"""
    t = open(os.path.join(ROOT, 'data', 'K', f'K{ymd[2:]}.TXT'), 'rb').read().decode('cp932', 'replace')
    i = t.find(f'{jcd}KBGN'); j = t.find(f'{jcd}KEND', i); t = t[i:j if j > 0 else len(t)]
    pay = {}; win = {}; r = None
    for line in t.splitlines():
        m = re.match(r'^\s{2,4}(\d{1,2})R\s{3,}\S', line)
        if m and 'H' in line: r = int(m.group(1)); continue
        m = re.match(r'^\s+３連単\s+(\d-\d-\d)\s+(\d+)', line)
        if m and r and r not in pay: pay[r] = (m.group(1), int(m.group(2)))
        if r and re.match(r'^\s\s01\s\s\d\s\d{4}\s', line):
            rest = line[21:].split(); win[r] = rest[3] if len(rest) > 3 else ''
    return pay, win

def bought(r): return r[6] not in ('', '0')

def stats(rs):
    b = [r for r in rs if bought(r) and r[7]]; n = len(b)
    if not n: return None
    a = sum(int(r[6]) for r in b); p = sum(int(r[8] or 0) for r in b); f = lambda r: (r[9] if len(r) > 9 and r[9] else r[3])
    return dict(n=n, buy=a, pay=p, hit=sum(int(r[8] or 0) > 0 for r in b), gami=sum(0 < int(r[8] or 0) < int(r[6]) for r in b),
                m1=sum(r[7][0] == r[3][0] for r in b), m2=sum(r[3][0] in r[7][:3] for r in b),
                f1=sum(r[7][0] == f(r)[0] for r in b), f2=sum(f(r)[0] in r[7][:3] for r in b),
                b1=sum(r[7][0] == '1' for r in b), mod=[r for r in b if f(r) != r[3]])

def show(name, s):
    if not s: print(f'{name}: 購入なし'); return
    n = s['n']
    print(f"{name}: 購入{n}R・仮想購入{s['buy']:,}円・仮想払戻{s['pay']:,}円・的中{s['hit']}R({s['hit']/n:.1%})・回収率{s['pay']/s['buy']:.1%}"
          f"・仮想収支{s['pay']-s['buy']:+,}円・取りガミ{s['gami']}件")
    print(f"  本命1着: 朝{s['m1']}/{n}({s['m1']/n:.1%}) 最終{s['f1']}/{n}({s['f1']/n:.1%}) | 2着以内: 朝{s['m2']}/{n}({s['m2']/n:.1%}) 最終{s['f2']}/{n}({s['f2']/n:.1%})"
          f" | 比較基準(常に1号艇を本命){s['b1']}/{n}({s['b1']/n:.1%})")
    good = sum(r[7][0] == r[9][0] for r in s['mod']); print(f"  本命・対抗の修正{len(s['mod'])}件(うち最終本命が1着{good}件)")

def main():
    ymd = sys.argv[1]; date = f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}'; p = os.path.join(ROOT, 'kyotei_log.csv')
    rows = list(csv.reader(open(p, encoding='utf-8-sig'))); day = [r for r in rows[1:] if r and r[0] == date]
    if not day: print('前日レポートなし(ログに該当日の行なし)'); return
    pay, win = official(ymd, JCD[day[0][1]])
    print(f'## {date} {day[0][1]} 検証(すべて仮想)\n| R | 朝-最終 | 自信 | 最終買い目 | 結果 | 公式払戻/100円 | 仮想払戻 | 判定 |\n|---|---|---|---|---|---|---|---|')
    for r in day:
        R = int(r[2]); r += [''] * (11 - len(r))
        if r[5].startswith(('仮', '未確定')): r[6] = '0'
        if R not in pay: print(f'| {R} | {r[3]} | {r[4]} | {r[5]} | 取得不可 | - | - | - |'); continue
        res, yen = pay[R]; ret = sum(yen * int(m) // 100 for k, m in re.findall(r'(\d-\d-\d)\((\d+)\)', r[5]) if k == res) if bought(r) else 0
        r[7] = res; r[8] = str(ret)
        print(f"| {R} | {r[3]}→{r[9] or r[3]} | {r[4]} | {r[5] if bought(r) else '購入なし(' + r[5][:12] + ')'} | {res} | {yen:,} | {ret:,} | {'◯' if ret else ('✕' if bought(r) else '-')} |")
    print(f"前日の1コース(進入)1着: {sum(v == '1' for v in win.values())}/{len(win)}")
    if '--dry' not in sys.argv:
        with open(p, 'w', newline='', encoding='utf-8-sig') as f: csv.writer(f, lineterminator='\n').writerows(rows)
    allr = [r for r in rows[1:] if r and len(r) > 8 and r[7]]
    show('前日', stats(day)); show('累計', stats(allr))
    for nm, rs in (('前日', day), ('累計', allr)):
        for c in '高中低':
            s = stats([r for r in rs if r[4].startswith(c)])
            if s: print(f"  {nm} 自信度{c}: {s['n']}R 回収率{s['pay']/s['buy']:.1%} 的中{s['hit']}R 本命1着{s['m1']/s['n']:.1%}")
    v2 = stats([r for r in allr if r[0] >= '2026-11-14'])
    if v2: show('モデルv2切替後(2026-11-14〜)', v2)

main()
