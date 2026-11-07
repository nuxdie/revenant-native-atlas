"""Recover retail edge scenery using registered cameras inside world XY bounds."""
import argparse
import fcntl
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image
from atlas import dump
from .audit import audit,registered_overlap
from .bigtiff import build as bigtiff
from .edges import verify_edges
from .export import capture_core
from .finalize import finalize
from .plan import camera_for_core
from .quilt import quilt
from .recut import recut
from .repair_edges import repair
from .retail import RetailGame,RUNTIME


def pin_reference(root,name):
    """Keep an immutable native anchor when its output core is later recaptured."""
    path=root/'captures'/f'{name}.png';state=json.loads(path.with_suffix('.json').read_text())
    cx,cy=map(int,name.split('_'))
    mask=root/'temporal'/path.name
    if state['camera']!=list(camera_for_core(cx,cy)):
        if state.get('original_grid_reference_key'):return state['original_grid_reference_key']
        # Review can move between isolated instances; its native archive must
        # remain usable without depending on the reviewing instance's name.
        bases=[RUNTIME/'raised-core-history'/root.name/name]
        bases.extend(sorted(RUNTIME.parent.glob(f'retail*/raised-core-history/{root.name}/{name}')))
        for base in dict.fromkeys(bases):
            candidate=base/'captures'/f'{name}.png'
            if not candidate.with_suffix('.json').exists():continue
            original=json.loads(candidate.with_suffix('.json').read_text())
            if (original['camera']==list(camera_for_core(cx,cy))
                    and original.get('executable_sha256')==state.get('executable_sha256')
                    and original.get('time_of_day_minutes')==state.get('time_of_day_minutes')
                    and original.get('level')==state.get('level')):
                path=candidate;mask=base/'temporal'/path.name;state=original;break
        else:raise ValueError(f'Original native reference unavailable: {root.name}/{name}')
    if state['camera']!=list(camera_for_core(cx,cy)):raise ValueError('Original native reference unavailable')
    key=name+'-'+hashlib.sha256(path.read_bytes()).hexdigest()[:16]+'-'+hashlib.sha256(mask.read_bytes()).hexdigest()[:12]
    target=root/'registration-references';target.mkdir(exist_ok=True)
    for source,suffix in [(path,'.png'),(path.with_suffix('.json'),'.json'),(mask,'-motion.png')]:
        destination=target/(key+suffix)
        if not destination.exists():shutil.copy2(source,destination)
    return key


def matching_reference(root,by_name,cx,cy,rgb,motion,state):
    for dx,dy in [(-1,0),(1,0),(0,1),(0,-1),(-1,1),(1,1),(-1,-1),(1,-1)]:
        candidate=f'{cx+dx}_{cy+dy}'
        if candidate not in by_name:continue
        try:key=pin_current_reference(root,candidate)
        except ValueError:continue
        p=root/'registration-references'/f'{key}.png'
        rs=json.loads(p.with_suffix('.json').read_text())
        with Image.open(p)as im:reference_rgb=np.array(im.convert('RGB'))
        with Image.open(p.parent/f'{key}-motion.png')as im:reference_mask=np.array(im)>0
        try:count=registered_overlap(rgb,motion,state['scroll'],reference_rgb,reference_mask,rs['scroll'],recover_black=True)
        except ValueError:continue
        return candidate,count
    return None,0


def pin_current_reference(root,name):
    """Snapshot an ordinary view or an already anchored in-world native view."""
    from .audit import load_native_reference
    path=root/'captures'/f'{name}.png';mask=root/'temporal'/path.name
    state=json.loads(path.with_suffix('.json').read_text())
    if not all(0<=v<=32768 for v in state['camera'][:2]):
        return pin_reference(root,name)
    key=name+'-'+hashlib.sha256(path.read_bytes()).hexdigest()[:16]+'-'+hashlib.sha256(mask.read_bytes()).hexdigest()[:12]
    target=root/'registration-references';target.mkdir(exist_ok=True)
    for source,suffix in [(path,'.png'),(path.with_suffix('.json'),'.json'),(mask,'-motion.png')]:
        destination=target/(key+suffix)
        if not destination.exists():shutil.copy2(source,destination)
    load_native_reference(root,key,name,json.loads((root/'plan.json').read_text()))
    return key


def capture_raised(game,capture,cx,cy,height):
    original=camera_for_core(cx,cy);shift=math.ceil(height*867/1000)
    camera=[original[0]+shift,original[1]+shift,height]
    game.view(game.export_level,*camera);game.command('@wait');s=game.info()
    dy=cy*256-42-s['scroll'][1];camera[0]+=dy;camera[1]+=dy
    result=capture_core(game,capture,[cx,cy],.08,32,.1,camera=camera)
    if result[3]['scroll']!=[cx*512-64,cy*256-42]:raise ValueError('Raised native scroll registration failed')
    return (*result,camera)


