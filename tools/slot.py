#!/usr/bin/env python3
"""確定の回用: 今回の実行で購入を確定すべきレースを判定する。
使い方: python3 tools/slot.py YYYYMMDD [--now HH:MM]   (時刻はJST。省略時は現在のJST)
入力  : data/schedule_YYYYMMDD.json (朝の回が作成) と kyotei_log.csv (「未確定」行)
出力  : JSON。action = NO_ACTION | FINALIZE
  targets : 今回確定するレース(締切が now+MIN_MARGIN より後、now+WINDOW 以内)
  expired : 未確定のまま締切が now+MIN_MARGIN 以前になったレース(仮買い目があればそれを確定、無ければ購入なしとして記録する)
  各レースの "provisional" に朝の回の仮買い目(無ければ空)を入れる
  all_done: 未確定のレースが残っていなければ true
"""
import csv, json, sys, datetime, os

MIN_MARGIN = 4    # 分: 締切まで4分を切ったレースは購入しない
WINDOW = 40       # 分: 今から40分以内に締切のレースを今回確定する

def hm(s):
    h, m = s.split(":"); return int(h) * 60 + int(m)

def main():
    ymd = sys.argv[1]
    if "--now" in sys.argv:
        now = hm(sys.argv[sys.argv.index("--now") + 1])
    else:
        t = datetime.datetime.utcnow() + datetime.timedelta(hours=9); now = t.hour * 60 + t.minute
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sp = os.path.join(base, "data", f"schedule_{ymd}.json")
    if not os.path.exists(sp):
        print(json.dumps({"action": "NO_ACTION", "reason": "schedule無し(朝の回未実行または対象場なし)"}, ensure_ascii=False)); return
    sch = json.load(open(sp, encoding="utf-8"))
    date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
    pending = set(); prov = {}
    for row in csv.reader(open(os.path.join(base, "kyotei_log.csv"), encoding="utf-8-sig")):
        if row and row[0] == date and row[1] == sch["venue"] and (row[5].startswith("未確定") or row[5].startswith("仮")):
            pending.add(int(row[2]))
            if row[5].startswith("仮"): prov[int(row[2])] = row[5]
    targets, expired = [], []
    for r in sch["races"]:
        if r["r"] not in pending: continue
        r["provisional"] = prov.get(r["r"], "")
        d = hm(r["deadline"])
        if d <= now + MIN_MARGIN: expired.append(r)
        elif d <= now + WINDOW: targets.append(r)
    action = "FINALIZE" if (targets or expired) else "NO_ACTION"
    print(json.dumps({"action": action, "venue": sch["venue"], "jcd": sch["jcd"], "targets": targets,
                      "expired": expired, "all_done": len(pending) == len(targets) + len(expired)},
                     ensure_ascii=False))

main()
