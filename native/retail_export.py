"""Capture retail maps and lighting variants with recorded native pixel sources."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image

from atlas import dump
from .audit import audit
from .bigtiff import build as bigtiff
from .export import assemble,capture_core
from .finalize import finalize
from .quilt import quilt
from .plan import camera_for_core
from .retail import RetailGame,ROOT,RUNTIME,EXE_SHA256


def capture(plan,variant,out,samples=8,rebuild_held=False):
    from .sound_markers import PROFILE,intersects_viewport,speaker_positions
    if 'speaker_positions' not in plan:
        from .retail import DATA
        plan=dict(plan,speaker_positions=speaker_positions(DATA/'Modules'/f'{plan["module"]}.rvm',plan['level']))
    root=out/variant/f'level-{plan["level"]}'
    minute=plan.get('time_of_day_minutes',60 if variant=='night'else 720)
    if not isinstance(minute,int)or not 0<=minute<1440:raise ValueError('Invalid native capture clock')
    profile=plan.get('lighting_profiles',{}).get(variant)
    def ambient_matches(state):
        return not profile or(state.get('ambient')==profile['expected_native_ambient']and state.get('ambient_rgb')==profile['ambient_rgb']and not state.get('ambient_fade_frames',0))
    def module_matches(state):
        return plan['module']=='Ahkuilon'or state.get('native_module','').casefold()==plan['module'].casefold()
    prior_ambient_valid=not profile or all(
        (p:=root/'captures'/f'{x}_{y}.json').exists()and ambient_matches(json.loads(p.read_text()))for x,y in plan['cores'])
    prior_ambient_valid=prior_ambient_valid and all(
        (p:=root/'captures'/f'{x}_{y}.json').exists()and json.loads(p.read_text()).get('time_of_day_minutes')==minute for x,y in plan['cores'])
    prior_ambient_valid=prior_ambient_valid and(plan['module']=='Ahkuilon'or all(
        (p:=root/'captures'/f'{x}_{y}.json').exists()and module_matches(json.loads(p.read_text()))for x,y in plan['cores']))
    def speaker_matches(state):
        return not intersects_viewport(state['scroll'],plan['speaker_positions']) or state.get('sound_marker_profile')==PROFILE
    prior_ambient_valid=prior_ambient_valid and all(
        (p:=root/'captures'/f'{x}_{y}.json').exists()and speaker_matches(json.loads(p.read_text()))for x,y in plan['cores'])
    validation=root/'validation.json';tiff=root/'tiff-validation.json'
    if validation.exists()and tiff.exists()and prior_ambient_valid:
        checked=json.loads(validation.read_text());tiff_checked=json.loads(tiff.read_text())
        png=root/'full-resolution.png';tif=root/'full-resolution.tif'
        if (checked.get('acceptance','').startswith('native_pixels_verified')
                and checked.get('full_png_crc')=='verified'and png.exists()and tif.exists()
                and tiff_checked.get('source_png_sha256')==checked['full_png_sha256']
                and hashlib.sha256(png.read_bytes()).hexdigest()==checked['full_png_sha256']
                and hashlib.sha256(tif.read_bytes()).hexdigest()==tiff_checked['sha256']):
            print(f'ALREADY VERIFIED {root}',flush=True)
            return True
    if validation.exists()and not prior_ambient_valid:
        checked=json.loads(validation.read_text());checked.update(acceptance='review_required',capture_review='Recapture inconsistent lighting, mounted module or sound-marker visibility states')
        dump(validation,checked)
    if validation.exists()and not rebuild_held and prior_ambient_valid:
        checked=json.loads(validation.read_text())
        if checked.get('acceptance')=='review_required'and all(
                (root/'captures'/f'{x}_{y}.png').exists()
                and(root/'captures'/f'{x}_{y}.json').exists()
                and(root/'temporal'/f'{x}_{y}.png').exists()for x,y in plan['cores']):
            print(f'HELD FOR SEPARATE REVIEW {root}',flush=True)
            return False
    for name in ['captures','temporal']: (root/name).mkdir(parents=True,exist_ok=True)
    plan=dict(plan,variant=variant,time_of_day_minutes=minute,game_time=f'{minute//60:02d}:{minute%60:02d}')
    if profile:plan['lighting_profile']=profile
    dump(root/'plan.json',plan)
    game=RetailGame();game.export_level=plan['level'];game.capture_lighting=profile
    deadline=time.monotonic()+180
    while True:
        state=game.info()
        if state['editor'] and state['current_screen']==0x65caf0 and state['screen_frame']>0:break
        if time.monotonic()>deadline:raise RuntimeError('Retail editor did not finish initialization')
        time.sleep(.5)
    game.command('@presentation');game.command('@helpers-off');game.command('@grid')
    game.mount(plan['module'])
    game.view(plan['level'],*camera_for_core(*plan['cores'][0]))
    game.command(f'@time {minute}');game.command('mono 0');game.command('@wait')
    started=time.monotonic();done=0
    with game.backing_capture()as grab:
        for coord in plan['cores']:
            cx,cy=coord;path=root/'captures'/f'{cx}_{cy}.png'
            if path.exists()and path.with_suffix('.json').exists()and(root/'temporal'/path.name).exists():
                old=json.loads(path.with_suffix('.json').read_text())
                if old.get('executable_sha256')!=EXE_SHA256 or old.get('time_of_day_minutes')!=minute:
                    raise ValueError(f'Capture dataset/time differs: {path}')
                if hashlib.sha256(path.read_bytes()).hexdigest()!=old['source_png_sha256']:
                    raise ValueError(f'Capture hash differs: {path}')
                if ambient_matches(old)and module_matches(old)and speaker_matches(old):
                    try:
                        with Image.open(root/'temporal'/path.name)as mask:mask.load();valid=mask.size==(640,340)
                    except OSError:valid=False
                    if valid:done+=1;continue
                archive=RUNTIME/'ambient-history'/variant/root.name
                for source in [path,path.with_suffix('.json'),root/'temporal'/path.name]:
                    target=archive/('temporal'if source.parent.name=='temporal'else'captures')/source.name
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.exists():shutil.copy2(source,target)
            if shutil.disk_usage(out).free<1024**3:
                raise RuntimeError('Less than 1 GiB disk space remains; retail export safely stopped')
            first,array,motion,state=capture_core(game,grab,coord,.08,temporal_samples=samples)
            if (state['time_of_day_minutes']!=minute or state['visibility_profile']!='gameplay_2d_and_3d'
                    or state.get('sound_marker_profile')!=PROFILE):
                raise RuntimeError(f'Retail state changed: {state}')
            state.update(core=coord,captured_at=time.time(),crop=[64,42,576,298],
                capture_recipe='retail_redraw_bg_barrier_v2',variant=variant,module=plan['module'],
                temporal_samples=samples,temporal_sample_interval_seconds=1/24,temporal_margin_pixels=8)
            temporary=path.with_suffix('.png.tmp');first.save(temporary,format='PNG',compress_level=3);temporary.replace(path)
            state['source_png_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();dump(path.with_suffix('.json'),state)
            mask_path=root/'temporal'/path.name;mask_tmp=mask_path.with_suffix('.png.tmp')
            Image.fromarray(motion.astype(np.uint8)*255).save(mask_tmp,format='PNG');mask_tmp.replace(mask_path)
            done+=1
            if done%25==0 or done==1:
                progress=dict(level=plan['level'],variant=variant,captured=done,planned=len(plan['cores']),seconds=time.monotonic()-started)
                dump(root/'progress.json',progress);print(json.dumps(progress),flush=True)
    tiles=assemble(root,plan)
    manifest={k:v for k,v in plan.items()if k!='cores'}
    manifest.update(provider='original_retail_1.22L',renderer='Original GOG 1.22L executable, Wine/D7VK, GammaLevel 3',
        sound_marker_profile=PROFILE,
        tile_size=1024,tiles=tiles,tile_count=len(tiles),pixel_scale='native pixels, no resampling',
        statistics=dict(source_objects=plan['retained_source_objects'],captures=len(plan['cores'])),
        temporal_scope='Stitched native animation snapshots at a fixed day/night clock')
    dump(root/'manifest.json',manifest)
    quilt(root,full=False)
    report=audit(root,full=False)
    if report['acceptance']=='review_required':
        print(f'REVIEW {root}: {report.get("actual_stitched_edges",{})}',flush=True)
        return False
    finalize(root);bigtiff(root)
    print(f'COMPLETE {root}',flush=True)
    return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--levels');p.add_argument('--variant',choices=['day','night','fixed'])
    p.add_argument('--index',type=Path,default=ROOT/'runtime/retail-index')
    p.add_argument('--out',type=Path,default=ROOT/'retail-output')
    p.add_argument('--samples',type=int,default=8)
    p.add_argument('--rebuild-held',action='store_true',help='Reassemble held maps instead of retaining them for dedicated review')
    args=p.parse_args();selected=set(map(int,args.levels.split(',')))if args.levels else None
    dataset=json.loads((args.index/'dataset.json').read_text());dump(args.out/'dataset.json',dataset)
    with (RUNTIME/'export.lock').open('a')as lock:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX)
        for level in dataset['levels']:
            if selected is not None and level['level']not in selected:continue
            plan=json.loads((args.index/'plans'/f'level-{level["level"]}.json').read_text())
            for variant in plan['variants']:
                if args.variant and args.variant!=variant:continue
                capture(plan,variant,args.out,args.samples,args.rebuild_held)


if __name__=='__main__':main()
