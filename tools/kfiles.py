# 公式「競走成績」Kファイル(https://www1.mbrace.or.jp/od2/K/)の取得と解析。
#   python3 kfiles.py fetch YYYYMMDD YYYYMMDD   … 期間のKファイルを data/K に取得・展開(取得済みはスキップ)
#   python3 kfiles.py build                      … data/K の全TXTから data/race_history.csv を作成
#   python3 kfiles.py recent 登番 [登番...]       … 直近10走(日付・場・R・枠・進入・ST・着)を表示
#   python3 kfiles.py payout YYYYMMDD 場コード   … その日の払戻金一覧(3連単/3連複/2連単/2連複)を表示
import sys, os, re, csv, datetime, subprocess
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
KDIR = os.path.join(BASE, 'K'); HIST = os.path.join(BASE, 'race_history.csv')
os.makedirs(KDIR, exist_ok=True)

def fetch(d1, d2):
    import lhafile
    d = datetime.date(int(d1[:4]), int(d1[4:6]), int(d1[6:]))
    e = datetime.date(int(d2[:4]), int(d2[4:6]), int(d2[6:]))
    while d <= e:
        y = d.strftime('%y%m%d'); txt = os.path.join(KDIR, f'K{y}.TXT')
        if not os.path.exists(txt):
            url = f'https://www1.mbrace.or.jp/od2/K/{d:%Y%m}/k{y}.lzh'
            lz = os.path.join(KDIR, f'k{y}.lzh')
            r = subprocess.run(['curl', '-sS', '-f', '-o', lz, url])
            if r.returncode == 0:
                f = lhafile.Lhafile(lz)
                for i in f.infolist(): open(os.path.join(KDIR, i.filename.upper()), 'wb').write(f.read(i.filename))
                print('ok', y)
            else: print('取得不可', y)
        d += datetime.timedelta(days=1)

def parse(path):
    t = open(path, 'rb').read().decode('cp932', 'replace')
    date = '20' + os.path.basename(path)[1:7]
    out = []; jcd = None; rno = None
    for line in t.splitlines():
        m = re.match(r'^(\d\d)KBGN', line)
        if m: jcd = m.group(1); continue
        m = re.match(r'^\s{2,4}(\d{1,2})R\s{3,}\S', line)
        if m and 'H' in line: rno = int(m.group(1)); continue
        if jcd and rno and len(line) > 30 and re.match(r'^\s\s\S\S\s\s\d\s\d{4}\s', line):
            rest = line[21:].split()
            out.append(dict(日付=date, 場=jcd, R=rno, 着=line[2:4].strip(), 枠=line[6], 登番=line[8:12],
                            選手=line[13:21].replace('　', ''), モーター=rest[0], ボート=rest[1],
                            展示=rest[2] if len(rest) > 2 else '', 進入=rest[3] if len(rest) > 3 else '',
                            ST=rest[4] if len(rest) > 4 else ''))
    return out

def build():
    rows = []
    for fn in sorted(os.listdir(KDIR)):
        if fn.endswith('.TXT'): rows += parse(os.path.join(KDIR, fn))
    with open(HIST, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(len(rows), 'rows ->', HIST)

def recent(tobans, n=10):
    rows = list(csv.DictReader(open(HIST, encoding='utf-8-sig')))
    for tb in tobans:
        r = sorted([x for x in rows if x['登番'] == tb], key=lambda x: (x['日付'], int(x['R'])), reverse=True)[:n]
        print(f'== {tb} 直近{len(r)}走 (日付 場 R 枠 進入 ST 着)')
        for x in r: print(x['日付'], x['場'], x['R'] + 'R', x['枠'], x['進入'], x['ST'], x['着'])

def payout(date, jcd):
    p = os.path.join(KDIR, f'K{date[2:]}.TXT'); t = open(p, 'rb').read().decode('cp932', 'replace')
    i = t.find(f'{jcd}KBGN'); j = t.find('[払戻金]', i); k = t.find('\n\n\n', j)
    print(t[j:k])

if __name__ == '__main__':
    c = sys.argv[1]
    if c == 'fetch': fetch(sys.argv[2], sys.argv[3])
    elif c == 'build': build()
    elif c == 'recent': recent(sys.argv[2:])
    elif c == 'payout': payout(sys.argv[2], sys.argv[3])
