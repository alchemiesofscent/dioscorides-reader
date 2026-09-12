"""Align two editions of the same Greek text as token streams, then read chapter
correspondences off the alignment. No hand editing; low-confidence rows are flagged."""
import re, sys, json, time, unicodedata, difflib
from xml.etree import ElementTree as ET
T='{http://www.tei-c.org/ns/1.0}'
SKIP={'note','rdg','ref','fw','head','num'}   # apparatus, footnotes, furniture, headings, numerals-as-elements

def text_of(el):
    out=[]
    def walk(e):
        if e.tag.split('}')[-1] in SKIP: return
        if e.text: out.append(e.text)
        for c in e:
            walk(c)
            if c.tail: out.append(c.tail)
    walk(el); return ''.join(out)

def norm_tokens(s):
    s=unicodedata.normalize('NFD',s)
    s=''.join(ch for ch in s if not unicodedata.combining(ch))   # strip accents/breathings
    s=s.lower().replace('ς','σ')
    return [t for t in re.findall(r'[α-ω]+',s) if len(t)>1]

def chapters(path, book, id_pattern=None):
    root=ET.parse(path).getroot()
    out=[]
    for bk in root.iter(T+'div'):
        if bk.get('subtype')=='book' and bk.get('n')==book:
            for d in bk.iter(T+'div'):
                if d.get('subtype')=='chapter':
                    xid=d.get('{http://www.w3.org/XML/1998/namespace}id','')
                    if id_pattern and not re.search(id_pattern,xid): continue
                    out.append((d.get('n'), xid, norm_tokens(text_of(d))))
    return out

def stream(chs):
    toks=[]; owner=[]
    for i,(n,xid,tk) in enumerate(chs):
        toks.extend(tk); owner.extend([i]*len(tk))
    return toks, owner

def align(A,B):
    sm=difflib.SequenceMatcher(None,A,B,autojunk=False)
    mapping=[None]*len(A)
    for i,j,n in sm.get_matching_blocks():
        for k in range(n): mapping[i+k]=j+k
    return mapping, sm

def concordance(wch, sch, mapping, sowner):
    rows=[]
    scount=[len(c[2]) for c in sch]
    pos=0
    for wi,(wn,wid,wt) in enumerate(wch):
        hits={}
        aligned=0
        for k in range(len(wt)):
            j=mapping[pos+k]
            if j is not None:
                aligned+=1; si=sowner[j]; hits[si]=hits.get(si,0)+1
        pos+=len(wt)
        if not wt:
            rows.append(dict(w=wn, relation='empty', evidence='no tokens')); continue
        if not hits:
            rows.append(dict(w=wn, w_tokens=len(wt), relation='absent', evidence='0 aligned tokens')); continue
        for si,c in sorted(hits.items(), key=lambda x:-x[1]):
            cov_w=c/len(wt); cov_s=c/scount[si]
            if cov_w<0.05 and c<8: continue
            rel = ('same' if cov_w>=0.6 and cov_s>=0.6 else
                   'contained-in' if cov_w>=0.6 else
                   'contains' if cov_s>=0.6 else 'overlaps')
            rows.append(dict(w=wn, s=sch[si][0], s_id=sch[si][1], relation=rel,
                             shared=c, cov_w=round(cov_w,2), cov_s=round(cov_s,2)))
    return rows

if __name__=='__main__':
    wpath,spath,book=sys.argv[1],sys.argv[2],sys.argv[3]
    t=time.time()
    wch=chapters(wpath,book); sch=chapters(spath,book,id_pattern=r'-grc$')
    W,wown=stream(wch); S,sown=stream(sch)
    print(f"Wellmann book {book}: {len(wch)} chapters, {len(W)} tokens; Sprengel: {len(sch)} chapters, {len(S)} tokens", file=sys.stderr)
    mapping,sm=align(W,S)
    print(f"aligned in {time.time()-t:.1f}s; ratio {sm.ratio():.3f}; tokens aligned {sum(m is not None for m in mapping)}/{len(W)}", file=sys.stderr)
    rows=concordance(wch,sch,mapping,sown)
    json.dump(rows,open(sys.argv[4],'w'),ensure_ascii=False,indent=0)
    from collections import Counter
    print(Counter(r['relation'] for r in rows), file=sys.stderr)
