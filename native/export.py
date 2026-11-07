"""Capture the original renderer in overlapping native-pixel viewports."""
import argparse
import fcntl
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image, ImageFilter

from atlas import dump, write_full_png
from .game import NativeGame,RUNTIME
from .plan import CORE_W, CORE_H, camera_for_core, create_plan


def overlap(a, b, ac, bc):
    ax, ay = ac[0] * CORE_W - 64, ac[1] * CORE_H - 42
    bx, by = bc[0] * CORE_W - 64, bc[1] * CORE_H - 42
    left, top, right, bottom = max(ax,bx),max(ay,by),min(ax+640,bx+640),min(ay+340,by+340)
    if right <= left or bottom <= top:return None
    aa, am = a;bb, bm = b
    aa=aa[top-ay:bottom-ay,left-ax:right-ax];bb=bb[top-by:bottom-by,left-bx:right-bx]
    mask=am[top-ay:bottom-ay,left-ax:right-ax]|bm[top-by:bottom-by,left-bx:right-bx]
    delta=np.abs(aa.astype(np.int16)-bb.astype(np.int16));peak=delta.max(axis=2)
    mismatch=(peak>0)&~mask
    foreground=(np.any(aa,axis=2)|np.any(bb,axis=2))&~mask
    return {'pixels':int(peak.size),'temporal_pixels':int(mask.sum()),
            'static_pixels':int((~mask).sum()),'static_mismatches':int(mismatch.sum()),
            'static_mismatch_fraction':float(mismatch.sum()/max(1,(~mask).sum())),
            'foreground_static_pixels':int(foreground.sum()),
            'foreground_static_mismatches':int((mismatch&foreground).sum()),
            'mean_absolute_channel_error':float(delta.mean()),
            'maximum_static_channel_error':int(peak[~mask].max())if(~mask).any()else 0}


def capture_core(game, capture, coord, settle, temporal_samples=3, temporal_interval=1/24,camera=None):
    if not 2<=temporal_samples<=256 or not 0<temporal_interval<=1:raise ValueError('Invalid temporal sampling')
    cx,cy=coord;x,y,z=camera if camera is not None else camera_for_core(cx,cy)
    state=game.view(game.export_level,x,y,z)
    expected=[cx*CORE_W-64,cy*CORE_H-42]if camera is None else None
    # The original editor's incremental scroll cache can retain a few stale
    # terrain pixels even after the new frame is presented. Its own Ctrl-R
    # redraw resolves this (verified with A -> B -> A reference captures).
    # CmdMono(0) leaves normal colour enabled and calls the original
    # TMapPane::RedrawAll directly. Keyboard Ctrl-R can be consumed by the
    # focused editor pane, so it is not a reliable capture barrier.
    game.command('mono 0')
    game.command('@wait')
    state=game.info()
    if hasattr(game,'prepare_capture'):state=game.prepare_capture()
    fade_deadline=time.monotonic()+10
    while state.get('ambient_fade_frames',0):
        if time.monotonic()>fade_deadline:raise RuntimeError('Original area lighting did not finish its transition')
        game.command('@wait');state=game.info()
    if (expected is not None and state['scroll']!=expected)or state['camera']!=[x,y,z]:
        # On first entering an editor level this executable can restore its
        # saved editor camera after the level number has already changed.
        game.view(game.export_level,x,y,z);game.command('mono 0');game.command('@wait');state=game.info()
    if (expected is not None and state['scroll']!=expected)or state['camera']!=[x,y,z]:raise RuntimeError(f'Native scroll differs from requested crop after renderer completion: {state}, expected {expected}')
    time.sleep(settle)
    first=capture.frame().crop((0,0,640,340));array=np.array(first);mask=np.zeros((340,640),bool)
    if getattr(capture,'window_barrier',None):state['capture_window_barrier']=capture.window_barrier
    if getattr(capture,'backing_policy',None):state['capture_backing_policy']=capture.backing_policy
    for _ in range(temporal_samples-1):
        time.sleep(temporal_interval)
        mask|=np.any(np.array(capture.frame().crop((0,0,640,340)))!=array,axis=2)
    end=game.info()
    if end['screen_frame']<=state['screen_frame']:
        raise RuntimeError('Original renderer stopped advancing during capture')
    if end['camera']!=state['camera']or end['scroll']!=state['scroll']:
        raise RuntimeError('Original camera changed during capture')
    profile=getattr(game,'capture_lighting',None)
    if profile and(end.get('ambient')!=profile['expected_native_ambient']or end.get('ambient_rgb')!=profile['ambient_rgb']or end.get('ambient_fade_frames',0)):
        raise RuntimeError('Original authored ambient changed during capture')
    if state.get('provider')=='original_retail_1.22L'and end.get('time_of_day_minutes')!=state['time_of_day_minutes']:
        raise RuntimeError('Original scene clock changed during capture')
    state['capture_end_screen_frame']=end['screen_frame']
    state['requested_camera']=[x,y,z]
    state['capture_end_camera']=end['camera'];state['capture_end_scroll']=end['scroll']
    if 'ambient'in end:state.update(capture_end_ambient=end['ambient'],capture_end_ambient_rgb=end['ambient_rgb'])
    # Explicit temporal mask, with a measured-motion margin. Static differences
    # outside it stay visible in seam reports; no pixels are blended or repaired.
    dynamic=np.asarray(Image.fromarray(mask.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(17)))>0
    return first,array,dynamic,state