def pin_existing_references(root):
    sources=json.loads((root/'ownership-sources.json').read_text())
    for source in sources:
        p=root/'captures'/f'{source["capture"]}.json';state=json.loads(p.read_text())
        if state.get('source_registration')=='native_raised_core_v1':
            if not state.get('registration_reference_key'):state['registration_reference_key']=pin_reference(root,state['registration_reference'])
            if not state.get('original_grid_reference_key'):state['original_grid_reference_key']=pin_reference(root,source['capture'])
            dump(p,state)


def raise_cores(root):
    meta=json.loads((root/'manifest.json').read_text())
    if meta.get('provider')!='original_retail_1.22L':raise ValueError('Retail maps only')
    sources=json.loads((root/'ownership-sources.json').read_text());by_id={s['id']:s for s in sources};by_name={s['capture']:s for s in sources}
    pin_existing_references(root)
    report=verify_edges(root,meta);candidates=[]
    for ident in report['static_owner_ids']:
        name=by_id[ident]['capture']
        if name.startswith('bridge-'):continue
        state=json.loads((root/'captures'/f'{name}.json').read_text())
        if state.get('source_registration')=='native_raised_core_v1':continue
        x,y,z=state['camera']
        if min(x,y)<=512 and z==0:candidates.append(name)
    print(f'{root}: {len(candidates)} out-of-world core cameras need registered replacements',flush=True)
    if not candidates:
        if not report['unmeasured_edges_requiring_review']and not report['edges_outside_both_source_viewports']:
            checked=audit(root,full=False)
            if checked['acceptance']!='review_required':
                finalize(root);bigtiff(root);print('NATIVE CAMERA REGISTRATION VERIFIED',root,flush=True);return True
        return False
    game=RetailGame();game.export_level=meta['level'];game.capture_lighting=meta.get('lighting_profile')
    game.command('@presentation');game.command('@helpers-off');game.command('@grid')
    game.mount(meta['module']);game.command(f'@time {meta["time_of_day_minutes"]}')
    changed=[];unresolved=[]
    with game.backing_capture()as capture:
        for name in candidates:
            cx,cy=map(int,name.split('_'));original=list(camera_for_core(cx,cy));negative=max(-original[0],-original[1],0)
            reference=None
            heights=list(dict.fromkeys([192*math.ceil((negative*1000/867+1)/192),209*math.ceil((negative*1000/867+1)/209)]))
            for height in heights:
                first,rgb,motion,state,camera=capture_raised(game,capture,cx,cy,height)
                reference,count=matching_reference(root,by_name,cx,cy,rgb,motion,state)
                if reference is not None:break
            if reference is None:
                unresolved.append(name);print('No exact in-world reference yet:',name,flush=True);continue
            path=root/'captures'/f'{name}.png';archive=RUNTIME/'raised-core-history'/root.name/name
            for source in [path,path.with_suffix('.json'),root/'temporal'/path.name]:
                target=archive/('temporal'if source.parent.name=='temporal'else'captures')/source.name
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():shutil.copy2(source,target)
            state.update(core=[cx,cy],captured_at=time.time(),crop=[64,42,576,298],
                source_registration='native_raised_core_v1',registration_reference=reference,
                registration_reference_key=pin_current_reference(root,reference),
                original_grid_reference_key=pin_reference(root,name),
                registration_recovery='native_black_coverage_v1',
                registration_foreground_pixels=count,original_grid_camera=original,
                camera_policy='in-world XY, same observed native pixel scroll',
                capture_recipe='retail_redraw_bg_barrier_v2',temporal_samples=32,
                temporal_sample_interval_seconds=.1,temporal_margin_pixels=8,
                module=meta['module'],variant=meta['variant'])
            temporary=path.with_suffix('.png.tmp');first.save(temporary,format='PNG',compress_level=3);temporary.replace(path)
            state['source_png_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();dump(path.with_suffix('.json'),state)
            p=root/'temporal'/path.name;temporary=p.with_suffix('.png.tmp');Image.fromarray(motion.astype('uint8')*255).save(temporary,format='PNG');temporary.replace(p)
            changed.append(dict(capture=name,camera=camera,reference=reference,static_registration_pixels=count))
            print(json.dumps(changed[-1]),flush=True)
    dump(root/'raised-core-registration.json',dict(changed=changed,unresolved=unresolved))
    if not changed:return False
    quilt(root,full=False);report=audit(root,full=False)
    if report['acceptance']=='review_required':
        repair(root,iterations=2);recut(root,iterations=2);report=audit(root,full=False)
    if report['acceptance']!='review_required':
        finalize(root);bigtiff(root);print('RAISED CAMERAS VERIFIED',root,flush=True);return True
    print('Further review required',root,report['actual_stitched_edges'],flush=True)
    return False


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directories',nargs='+',type=Path);a=p.parse_args()
    with(RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for root in a.directories:raise_cores(root)
