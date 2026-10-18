# 公式「ファン手帳(期別成績)」fanYYMM.txt(cp932, 1レコード416バイト)を
# 選手×コース別成績のCSVに変換する。レイアウト: https://www.boatrace.jp/owpc/pc/extra/data/layout.html
# 使い方: python3 parse_fan.py fan2604.txt course_stats.csv
import sys, csv
def num(b, d=0):
    s = b.decode('ascii', 'replace').strip()
    if not s.isdigit(): return None
    return int(s) / (10 ** d) if d else int(s)
src, dst = sys.argv[1], sys.argv[2]
recs = [r for r in open(src, 'rb').read().split(b'\r\n') if len(r) == 416]
head = ['登番','氏名','支部','級','算出期間自','算出期間至','全体勝率','全体2連率','全体出走','全体平均ST']
for c in range(1, 7):
    head += [f'{c}C進入', f'{c}C1着', f'{c}C2着', f'{c}C3着', f'{c}C1着率', f'{c}C2連率', f'{c}C3連率', f'{c}C平均ST', f'{c}C平均ST順位']
with open(dst, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(head)
    for r in recs:
        row = [r[0:4].decode(), r[4:20].decode('cp932').replace('　','').strip(), r[35:39].decode('cp932').replace('　','').strip(),
               r[39:41].decode('cp932').strip(), r[179:187].decode(), r[187:195].decode(),
               num(r[58:62], 2), num(r[62:66], 1), num(r[72:75]), num(r[79:82], 2)]
        for c in range(1, 7):
            o = 82 + (c - 1) * 13          # 進入回数3, 複勝率4, 平均ST3, 平均ST順位3
            p = 198 + (c - 1) * 34         # 1〜6着回数 各3
            n = num(r[o:o+3]) or 0
            w1, w2, w3 = num(r[p:p+3]) or 0, num(r[p+3:p+6]) or 0, num(r[p+6:p+9]) or 0
            pct = lambda x: round(100 * x / n, 1) if n else ''
            row += [n, w1, w2, w3, pct(w1), pct(w1 + w2), pct(w1 + w2 + w3),
                    num(r[o+7:o+10], 2) if n else '', num(r[o+10:o+13], 2) if n else '']
        w.writerow(row)
print(f'{len(recs)} records -> {dst}')