def assemble(root,plan):
    tile_size=1024;left,top,right,bottom=plan['bounds'];w,h=plan['width'],plan['height']
    tiles=root/'tiles';tiles.mkdir(exist_ok=True)
    buckets={}
    for cx,cy in plan['cores']:
        px,py=cx*CORE_W-left,cy*CORE_H-top
        buckets.setdefault((px//tile_size,py//tile_size),[]).append((cx,cy,px%tile_size,py%tile_size))
    scale=min(1,4096/max(w,h));preview=Image.new('RGB',(round(w*scale),round(h*scale)))
    for(tx,ty),cores in sorted(buckets.items()):
        image=Image.new('RGB',(min(tile_size,w-tx*tile_size),min(tile_size,h-ty*tile_size)))
        for cx,cy,x,y in cores:
            with Image.open(root/'captures'/f'{cx}_{cy}.png')as raw:image.paste(raw.crop((64,42,576,298)),(x,y))
        image.save(tiles/f'{tx}_{ty}.png',compress_level=4)
        px,py=round(tx*tile_size*scale),round(ty*tile_size*scale)
        xx,yy=round((tx*tile_size+image.width)*scale),round((ty*tile_size+image.height)*scale)
        preview.paste(image.resize((xx-px,yy-py),Image.Resampling.LANCZOS),(px,py))
    preview.save(root/'overview.jpg',quality=94,subsampling=0)
    return sorted(buckets)


def run(plan,out,settle=.15,limit=None,full=True,fast=True):
    root=out/f'level-{plan["level"]}';rawdir=root/'captures';rawdir.mkdir(parents=True,exist_ok=True)
    maskdir=root/'temporal';maskdir.mkdir(exist_ok=True)
    dump(root/'plan.json',plan)
    game=NativeGame();game.export_level=plan['level']
    state=game.command('@presentation')
    if state.get('shadow_blend_profile')!='rgb565_black_alpha_to_argb1555_v1':
        raise RuntimeError('Native shadow format correction was not verified')
    game.command('@grid')
    game.command('@time 487')
    game.command('@fast'if fast else'@normal')
    if not game.info()['helper_markers_hidden']:
        game.command('@helpers-off');game.command('@redraw')
    cache=OrderedDict();records=[];seams=[];start=time.monotonic();done=0
    history=root/'source-refresh.json'
    retired={r['capture']:r['before']for r in json.loads(history.read_text())['captures']if r['before']!=r['after']}if history.exists()else{}
    with game.backing_capture()as capture:
        for cx,cy in plan['cores']:
            coord=(cx,cy);path=rawdir/f'{cx}_{cy}.png';maskpath=maskdir/f'{cx}_{cy}.png';meta=root/'captures'/f'{cx}_{cy}.json'
            if path.exists()and maskpath.exists()and meta.exists():
                with Image.open(path)as im:array=np.array(im.convert('RGB'))
                with Image.open(maskpath)as im:dynamic=np.array(im)>0
                state=json.loads(meta.read_text())
                if state.get('source_png_sha256')==retired.get(f'{cx}_{cy}'):
                    raise RuntimeError(f'Retired source capture must not be reused: {meta}')
                if state.get('capture_recipe')!='console_redraw_bg_barrier_v3':
                    raise RuntimeError(f'Cannot resume a capture made with an older redraw recipe: {meta}')
            else:
                if shutil.disk_usage(out).free<3*1024**3:raise RuntimeError('Less than 3 GiB disk space remains; export safely stopped')
                first,array,dynamic,state=capture_core(game,capture,coord,settle)
                state.update(core=[cx,cy],captured_at=time.time(),crop=[64,42,576,298],
                             capture_recipe='console_redraw_bg_barrier_v3',
                             provider='original_game',temporal_samples=3,temporal_margin_pixels=8)
                first.save(path.with_suffix('.tmp'),format='PNG',compress_level=3)
                path.with_suffix('.tmp').replace(path)
                Image.fromarray(dynamic.astype(np.uint8)*255).save(maskpath)
                state['source_png_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();dump(meta,state)
            for neighbor in ((cx-1,cy),(cx+1,cy),(cx,cy-1)):
                if neighbor in cache:
                    result=overlap((array,dynamic),cache[neighbor],coord,neighbor)
                    if result:seams.append(dict(core=list(coord),neighbor=list(neighbor),**result))
            cache[coord]=(array,dynamic)
            while len(cache)>260:cache.popitem(last=False)
            records.append(state);done+=1
            if done%25==0 or done==1:
                elapsed=time.monotonic()-start
                dump(root/'progress.json',{'captured':done,'planned':plan['core_count'],'seconds':elapsed,
                    'last_core':[cx,cy],'unresolved_seams':sum(s['static_mismatch_fraction']>.001 for s in seams)})
                print(f'Native level {plan["level"]}: {done}/{plan["core_count"]}, {elapsed:.1f}s',flush=True)
            if limit and done>=limit:
                dump(root/'seams.json',seams);return
    dump(root/'seams.json',seams)
    tiles=assemble(root,plan)
    manifest={k:v for k,v in plan.items()if k!='cores'}
    manifest.update(provider='original_game',tile_size=1024,tile_count=len(tiles),tiles=[list(t)for t in tiles],
        pixel_scale='one original-game output pixel per exported pixel; no resampling',
        lighting='original game real-time light grid; GammaLevel 3',dynamic_objects='original renderer, captured animation frames and characters',
        statistics={'source_objects':plan['retained_source_objects'],'captures':len(records)},
        temporal_scope='stitched captures at recorded times; live animations are separate',
        unresolved_seams=sum(s['static_mismatch_fraction']>.001 for s in seams))
    dump(root/'manifest.json',manifest)
    if full:
        write_full_png(root,manifest,1024)
        print(f'Native full-resolution PNG: {root/"full-resolution.png"}',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--level',type=int,default=0)
    p.add_argument('--out',type=Path,default=Path('native-output'));p.add_argument('--plan',type=Path)
    p.add_argument('--limit',type=int);p.add_argument('--settle',type=float,default=.15)
    p.add_argument('--no-full',action='store_true');p.add_argument('--normal-timing',action='store_true')
    p.add_argument('--baseline',type=Path,default=Path('output-corrected')if Path('output-corrected/level-0/manifest.json').exists()else Path('output'))
    p.add_argument('--probe',nargs=4,type=int,metavar=('X0','Y0','X1','Y1'))
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    plan=json.loads(a.plan.read_text())if a.plan else create_plan(a.baseline,'runtime/game',a.level)
    if a.probe:
        x0,y0,x1,y1=a.probe;plan['cores']=[[x,y]for y in range(y0,y1)for x in range(x0,x1)]
        plan.update(bounds=[x0*512,y0*256,x1*512,y1*256],width=(x1-x0)*512,height=(y1-y0)*256,core_count=len(plan['cores']))
    with (RUNTIME/'export.lock').open('a')as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another original-game export owns the camera')
        try:
            run(plan,a.out,a.settle,a.limit,full=not a.no_full,fast=not a.normal_timing)
        finally:
            try:NativeGame().command('@normal')
            except RuntimeError:pass

if __name__=='__main__':main()
