# Kファイルからレース単位の情報(天候・風・波・3連単の組番と払戻)を data/races.csv に出力
import os,re,csv
BASE=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','data'); KDIR=os.path.join(BASE,'K')
rows=[]
for fn in sorted(os.listdir(KDIR)):
    if not fn.endswith('.TXT'): continue
    date='20'+fn[1:7]; t=open(os.path.join(KDIR,fn),'rb').read().decode('cp932','replace')
    jcd=None; cur=None
    for line in t.splitlines():
        m=re.match(r'^(\d\d)KBGN',line)
        if m: jcd=m.group(1); continue
        m=re.match(r'^\s{2,4}(\d{1,2})R\s{3,}(.*)$',line)
        if m and 'H1' in line:
            cur=dict(日付=date,場=jcd,R=int(m.group(1)),天候='',風向='',風速='',波='',三連単='',払戻='')
            w=re.search(r'H\d{4}m\s+(\S+)\s+風\s+(\S+)\s+(\d+)m\s+波\s+(\d+)cm',line)
            if w: cur.update(天候=w.group(1),風向=w.group(2),風速=w.group(3),波=w.group(4))
            rows.append(cur); continue
        m=re.match(r'^\s+３連単\s+(\d-\d-\d)\s+(\d+)',line)
        if m and cur and not cur['三連単']: cur['三連単']=m.group(1); cur['払戻']=m.group(2)
with open(os.path.join(BASE,'races.csv'),'w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows),'races', sum(1 for r in rows if r['三連単']),'with 3連単')
