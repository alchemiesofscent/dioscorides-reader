import sys, json, csv
sys.path.insert(0, __import__('os').path.dirname(__file__))
from align_chapters import *
from collections import Counter
OUT=__import__('os').environ.get('ALIGN_OUT','build/alignment/')

def seq_align(A, B, sim, gap=-0.15):
    """Needleman-Wunsch over two chapter sequences with a similarity function; returns pairs."""
    n,m=len(A),len(B); INF=-1e9
    F=[[0.0]*(m+1) for _ in range(n+1)]; P=[[None]*(m+1) for _ in range(n+1)]
    for i in range(1,n+1): F[i][0]=F[i-1][0]+gap; P[i][0]='u'
    for j in range(1,m+1): F[0][j]=F[0][j-1]+gap; P[0][j]='l'
    for i in range(1,n+1):
        for j in range(1,m+1):
            d=F[i-1][j-1]+sim(A[i-1],B[j-1]); u=F[i-1][j]+gap; l=F[i][j-1]+gap
            F[i][j]=max(d,u,l); P[i][j]='d' if F[i][j]==d else ('u' if F[i][j]==u else 'l')
    pairs=[]; i,j=n,m
    while i>0 or j>0:
        p=P[i][j]
        if p=='d': pairs.append((i-1,j-1)); i-=1; j-=1
        elif p=='u': pairs.append((i-1,None)); i-=1
        else: pairs.append((None,j-1)); j-=1
    return pairs[::-1]

def heads(root):
    out={}
    for bk in root.iter(T+'div'):
        if bk.get('subtype')!='book': continue
        lst=[]
        for d in bk.iter(T+'div'):
            if d.get('subtype')=='chapter':
                h=d.find(T+'head')
                grc=' '.join((f.text or '') for f in h.iter(T+'foreign')) if h is not None else ''
                lst.append((d.get('n'), set(norm_tokens(grc)), ' '.join(h.itertext())[:60] if h is not None else ''))
        out[bk.get('n')]=lst
    return out
beckh=heads(ET.parse('editions/beck/tei/beck2020_fresh_diplomatic_epidoc.xml').getroot())
berh=heads(ET.parse('editions/berendes/tei/berendes1902_epidoc.xml').getroot())

allrows=[]; exceptions=[]; totals=Counter(); trans_stats={}
for book in '12345':
    wch=chapters(f'editions/wellmann/tei/wellmann_book{book}.xml',book); sch=chapters('editions/sprengel/tei/sprengel1829_epidoc.xml',book,id_pattern=r'-grc$')
    W,wown=stream(wch); S,sown=stream(sch); mapping,sm=align(W,S)
    rows=concordance(wch,sch,mapping,sown)
    by={}
    for r in rows: by.setdefault(r['w'],[]).append(r)
    order=[c[0] for c in wch]; sidx={c[0]:i for i,c in enumerate(sch)}
    def anchor(k):
        rs=[r for r in by.get(order[k],[]) if 's' in r and r['relation'] in ('same','contains','contained-in') and r['s'] in sidx]
        return sidx[rs[0]['s']] if rs else None
    for i,wn in enumerate(order):
        rs=by.get(wn,[])
        if rs and all(r['relation']=='absent' for r in rs):
            wt=[c for c in wch if c[0]==wn][0][2]; wset=set(wt)
            lo=next((anchor(k) for k in range(i-1,-1,-1) if anchor(k) is not None),0)
            hi=next((anchor(k) for k in range(i+1,len(order)) if anchor(k) is not None),len(sch)-1)
            cands=sch[max(0,lo-2):hi+3]
            best=max(((len(wset&set(c[2]))/max(1,len(wset)),c) for c in cands), default=(0,None))
            if best[0]>=0.5:
                c=best[1]; by[wn]=[dict(w=wn,s=c[0],s_id=c[1],relation='same',shared=len(wset&set(c[2])),cov_w=round(best[0],2),cov_s=round(len(wset&set(c[2]))/len(set(c[2])),2),evidence='local-fallback')]
            else: exceptions.append((book,'wellmann',wn,'absent-in-sprengel',round(best[0],2)))
    for wn in order:
        for r in by.get(wn,[]):
            r['book']=book; allrows.append(r); totals[r['relation']]+=1
            if r['relation']=='overlaps' and r.get('cov_w',0)<0.3 and r.get('cov_s',0)<0.3: exceptions.append((book,'wellmann',wn,'weak-overlap-sprengel',r.get('s')))
    # translations: sequence-align chapter headings against Wellmann chapter openings
    wseq=[(c[0], set(c[2][:15])) for c in wch]
    def sim(a,b): 
        inter=len(a[1]&b[1]); return (0.6+0.4*min(1,inter/2)) if inter else -0.3
    for name,hs in (('beck2020',beckh.get(book,[])),('berendes1902',berh.get(book,[]))):
        pairs=seq_align(wseq,hs,sim)
        matched=sum(1 for i,j in pairs if i is not None and j is not None and wseq[i][1]&hs[j][1])
        unmatched_w=[wseq[i][0] for i,j in pairs if j is None]
        unmatched_t=[hs[j][0] for i,j in pairs if i is None]
        lowconf=[(wseq[i][0],hs[j][0]) for i,j in pairs if i is not None and j is not None and not (wseq[i][1]&hs[j][1])]
        trans_stats[(book,name)]=(len(wseq),len(hs),matched,len(unmatched_w),len(unmatched_t),len(lowconf))
        for i,j in pairs:
            if i is not None and j is not None:
                allrows.append(dict(book=book,w=wseq[i][0],s=hs[j][0],s_id=name,relation='same' if wseq[i][1]&hs[j][1] else 'positional',shared=len(wseq[i][1]&hs[j][1]),evidence='heading-sequence-alignment'))
        for w,t in lowconf: exceptions.append((book,name,w,'heading-no-overlap',t))
        for w in unmatched_w: exceptions.append((book,name,w,'no-translation-chapter',''))
        for t in unmatched_t: exceptions.append((book,name,t,'translation-chapter-unplaced',''))
    print(f"book {book}: W {len(wch)} / S {len(sch)}; text ratio {sm.ratio():.2f}")
print("Wellmann<->Sprengel relations:",dict(totals))
print("translations (book,edition): (W chapters, T chapters, matched by heading, W unplaced, T unplaced, positional-only)")
for k,v in trans_stats.items(): print("  ",k,v)
print("exceptions for a human:",len(exceptions))
c=Counter(e[3] for e in exceptions); print(dict(c))
for e in exceptions[:40]: print("  ",e)
with open(OUT+'dioscorides-concordance.tsv','w',encoding='utf-8',newline='') as f:
    w=csv.writer(f,delimiter='\t'); w.writerow(['book','wellmann','other_unit','other_edition_or_id','relation','shared_tokens','cov_wellmann','cov_other','evidence'])
    for r in allrows: w.writerow([r['book'],r['w'],r.get('s',''),r.get('s_id',''),r['relation'],r.get('shared',''),r.get('cov_w',''),r.get('cov_s',''),r.get('evidence','token-alignment')])
json.dump(exceptions,open(OUT+'exceptions.json','w'),ensure_ascii=False,indent=0)
print("rows:",len(allrows))
