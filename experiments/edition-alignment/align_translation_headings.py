import sys, json
sys.path.insert(0, __import__('os').path.dirname(__file__))
from align_chapters import *
def seq_align(A, B, sim, gap=-0.15):
    n,m=len(A),len(B)
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
def stems(tokens): return {t[:4] for t in tokens if len(t)>=4 and t not in ('περι','σκευ')}
def heads(root):
    out={}
    for bk in root.iter(T+'div'):
        if bk.get('subtype')!='book': continue
        lst=[]
        for d in bk.iter(T+'div'):
            if d.get('subtype')=='chapter':
                h=d.find(T+'head')
                grc=' '.join((f.text or '') for f in h.iter(T+'foreign')) if h is not None else ''
                lst.append((d.get('n'), stems(norm_tokens(grc))))
        out[bk.get('n')]=lst
    return out
beckh=heads(ET.parse('editions/beck/tei/beck2020_fresh_diplomatic_epidoc.xml').getroot())
berh=heads(ET.parse('editions/berendes/tei/berendes1902_epidoc.xml').getroot())
stable={}
for line in open('editions/sprengel/sprengel_chapter_table.tsv',encoding='utf-8').read().splitlines()[1:]:
    n,xid,la,grc=line.split('\t'); b,c=n.split('.',1); stable.setdefault(b,[]).append((c,stems(norm_tokens(grc))))
def sim(a,b):
    inter=len(a[1]&b[1]); return (0.7+0.3*min(1,inter/2)) if inter else -0.3
tot=dict(matched=0,positional=0,unplaced_w=0,unplaced_t=0)
for book in '12345':
    wch=chapters(f'editions/wellmann/tei/wellmann_book{book}.xml',book)
    wseq=[(c[0], stems(c[2][:15])) for c in wch]
    for name,src,hs in (('beck2020->wellmann',wseq,beckh.get(book,[])),('berendes1902->sprengel',stable.get(book,[]),berh.get(book,[]))):
        pairs=seq_align(src,hs,sim)
        matched=sum(1 for i,j in pairs if i is not None and j is not None and src[i][1]&hs[j][1])
        pos=[(src[i][0],hs[j][0]) for i,j in pairs if i is not None and j is not None and not (src[i][1]&hs[j][1])]
        uw=[src[i][0] for i,j in pairs if j is None]; ut=[hs[j][0] for i,j in pairs if i is None]
        print(f"book {book} {name}: {len(src)} vs {len(hs)} chapters; matched {matched}, positional-only {len(pos)}, source unplaced {len(uw)}, translation unplaced {len(ut)}")
        if pos: print("     positional:", pos[:8])
        if uw: print("     source unplaced:", uw[:10])
        if ut: print("     translation unplaced:", ut[:10])
        tot['matched']+=matched; tot['positional']+=len(pos); tot['unplaced_w']+=len(uw); tot['unplaced_t']+=len(ut)
print(tot)
