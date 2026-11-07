"""Join native captures along matching pixels, retaining per-pixel provenance.

This chooses whole source pixels across overlaps. It never averages colours,
resamples, fills a hole with invented scenery, or changes the source captures.
"""
import argparse
from collections import OrderedDict
import json
from pathlib import Path

import numpy as np
from PIL import Image

from atlas import dump, write_full_png


def minimum_path(energy, centre):
    """Top-to-bottom cut, moving at most one pixel sideways per row."""
    height,width=energy.shape
    if not np.any(energy):return np.full(height,centre,np.int16)
    cost=energy.astype(np.float64)*1e9+np.abs(np.arange(width)-centre)
    previous=cost[0].copy()
    parent=np.empty((height,width),np.int16)
    columns=np.arange(width)
    for y in range(1,height):
        choices=np.stack((np.r_[np.inf,previous[:-1]],previous,np.r_[previous[1:],np.inf]))
        direction=np.argmin(choices,axis=0)-1
        parent[y]=columns+direction
        previous=cost[y]+choices[direction+1,columns]
    path=np.empty(height,np.int16);path[-1]=np.argmin(previous)
    for y in range(height-1,0,-1):path[y-1]=parent[y,path[y]]
    return path


def choose_patch(old,new,owners,left,above,overlap_x=128,overlap_y=84):
    h,w=new.shape[:2]
    delta=np.max(np.abs(old.astype(np.int16)-new.astype(np.int16)),axis=2)
    delta=np.where(owners>0,delta,0)
    choose=np.ones((h,w),bool)
    metrics=[]
    if left:
        path=minimum_path(delta[:,:overlap_x],overlap_x//2)
        choose&=np.arange(w)[None,:]>=path[:,None]
        errors=delta[np.arange(h),path]
        metrics.append({'direction':'vertical','cut_pixels':h,'nonmatching_cut_pixels':int((errors>0).sum()),
                        'maximum_channel_difference_on_cut':int(errors.max())})
    if above:
        path=minimum_path(delta[:overlap_y,:].T,overlap_y//2)
        choose&=np.arange(h)[:,None]>=path[None,:]
        errors=delta[path,np.arange(w)]
        metrics.append({'direction':'horizontal','cut_pixels':w,'nonmatching_cut_pixels':int((errors>0).sum()),
                        'maximum_channel_difference_on_cut':int(errors.max())})
    choose|=owners==0
    return choose,metrics


class TileWriter:
    def __init__(self,root,width,height):
        self.root=root;self.width=width;self.height=height
        self.rgb=np.zeros((1024,width,3),np.uint8)
        self.owner=np.zeros((1024,width),np.uint16)
        self.count=0;self.row=0;self.ty=0;self.tiles=[];self.pixels=0
        self.scale=min(1,4096/max(width,height))
        self.preview=Image.new('RGB',(round(width*self.scale),round(height*self.scale)))
        (root/'tiles').mkdir(exist_ok=True);(root/'ownership').mkdir(exist_ok=True)

    def feed(self,rgb,owners):
        offset=0
        while offset<len(rgb):
            n=min(1024-self.count,len(rgb)-offset)
            self.rgb[self.count:self.count+n]=rgb[offset:offset+n]
            self.owner[self.count:self.count+n]=owners[offset:offset+n]
            self.count+=n;self.row+=n;offset+=n
            if self.count==1024:self.flush()

    def flush(self):
        if not self.count:return
        for tx in range((self.width+1023)//1024):
            x=tx*1024;right=min(x+1024,self.width)
            owner=self.owner[:self.count,x:right]
            if not np.any(owner):continue
            image=Image.fromarray(self.rgb[:self.count,x:right])
            image.save(self.root/'tiles'/f'{tx}_{self.ty}.png',compress_level=4)
            Image.fromarray(owner).save(self.root/'ownership'/f'{tx}_{self.ty}.png')
            self.tiles.append([tx,self.ty]);self.pixels+=int((owner>0).sum())
            px=round(x*self.scale);py=round(self.ty*1024*self.scale)
            xx=round(right*self.scale);yy=round((self.ty*1024+self.count)*self.scale)
            self.preview.paste(image.resize((xx-px,yy-py),Image.Resampling.LANCZOS),(px,py))
        self.count=0;self.ty+=1;self.rgb.fill(0);self.owner.fill(0)

    def finish(self):
        self.flush()
        if self.row!=self.height:raise ValueError(f'Incomplete quilt rows: {self.row}/{self.height}')
        self.preview.save(self.root/'overview.jpg',quality=94,subsampling=0)
        # Remove tiles from the preceding fixed-crop assembly which are no
        # longer part of the quilt; the manifest lists the complete set.
        expected={f'{x}_{y}.png' for x,y in self.tiles}
        for directory in (self.root/'tiles',self.root/'ownership'):
            for path in directory.glob('*.png'):
                if path.name not in expected:path.unlink()


def quilt(root,full=True):
    plan=json.loads((root/'plan.json').read_text())
    coords=set(map(tuple,plan['cores']));ordered=sorted(coords,key=lambda c:(c[1],c[0]))
    if len(ordered)>=65535:raise ValueError('Ownership indices exceed uint16')
    ids={c:i+1 for i,c in enumerate(ordered)}
    source_index=[]
    for c in ordered:
        name=f'{c[0]}_{c[1]}'
        state=json.loads((root/'captures'/f'{name}.json').read_text())
        source_index.append({'id':ids[c],'capture':name,'scroll':state['scroll'],
                             'sha256':state['source_png_sha256']})
    left,top,right,bottom=plan['bounds'];w,h=right-left,bottom-top
    canvas=np.zeros((340,w+128,3),np.uint8);owners=np.zeros((340,w+128),np.uint16)
    writer=TileWriter(root,w,h);metrics=[]
    y0,y1=top//256,bottom//256
    rows={}
    for cx,cy in ordered:rows.setdefault(cy,[]).append(cx)
    for cy in range(y0,y1):
        origin=cy*256-42
        for cx in rows.get(cy,[]):
            x=cx*512-left
            with Image.open(root/'captures'/f'{cx}_{cy}.png') as im:new=np.array(im.convert('RGB'))
            old=canvas[:,x:x+640];own=owners[:,x:x+640]
            has_left=(cx-1,cy)in coords
            has_above=bool(np.any(own[:84]))
            choose,cuts=choose_patch(old,new,own,has_left,has_above)
            old[choose]=new[choose];own[choose]=ids[cx,cy]
            for cut in cuts:metrics.append({'core':[cx,cy],**cut})
        start=max(0,top-origin);stop=min(256,bottom-origin)
        if stop>start:writer.feed(canvas[start:stop,64:64+w],owners[start:stop,64:64+w])
        if cy+1<y1:
            canvas[:84]=canvas[256:].copy();canvas[84:]=0
            owners[:84]=owners[256:].copy();owners[84:]=0
        if (cy-y0)%10==0:print(f'Quilting native row {cy-y0+1}/{y1-y0}',flush=True)
    start=256;stop=min(340,bottom-(cy*256-42))
    if stop>start:writer.feed(canvas[start:stop,64:64+w],owners[start:stop,64:64+w])
    writer.finish()
    dump(root/'ownership-sources.json',source_index);dump(root/'quilt-cuts.json',metrics)
    report={'method':'minimum-difference cuts; original source pixels only, no colour blending',
            'cuts':len(metrics),'nonmatching_cut_pixels':sum(m['nonmatching_cut_pixels']for m in metrics),
            'cuts_requiring_review':sum(m['nonmatching_cut_pixels']>0 for m in metrics),
            'source_owned_pixels':writer.pixels,'temporal_scope':'successive animation frames, not one synchronized island tick'}
    dump(root/'quilting.json',report)
    meta=json.loads((root/'manifest.json').read_text())
    meta.pop('native_viewport_bridges',None)
    if 'statistics'in meta:meta['statistics']['captures']=len(source_index)
    meta.update(tile_count=len(writer.tiles),tiles=writer.tiles,ownership='ownership-sources.json',
                quilted_seams_requiring_review=report['cuts_requiring_review'],
                stitching=report['method'])
    dump(root/'manifest.json',meta)
    if full:write_full_png(root,meta,1024)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--no-full',action='store_true');a=p.parse_args()
    print(json.dumps(quilt(a.directory,not a.no_full),indent=2))

if __name__=='__main__':main()
