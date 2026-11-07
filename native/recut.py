"""Recut native source ownership around static disagreements using a graph cut.

The two original viewports provide every candidate colour. Adjacent ownership
edges use the same native-neighbour predicate as the final auditor. Outside
owners are fixed; a patch is retained only when its measured static edge count
falls. Raw captures and temporal masks are never changed.
"""
import argparse
from collections import Counter, deque
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from atlas import dump
from .edges import verify_edges


class Cut:
    def __init__(self, count):
        self.adj=[[]for _ in range(count)];self.to=[];self.cap=[]

    def edge(self,a,b,capacity,reverse=0):
        i=len(self.to);self.to.extend([b,a]);self.cap.extend([capacity,reverse])
        self.adj[a].append(i);self.adj[b].append(i+1)

    def reachable(self,source,sink):
        n=len(self.adj);sys.setrecursionlimit(max(sys.getrecursionlimit(),n+100))
        while True:
            level=[-1]*n;level[source]=0;q=deque([source])
            while q:
                a=q.popleft()
                for e in self.adj[a]:
                    b=self.to[e]
                    if self.cap[e]and level[b]<0:level[b]=level[a]+1;q.append(b)
            if level[sink]<0:return np.array(level)>=0
            at=[0]*n
            def send(a,amount):
                if a==sink:return amount
                while at[a]<len(self.adj[a]):
                    e=self.adj[a][at[a]];b=self.to[e]
                    if self.cap[e]and level[b]==level[a]+1:
                        sent=send(b,min(amount,self.cap[e]))
                        if sent:self.cap[e]-=sent;self.cap[e^1]+=sent;return sent
                    at[a]+=1
                return 0
            while send(source,10**30):pass


