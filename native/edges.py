"""Check actual stitched boundaries against adjacent pairs in native captures."""
from collections import OrderedDict
import json
import numpy as np
from PIL import Image


def verify_edges(root,meta,scan_tiles=None):
    sources={s['id']:s for s in json.loads((root/'ownership-sources.json').read_text())}
    cache=OrderedDict();tiles=OrderedDict();keys=set(map(tuple,meta['tiles']))
    examined=bad=temporal_bad=unverified=0;maximum=0;samples=[];static_samples=[]
    left,top=meta['bounds'][:2]
    def frame(ident):
        if ident not in cache:
            entry=sources[int(ident)]
            with Image.open(root/'captures'/f'{entry["capture"]}.png')as im:rgb=np.array(im.convert('RGB'))
            with Image.open(root/'temporal'/f'{entry["capture"]}.png')as im:mask=np.array(im)>0
            cache[ident]=(entry,rgb,mask)
            while len(cache)>260:cache.popitem(last=False)
        return cache[ident]
    def tile(key):
        if key not in tiles:
            if key not in keys:return None
            with Image.open(root/'tiles'/f'{key[0]}_{key[1]}.png')as im:rgb=np.array(im.convert('RGB'))
            with Image.open(root/'ownership'/f'{key[0]}_{key[1]}.png')as im:owner=np.array(im)
            tiles[key]=(rgb,owner)
            while len(tiles)>8:tiles.popitem(last=False)
        return tiles[key]
    def edges(p,q,a,b,wx,wy,dx,dy):
        nonlocal examined,bad,temporal_bad,maximum,unverified
        selected=(a!=b)&((a>0)|(b>0))&(np.any(p,axis=-1)|np.any(q,axis=-1))
        where=np.where(selected)
        if not len(where[0]):return
        p=p[where];q=q[where];a=a[where];b=b[where]
        x=np.broadcast_to(wx,selected.shape)[where];y=np.broadcast_to(wy,selected.shape)[where]
        pair=a.astype(np.uint64)*65536+b
        examined+=len(x)
        for code in np.unique(pair):
            pick=pair==code;aa,bb=int(code)//65536,int(code)%65536
            px,py=x[pick],y[pick];pr,qr=p[pick],q[pick]
            error=np.full(len(px),256,np.int16);moving=np.zeros(len(px),bool)
            if aa:
                entry,rgb,mask=frame(aa);sx=px+dx-entry['scroll'][0];sy=py+dy-entry['scroll'][1]
                valid=(sx>=0)&(sy>=0)&(sx<640)&(sy<340)
                error[valid]=np.max(np.abs(rgb[sy[valid],sx[valid]].astype(np.int16)-qr[valid]),axis=1)
                moving[valid]|=mask[sy[valid],sx[valid]]
                sx=px-entry['scroll'][0];sy=py-entry['scroll'][1]
                valid=(sx>=0)&(sy>=0)&(sx<640)&(sy<340)
                moving[valid]|=mask[sy[valid],sx[valid]]
            if bb:
                entry,rgb,mask=frame(bb);sx=px-entry['scroll'][0];sy=py-entry['scroll'][1]
                valid=(sx>=0)&(sy>=0)&(sx<640)&(sy<340)
                error[valid]=np.minimum(error[valid],np.max(np.abs(rgb[sy[valid],sx[valid]].astype(np.int16)-pr[valid]),axis=1))
                moving[valid]|=mask[sy[valid],sx[valid]]
                sx=px+dx-entry['scroll'][0];sy=py+dy-entry['scroll'][1]
                valid=(sx>=0)&(sy>=0)&(sx<640)&(sy<340)
                moving[valid]|=mask[sy[valid],sx[valid]]
            mismatch=error>0;bad+=int(mismatch.sum());temporal_bad+=int((mismatch&moving).sum())
            unverified+=int((error==256).sum())
            if mismatch.any():
                maximum=max(maximum,int(error[mismatch].max()))
                for j in np.flatnonzero(mismatch)[:max(0,40-len(samples))]:
                    samples.append({'world_pixel':[int(px[j]),int(py[j])],'owners':[aa,bb],
                                    'minimum_native_pair_channel_error':int(error[j]),'measured_temporal':bool(moving[j])})
                for j in np.flatnonzero(mismatch&~moving)[:max(0,40-len(static_samples))]:
                    static_samples.append({'world_pixel':[int(px[j]),int(py[j])],'owners':[aa,bb],
                                           'minimum_native_pair_channel_error':int(error[j])})
    for tx,ty in sorted(keys if scan_tiles is None else keys&set(scan_tiles),key=lambda k:(k[1],k[0])):
        rgb,owner=tile((tx,ty));h,w=owner.shape
        x=left+tx*1024+np.arange(w)[None,:];y=top+ty*1024+np.arange(h)[:,None]
        edges(rgb[:,:-1],rgb[:,1:],owner[:,:-1],owner[:,1:],x[:,:-1],y,1,0)
        edges(rgb[:-1],rgb[1:],owner[:-1],owner[1:],x,y[:-1],0,1)
        neighbor=tile((tx+1,ty))
        if neighbor is not None:
            nr,no=neighbor;hh=min(h,no.shape[0]);edges(rgb[:hh,-1:],nr[:hh,:1],owner[:hh,-1:],no[:hh,:1],x[:,-1:],y[:hh],1,0)
        neighbor=tile((tx,ty+1))
        if neighbor is not None:
            nr,no=neighbor;ww=min(w,no.shape[1]);edges(rgb[-1:,:ww],nr[:1,:ww],owner[-1:,:ww],no[:1,:ww],x[:,:ww],y[-1:],0,1)
    return {'checked_foreground_ownership_edges':examined,'edges_not_reproduced_by_either_native_source':bad,
            'measured_animation_edges':temporal_bad,'unmeasured_edges_requiring_review':bad-temporal_bad,
            'edges_outside_both_source_viewports':unverified,'maximum_minimum_channel_error':maximum,
            'exact_native_neighbor_pair_fraction':1-bad/max(1,examined),'samples':samples,'static_samples':static_samples}
