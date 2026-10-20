#!/usr/bin/env python3
"""朝の回用: オッズ不使用の「仮買い目」(3連単・合計1,000円)を作る。
使い方: python3 tools/provisional.py 本命 対抗 3番手 4番手 自信度(高|中|低)
  3番手・4番手 = 朝の簡易スコアで本命・対抗に続く艇番。
出力  : 例) 仮 3連単 1-2-3(300)/1-3-2(200)/1-2-4(200)/1-4-2(100)/1-3-4(200)
確定の回(tools/slot.py)が最新オッズ・直前情報で修正・確定する。オッズ未確認のため取りガミ判定はしていない。
"""
import sys

def build(h, t, c, d, conf):
    if conf == "高":   # 本命頭固定 5点
        pts = [(h, t, c, 300), (h, c, t, 200), (h, t, d, 200), (h, d, t, 100), (h, c, d, 200)]
    else:              # 中・低: 本命頭と対抗頭の両方 8点
        pts = [(h, t, c, 200), (h, t, d, 100), (h, c, t, 100), (h, d, t, 100),
               (t, h, c, 200), (t, h, d, 100), (h, c, d, 100), (t, c, h, 100)]
    assert sum(p[3] for p in pts) == 1000
    return "仮 3連単 " + "/".join(f"{a}-{b}-{e}({m})" for a, b, e, m in pts)

if __name__ == "__main__":
    h, t, c, d = sys.argv[1:5]; print(build(h, t, c, d, sys.argv[5]))
