"""Resolve static joins by selecting an existing native source pixel.

Every replacement retains its source viewport ID. No colour is calculated or
painted; four neighbouring edges must improve before a change is accepted.
"""
from collections import OrderedDict
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from atlas import dump
from .edges import verify_edges


def repair(root,iterations=4):
    meta=json.loads((root/'manifest.json').read_text())
    sources={s['id']:s for s in json.loads((root/'ownership-sources.json').read_text())}
    left,top,right,bottom=meta['bounds'];frames={};tiles={};changed=set();actions=[]
    def source(ident,x,y):
        if not ident:return None
        if ident not in frames:
            info=sources[ident]
            with Image.open(root/'captures'/f'{info["capture"]}.png')as im:rgb=np.array(im.convert('RGB'))
            with Image.open(root/'temporal'/f'{info["capture"]}.png')as im:mask=np.array(im)>0
            frames[ident]=(info,rgb,mask)
        info,rgb,mask=frames[ident];xx=x-info['scroll'][0];yy=y-info['scroll'][1]
        if not(0<=xx<640 and 0<=yy<340):return None
        return rgb[yy,xx],bool(mask[yy,xx])
    def pixel(x,y):
        if not(left<=x<right and top<=y<bottom):return np.zeros(3,np.uint8),0
        tx,ty=(x-left)//1024,(y-top)//1024
        key=(tx,ty)
        if key not in tiles:
            path=root/'tiles'/f'{tx}_{ty}.png'
            if not path.exists():return np.zeros(3,np.uint8),0
            with Image.open(path)as im:rgb=np.array(im.convert('RGB'))
            with Image.open(root/'ownership'/path.name)as im:owner=np.array(im)
            tiles[key]=(rgb,owner)
        rgb,owner=tiles[key];xx=(x-left)%1024;yy=(y-top)%1024
        return rgb[yy,xx],int(owner[yy,xx])
    def score(x,y,rgb,ident):
        static=total=0
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            other,owner=pixel(x+dx,y+dy)
            if owner==ident:continue
            a=source(ident,x+dx,y+dy);b=source(owner,x,y)
            match=(a is not None and np.array_equal(a[0],other))or(b is not None and np.array_equal(b[0],rgb))
            if match:continue
            own=source(ident,x,y);neighbor=source(owner,x+dx,y+dy)
            moving=any(v is not None and v[1]for v in (a,b,own,neighbor))
            total+=1;static+=not moving
        return static,total
    existing=root/'edge-validation.json'
    report=json.loads(existing.read_text())if existing.exists()else verify_edges(root,meta)
    if report['unmeasured_edges_requiring_review']>len(report['static_samples']):
        report=verify_edges(root,meta)
    for iteration in range(iterations):
        if not report['unmeasured_edges_requiring_review']:break
        progress=0
        for sample in report['static_samples']:
            x,y=sample['world_pixel'];candidate_points=[(x,y),(x+1,y),(x,y+1)]
            best=None
            for px,py in candidate_points:
                if not(left<=px<right and top<=py<bottom):continue
                current,owner=pixel(px,py)
                if not owner:continue
                baseline=score(px,py,current,owner)
                candidates=set(sample['owners'])|{pixel(px+dx,py+dy)[1]for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))}
                for ident in candidates-{0,owner}:
                    original=source(ident,px,py)
                    if original is None:continue
                    rgb=original[0];value=score(px,py,rgb,ident)
                    if value[0]>=baseline[0]:continue
                    rank=(value[0]-baseline[0],value[1]-baseline[1],int(np.abs(rgb.astype(np.int16)-current).sum()))
                    if best is None or rank<best[0]:best=(rank,px,py,ident,rgb.copy(),owner,current.copy())
            if best:
                _,x,y,ident,rgb,old,old_rgb=best;tx,ty=(x-left)//1024,(y-top)//1024
                image,owner=tiles[tx,ty];image[(y-top)%1024,(x-left)%1024]=rgb;owner[(y-top)%1024,(x-left)%1024]=ident
                changed.add((tx,ty));actions.append({'world_pixel':[x,y],'old_owner':old,'new_owner':ident,
                    'old_rgb':old_rgb.tolist(),'new_rgb':rgb.tolist(),'source_pixel_preserved':True});progress+=1
        for tx,ty in changed:
            rgb,owner=tiles[tx,ty];Image.fromarray(rgb).save(root/'tiles'/f'{tx}_{ty}.png',compress_level=4)
            Image.fromarray(owner).save(root/'ownership'/f'{tx}_{ty}.png')
        if not progress:break
        local=set(changed)|{(tx-1,ty)for tx,ty in changed}|{(tx,ty-1)for tx,ty in changed}
        report=verify_edges(root,meta,scan_tiles=local)
    result=verify_edges(root,meta)
    dump(root/'edge-validation.json',result)
    dump(root/'source-pixel-seam-repairs.json',{'method':'choose native viewport ownership with fewer static edge disagreements; no colour synthesis','changes':actions,'modified_tiles':sorted(changed)})
    return {'selected_source_pixels':len(actions),'remaining_static_edges':result['unmeasured_edges_requiring_review'],
            'measured_animation_edges':result['measured_animation_edges']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args()
    print(json.dumps(repair(a.directory),indent=2))

if __name__=='__main__':main()