def recut_pair(root,meta,pair):
    sources={s['id']:s for s in json.loads((root/'ownership-sources.json').read_text())}
    frames={};tiles={}
    def frame(ident):
        if not ident:return None
        if ident not in frames:
            s=sources[ident]
            with Image.open(root/'captures'/f'{s["capture"]}.png')as im:rgb=np.array(im.convert('RGB'))
            with Image.open(root/'temporal'/f'{s["capture"]}.png')as im:mask=np.array(im)>0
            frames[ident]=(s,rgb,mask)
        return frames[ident]
    def source(ident,x,y):
        f=frame(ident)
        if f is None:return None
        s,rgb,mask=f;xx=x-s['scroll'][0];yy=y-s['scroll'][1]
        if not(0<=xx<640 and 0<=yy<340):return None
        return rgb[yy,xx],bool(mask[yy,xx])
    left,top,right,bottom=meta['bounds']
    def tile(tx,ty):
        key=tx,ty
        if key not in tiles:
            p=root/'tiles'/f'{tx}_{ty}.png'
            if not p.exists():return None
            with Image.open(p)as im:rgb=np.array(im.convert('RGB'))
            with Image.open(root/'ownership'/p.name)as im:own=np.array(im)
            tiles[key]=(rgb,own)
        return tiles[key]
    def pixel(x,y):
        if not(left<=x<right and top<=y<bottom):return np.zeros(3,np.uint8),0
        t=tile((x-left)//1024,(y-top)//1024)
        if t is None:return np.zeros(3,np.uint8),0
        rgb,own=t;xx=(x-left)%1024;yy=(y-top)%1024
        return rgb[yy,xx],int(own[yy,xx])
    a,b=pair
    if not a or not b:return {'changed':0}
    sa,ar,am=frame(a);sb,br,bm=frame(b)
    x0=max(left,sa['scroll'][0],sb['scroll'][0]);x1=min(right,sa['scroll'][0]+640,sb['scroll'][0]+640)
    y0=max(top,sa['scroll'][1],sb['scroll'][1]);y1=min(bottom,sa['scroll'][1]+340,sb['scroll'][1]+340)
    if x1<=x0 or y1<=y0:return {'changed':0}
    points=[];ids={};owners=[]
    for y in range(y0,y1):
        for x in range(x0,x1):
            _,owner=pixel(x,y)
            if owner in pair:ids[x,y]=len(points);points.append((x,y));owners.append(owner)
    n=len(points);graph=Cut(n+2);start,end=n,n+1
    delta={};motion={}
    for x,y in points:
        av,ma=source(a,x,y);bv,mb=source(b,x,y)
        delta[x,y]=bool(np.any(av!=bv));motion[x,y]=ma or mb
    def weight(mismatch,moving):return (10**12 if not moving else 0)+10**6 if mismatch else 0
    for i,(x,y)in enumerate(points):
        costs=[int(owners[i]!=a),int(owners[i]!=b)]
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            q=x+dx,y+dy;j=ids.get(q)
            if j is not None:
                if j>i:
                    cost=weight(delta[x,y]and delta[q],motion[x,y]or motion[q])
                    if cost:graph.edge(i,j,cost,cost)
                continue
            other,owner=pixel(*q)
            neighbor=source(owner,*q);back=source(owner,x,y)
            for label,ident in enumerate(pair):
                own=source(ident,x,y);across=source(ident,*q)
                match=(across is not None and np.array_equal(across[0],other))or(back is not None and np.array_equal(back[0],own[0]))
                moving=any(v is not None and v[1]for v in (own,across,neighbor,back))
                costs[label]+=weight(not match,moving)
        if costs[1]:graph.edge(start,i,costs[1])
        if costs[0]:graph.edge(i,end,costs[0])
    reachable=graph.reachable(start,end);changed=set();backup={};count=0
    for i,(x,y)in enumerate(points):
        ident=a if reachable[i]else b
        if ident==owners[i]:continue
        key=(x-left)//1024,(y-top)//1024
        rgb,own=tile(*key)
        if key not in backup:backup[key]=(rgb.copy(),own.copy())
        xx=(x-left)%1024;yy=(y-top)%1024;rgb[yy,xx]=source(ident,x,y)[0];own[yy,xx]=ident
        changed.add(key);count+=1
    if not changed:return {'changed':0}
    local=changed|{(tx-1,ty)for tx,ty in changed}|{(tx,ty-1)for tx,ty in changed}
    before=verify_edges(root,meta,scan_tiles=local)
    def save(values):
        for(tx,ty),(rgb,own)in values.items():
            Image.fromarray(rgb).save(root/'tiles'/f'{tx}_{ty}.png',compress_level=4)
            Image.fromarray(own).save(root/'ownership'/f'{tx}_{ty}.png')
    save({k:tiles[k]for k in changed})
    after=verify_edges(root,meta,scan_tiles=local)
    if after['unmeasured_edges_requiring_review']>=before['unmeasured_edges_requiring_review']:
        save(backup);return {'changed':0,'rejected_candidate_pixels':count}
    return dict(changed=count,owners=list(pair),tiles=sorted(changed),
                static_before=before['unmeasured_edges_requiring_review'],static_after=after['unmeasured_edges_requiring_review'])


def recut(root,iterations=4):
    meta=json.loads((root/'manifest.json').read_text());actions=[]
    report=verify_edges(root,meta)
    for _ in range(iterations):
        if not report['unmeasured_edges_requiring_review']:break
        pairs=Counter(tuple(sorted(s['owners']))for s in report['static_samples'])
        progress=0
        for pair,_ in pairs.most_common():
            result=recut_pair(root,meta,pair)
            print(json.dumps(result),flush=True)
            if result['changed']:actions.append(result);progress+=result['changed']
        report=verify_edges(root,meta)
        if not progress:break
    dump(root/'edge-validation.json',report)
    dump(root/'native-graph-recuts.json',dict(method='binary minimum cut of original source ownership; fixed outside owners; fewer static native-neighbour disagreements required',actions=actions))
    if actions:
        w,h=meta['width'],meta['height'];scale=min(1,4096/max(w,h));preview=Image.new('RGB',(round(w*scale),round(h*scale)))
        for tx,ty in meta['tiles']:
            with Image.open(root/'tiles'/f'{tx}_{ty}.png')as im:
                x,y=round(tx*1024*scale),round(ty*1024*scale);xx,yy=round((tx*1024+im.width)*scale),round((ty*1024+im.height)*scale)
                preview.paste(im.resize((xx-x,yy-y),Image.Resampling.LANCZOS),(x,y))
        preview.save(root/'overview.jpg',quality=94,subsampling=0)
    return {k:v for k,v in report.items()if k not in ('samples','static_samples')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);args=parser.parse_args()
    print(json.dumps(recut(args.directory),indent=2))
