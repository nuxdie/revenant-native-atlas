"""Capture a registered native viewport spanning a difficult ownership join."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
from atlas import dump
from .audit import audit
from .edges import verify_edges
from .export import capture_core
from .finalize import finalize
from .game import NativeGame,RUNTIME


def bridge(root,camera=None,reference=None,point=None,partial=False):
    meta=json.loads((root/'manifest.json').read_text());report=verify_edges(root,meta)
    points=[s['world_pixel']for s in report['static_samples']]
    if not points:raise ValueError('No static join needs a bridge')
    if point is not None:
        points=[p for p in points if abs(p[0]-point[0])<=128 and abs(p[1]-point[1])<=96]
        if not points:raise ValueError('Selected bridge has no reported static join')
    x0,y0=np.min(points,axis=0);x1,y1=np.max(points,axis=0)
    centre_x=int(round((x0+x1)/4)*2);centre_y=int(round((y0+y1)/2))
    if x1-x0>300 or y1-y0>200:raise ValueError('Review clusters separately before bridging')
    coord=[(centre_x-256)/512,(centre_y-128)/256]
    retail=meta.get('provider')=='original_retail_1.22L'
    if retail:
        from .retail import RetailGame
        game=RetailGame();game.command('@presentation');game.command('@helpers-off')
        game.command(f'setcurmodule "{meta["module"]}"');game.command('@wait')
        commands=['@grid',f'@time {meta["time_of_day_minutes"]}']
    else:
        game=NativeGame();commands=['@presentation','@grid','@time 487','@normal']
    game.export_level=meta['level']
    for command in commands:game.command(command)
    with game.backing_capture()as capture:first,array,dynamic,state=capture_core(game,capture,coord,.15,32,.1,camera=camera)
    name=f'bridge-{centre_x}-{centre_y}'+(f'-z{camera[2]}'if camera else'');path=root/'captures'/f'{name}.png'
    if path.exists():
        name+=f'-{time.time_ns()}';path=root/'captures'/f'{name}.png'
    first.save(path,compress_level=3)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    state.update(core=coord,captured_at=time.time(),capture_recipe='retail_redraw_bg_barrier_v2'if retail else'console_redraw_bg_barrier_v3',
                 source_registration='native_camera_z_bridge_v1'if camera else'native_camera_bridge_v1',provider='original_retail_1.22L'if retail else'original_game',
                 temporal_samples=32,temporal_sample_interval_seconds=.1,temporal_margin_pixels=8,
                 source_png_sha256=digest,recapture_reason='one native viewport spanning a persistent coarse-grid ownership join')
    if camera:state['bridge_reference']=reference
    if retail:state.update(module=meta['module'],variant=meta['variant'])
    dump(path.with_suffix('.json'),state);Image.fromarray(dynamic.astype('uint8')*255).save(root/'temporal'/path.name)
    sources=json.loads((root/'ownership-sources.json').read_text());ident=max(s['id']for s in sources)+1
    if ident>=65535:raise ValueError('Ownership IDs exhausted')
    sources.append(dict(id=ident,capture=name,scroll=state['scroll'],sha256=digest))
    dump(root/'ownership-sources.json',sources)
    left,top,right,bottom=meta['bounds'];old={};tiles={}
    for tx,ty in meta['tiles']:
        wx,wy=left+tx*1024,top+ty*1024
        if wx>=centre_x+300 or wx+1024<=centre_x-300 or wy>=centre_y+160 or wy+1024<=centre_y-160:continue
        with Image.open(root/'tiles'/f'{tx}_{ty}.png')as im:rgb=np.array(im.convert('RGB'))
        with Image.open(root/'ownership'/f'{tx}_{ty}.png')as im:owners=np.array(im)
        old[tx,ty]=(rgb,owners)
    local=set(old)|{(tx-1,ty)for tx,ty in old}|{(tx,ty-1)for tx,ty in old}
    def save(values):
        for(tx,ty),(rgb,owners)in values.items():
            Image.fromarray(rgb).save(root/'tiles'/f'{tx}_{ty}.png',compress_level=4)
            Image.fromarray(owners).save(root/'ownership'/f'{tx}_{ty}.png')
    chosen=None;best=None
    before=verify_edges(root,meta,scan_tiles=local)['unmeasured_edges_requiring_review']
    for radius_x,radius_y in [(64,64),(96,96),(128,128),(192,144),(256,150),(300,160)]:
        count=0;tiles={k:(rgb.copy(),owners.copy())for k,(rgb,owners)in old.items()}
        for(tx,ty),(rgb,owners)in tiles.items():
            wx,wy=left+tx*1024,top+ty*1024
            l=max(wx,centre_x-radius_x,state['scroll'][0]);t=max(wy,centre_y-radius_y,state['scroll'][1])
            r=min(wx+rgb.shape[1],centre_x+radius_x,state['scroll'][0]+640);b=min(wy+rgb.shape[0],centre_y+radius_y,state['scroll'][1]+340)
            if r<=l or b<=t:continue
            dest=rgb[t-wy:b-wy,l-wx:r-wx];owner=owners[t-wy:b-wy,l-wx:r-wx]
            source=array[t-state['scroll'][1]:b-state['scroll'][1],l-state['scroll'][0]:r-state['scroll'][0]]
            keep=owner>0;dest[keep]=source[keep];owner[keep]=ident;count+=int(keep.sum())
        save(tiles);after=verify_edges(root,meta,scan_tiles=local)
        print(f'Native bridge {radius_x} × {radius_y} radii: {after["unmeasured_edges_requiring_review"]} static edges',flush=True)
        if after['unmeasured_edges_requiring_review']==0:
            chosen=dict(capture=name,source_id=ident,centre=[centre_x,centre_y],radii=[radius_x,radius_y],native_pixels=count);break
        if partial and after['unmeasured_edges_requiring_review']<before and(best is None or after['unmeasured_edges_requiring_review']<best[0]):
            best=(after['unmeasured_edges_requiring_review'],{k:(rgb.copy(),owners.copy())for k,(rgb,owners)in tiles.items()},dict(capture=name,source_id=ident,centre=[centre_x,centre_y],radii=[radius_x,radius_y],native_pixels=count))
        save(old)
    if chosen is None and best is not None:
        _,tiles,chosen=best;save(tiles)
    if chosen is None:
        dump(root/'ownership-sources.json',sources[:-1]);raise RuntimeError('Bridge boundaries still require review')
    meta.setdefault('native_viewport_bridges',[]).append(chosen);meta['statistics']['captures']=len(sources);dump(root/'manifest.json',meta)
    scale=min(1,4096/max(meta['width'],meta['height']));preview=Image.new('RGB',(round(meta['width']*scale),round(meta['height']*scale)))
    for tx,ty in meta['tiles']:
        with Image.open(root/'tiles'/f'{tx}_{ty}.png')as im:
            x,y=round(tx*1024*scale),round(ty*1024*scale);xx,yy=round((tx*1024+im.width)*scale),round((ty*1024+im.height)*scale)
            preview.paste(im.resize((xx-x,yy-y),Image.Resampling.LANCZOS),(x,y))
    preview.save(root/'overview.jpg',quality=94,subsampling=0)
    validation=audit(root,full=False)
    if validation['acceptance']=='review_required':
        if not partial:raise RuntimeError('Bridge failed the complete native audit')
    else:finalize(root)
    return chosen


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--camera',nargs=3,type=int);parser.add_argument('--reference')
    parser.add_argument('--point',nargs=2,type=int);parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    if args.camera and not args.reference:parser.error('A nonzero-Z bridge requires a native registration reference')
    runtime=RUNTIME
    if json.loads((args.directory/'manifest.json').read_text()).get('provider')=='original_retail_1.22L':
        from .retail import RUNTIME as runtime
    with (runtime/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);print(json.dumps(bridge(args.directory,args.camera,args.reference,args.point,args.partial),indent=2))
