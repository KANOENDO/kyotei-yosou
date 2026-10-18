import csv,json,math,re,itertools
B="/sessions/"  # placeholder
import os
BASE=os.path.expanduser('~/mnt/Documents/競艇予想')
cs={r['登番']:r for r in csv.DictReader(open(BASE+'/data/course_stats_2604.csv',encoding='utf-8-sig'))}
hist=list(csv.DictReader(open(BASE+'/data/race_history.csv',encoding='utf-8-sig')))
odds=json.load(open('odds.json'))
E={4:[3687,5209,4654,5243,3473,3784],5:[4413,4072,4094,3912,5093,3905],6:[3613,5011,3957,3556,4861,3564],
7:[4063,4639,4824,4315,4106,5392],8:[3951,3473,4422,4261,5208,5452],9:[4140,4747,4060,4072,4750,4298],
10:[3963,4028,3613,3687,4094,4055],11:[3556,5270,4063,4523,5209,3912],12:[3966,3957,5269,4413,4639,4654]}
MOT={4:[32.10,31.91,33.77,26.83,17.11,32.91],5:[23.46,17.57,40.91,26.92,37.50,40.45],6:[25.64,38.55,28.57,32.18,31.58,31.71],
7:[16.46,31.87,25.64,35.63,25.00,33.33],8:[46.59,17.11,13.75,50.00,43.53,46.51],9:[46.25,31.76,29.55,17.57,30.26,23.17],
10:[33.33,24.69,25.64,32.10,40.91,32.50],11:[32.18,35.80,16.46,14.47,31.91,26.92],12:[29.55,28.57,27.71,23.46,31.87,33.77]}
VW=[58.0,13.7,11.4,9.9,6.1,1.5]   # 大村 コース別1着率(2026/7-9)
V3=[85.0,60.0,55.0,48.0,35.0,18.0] # 3連率の事前値(目安)
def recent(tb,n=10):
    r=sorted([x for x in hist if x['登番']==str(tb)],key=lambda x:(x['日付'],int(x['R'])),reverse=True)[:n]
    fin=[int(x['着']) if x['着'].isdigit() else 6 for x in r]
    st=[float(x['ST']) for x in r if re.match(r'^0\.\d\d$',x['ST'])]
    return r,fin,st
def ex_times(r):
    s=open(f'b{r}.html',encoding='utf-8').read()
    return [float(x) for x in re.findall(r'<td rowspan="4">(\d\.\d\d)</td>',s)]
out={}
for r,tbs in E.items():
    ex=ex_times(r); W=[];P=[];info=[]
    for i,tb in enumerate(tbs):
        c=i+1; s=cs.get(str(tb)); k=10
        if s:
            n=int(s[f'{c}C進入']); w1=int(s[f'{c}C1着']); w3=w1+int(s[f'{c}C2着'])+int(s[f'{c}C3着'])
        else: n=w1=w3=0
        wr=(w1+k*VW[i]/100)/(n+k); pr=(w3+k*V3[i]/100)/(n+k)
        rr,fin,st=recent(tb); af=sum(fin)/len(fin) if fin else 3.5
        form=math.exp(0.25*(3.5-af)); mot=1+(MOT[r][i]-33)/100
        exm=math.exp(-(ex[i]-sum(ex)/6)*3) if len(ex)==6 else 1
        W.append(wr*form*mot*exm); P.append(pr*form*mot*exm)
        info.append(dict(艇=c,登番=tb,コース進入=n,コース1着率=round(100*w1/n,1) if n else None,コース3連率=round(100*w3/n,1) if n else None,
                         直近10走=''.join(str(f) for f in fin),平均着=round(af,2),平均ST=round(sum(st)/len(st),3) if st else None,
                         M2連=MOT[r][i],展示=ex[i] if len(ex)==6 else None))
    sw=sum(W); pw=[w/sw for w in W]
    probs={}
    for a,b,c in itertools.permutations(range(6),3):
        pb=P[b]/(sum(P)-P[a]); pc=P[c]/(sum(P)-P[a]-P[b])
        probs[f'{a+1}-{b+1}-{c+1}']=pw[a]*pb*pc
    od=odds[str(r)]['odds']
    inv={k:1/o for k,o in od.items() if o}; Z=sum(inv.values())
    cand=[]
    for k,o in od.items():
        if not o: continue
        p=0.5*probs[k]+0.5*inv[k]/Z
        cand.append((k,p,o,p*o))
    # 候補: 推定確率2%以上、EV上位
    cand=[x for x in cand if x[1]>=0.025]; cand.sort(key=lambda x:-x[3])
    picks=[];total=0
    for k,p,o,ev in cand:
        need=max(100,math.ceil(1500/o/100)*100)
        if total+need>1000: continue
        picks.append([k,p,o,ev,need]); total+=need
        if len(picks)>=6: break
    # 余りをEV上位に、条件(オッズ×金額≧1500)は増額で崩れない
    i=0
    while total<1000 and picks:
        picks[i%len(picks)][4]+=100; total+=100; i+=1
    out[r]=dict(info=info,win=[round(100*x,1) for x in pw],picks=[dict(買い目=k,推定確率=round(100*p,1),オッズ=o,期待値=round(ev,2),金額=s) for k,p,o,ev,s in picks],total=total,odds_time=odds[str(r)]['time'])
json.dump(out,open('bets_blend.json','w'),ensure_ascii=False,indent=1)
for r,v in out.items():
    print(f"## {r}R 1着推定% {v['win']} オッズ{v['odds_time']}")
    for x in v['info']: print('  ',x)
    for x in v['picks']: print('   BET',x)
    print('   total',v['total'])
