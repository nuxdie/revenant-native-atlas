"""Audit original-game capture provenance and unmodified tile pixels."""
import argparse
from collections import OrderedDict,Counter
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from atlas import dump
from audit import verify_png, verify_samples
from .export import overlap
from .plan import CORE_W, CORE_H,camera_for_core
from .edges import verify_edges


def registered_overlap(rgb,mask,scroll,reference_rgb,reference_mask,reference_scroll,minimum=1000,recover_black=False):
    """Anchor native camera alignment; optional recovery adds only over black culling gaps."""
    sx,sy=scroll;rx,ry=reference_scroll;l,t=max(sx,rx),max(sy,ry);r,b=min(sx+640,rx+640),min(sy+340,ry+340)
    if r<=l or b<=t:raise ValueError('Registered camera has no native reference overlap')
    a=rgb[t-sy:b-sy,l-sx:r-sx];z=reference_rgb[t-ry:b-ry,l-rx:r-rx]
    static=~(mask[t-sy:b-sy,l-sx:r-sx]|reference_mask[t-ry:b-ry,l-rx:r-rx])
    same=np.all(a==z,axis=2)
    foreground=static&same&np.any(z,axis=2)
    recovered=~np.any(z,axis=2)&np.any(a,axis=2)if recover_black else np.zeros(static.shape,bool)
    if foreground.sum()<minimum or np.any(static&~same&~recovered):
        raise ValueError('Registered camera does not match its native reference outside measured motion')
    return int(foreground.sum())


def load_native_reference(root,key,name,plan,seen=()):
    """Verify every immutable overlap back to an ordinary in-world view."""
    if not key or Path(key).name!=key or key in seen or len(seen)>=64:
        raise ValueError('Invalid or cyclic native reference chain')
    cx,cy=map(int,name.split('_'))
    if [cx,cy]not in plan['cores']:raise ValueError('Native reference is not planned')
    p=root/'registration-references'/f'{key}.png';mp=p.parent/f'{key}-motion.png'
    state=json.loads(p.with_suffix('.json').read_text())
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    if sha!=state['source_png_sha256']or key!=name+'-'+sha[:16]+'-'+hashlib.sha256(mp.read_bytes()).hexdigest()[:12]:
        raise ValueError('Native reference snapshot differs')
    if (state.get('provider')!='original_retail_1.22L'
            or state.get('executable_sha256')!=plan['executable_sha256']
            or state['level']!=plan['level']or state['time_of_day_minutes']!=plan['time_of_day_minutes']):
        raise ValueError('Native reference dataset or clock differs')
    if (state.get('visibility_profile')!='gameplay_2d_and_3d'
            or state.get('shadow_blend_profile')!='retail_original_raster'
            or state.get('lighting_mode')!='real_time_grid'):
        raise ValueError('Native reference capture profile differs')
    profile=plan.get('lighting_profile')
    if profile and(state['ambient']!=profile['expected_native_ambient']or state['ambient_rgb']!=profile['ambient_rgb']or state['ambient_fade_frames']):
        raise ValueError('Native reference ambient differs')
    if (state['capture_end_screen_frame']<=state['screen_frame']
            or verify_png(p)!=(640,340)or verify_png(mp)!=(640,340)):
        raise ValueError('Native reference frame is incomplete')
    if state['scroll']!=[cx*512-64,cy*256-42]:raise ValueError('Native reference scroll differs')
    if not all(0<=v<=32768 for v in state['camera'][:2]):raise ValueError('Native reference camera is outside world XY')
    with Image.open(p)as im:rgb=np.array(im.convert('RGB'))
    with Image.open(mp)as im:mask=np.array(im)>0
    if state['camera']!=list(camera_for_core(cx,cy)):
        if (state.get('source_registration')!='native_raised_core_v1'
                or state['camera']!=state['requested_camera']
                or state['camera']!=state['capture_end_camera']or state['scroll']!=state['capture_end_scroll']):
            raise ValueError('Native reference raised camera lacks registration')
        reference_rgb,reference_mask,reference=load_native_reference(root,
            state.get('registration_reference_key'),state['registration_reference'],plan,seen+(key,))
        registered_overlap(rgb,mask,state['scroll'],reference_rgb,reference_mask,reference['scroll'],
            recover_black=state.get('registration_recovery')=='native_black_coverage_v1')
    return rgb,mask,state


def verify_ownership(root,meta):
    index={r['id']:r for r in json.loads((root/'ownership-sources.json').read_text())}
    cache=OrderedDict();checked=0;nonblack=0
    left,top=meta['bounds'][:2]
    for tx,ty in meta['tiles']:
        path=root/'tiles'/f'{tx}_{ty}.png'
        with Image.open(path) as im:rgb=np.array(im.convert('RGB'))
        ownerpath=root/'ownership'/path.name
        verify_png(path);verify_png(ownerpath)
        with Image.open(ownerpath) as im:owners=np.array(im)
        if owners.shape!=rgb.shape[:2]:raise ValueError(f'Ownership dimensions: {path}')
        if np.any(rgb[owners==0]):raise ValueError(f'Nonblack pixels have no original-game source: {path}')
        nonblack+=int(np.any(rgb,axis=2).sum())
        for ident in np.unique(owners):
            if ident==0:continue
            source=index[int(ident)]
            if ident not in cache:
                source_path=root/'captures'/f'{source["capture"]}.png'
                if hashlib.sha256(source_path.read_bytes()).hexdigest()!=source['sha256']:
                    raise ValueError(f'Ownership index has a stale source digest: {source_path}')
                with Image.open(source_path)as im:cache[ident]=np.array(im.convert('RGB'))
                while len(cache)>260:cache.popitem(last=False)
            yy,xx=np.where(owners==ident)
            sx=left+tx*1024+xx-source['scroll'][0]
            sy=top+ty*1024+yy-source['scroll'][1]
            if sx.min()<0 or sy.min()<0 or sx.max()>=640 or sy.max()>=340:
                raise ValueError(f'Ownership points outside source viewport: {path}')
            if not np.array_equal(rgb[yy,xx],cache[ident][sy,sx]):
                raise ValueError(f'Quilt changes original-game source pixels: {path}')
            checked+=len(xx)
    return checked,nonblack


def audit(root, full=True):
    plan = json.loads((root / 'plan.json').read_text())
    meta = json.loads((root / 'manifest.json').read_text()) if (root / 'manifest.json').exists() else None
    cache = OrderedDict()
    seams = []
    checked = 0
    absent = []
    hashes = []
    modes = set()
    visibility=Counter()
    shadow_blending=Counter()
    geyser_blending=Counter()
    sampling=Counter()
    history=root/'source-refresh.json'
    retired={r['capture']:r['before']for r in json.loads(history.read_text())['captures']if r['before']!=r['after']}if history.exists()else{}
    frontier = []
    background_frontier=[]
    planned = set(map(tuple, plan['cores']))
    background_crop=bool(plan.get('background_crop')and plan.get('background_effects'))
    if background_crop:
        l,t,r,b=plan['bounds'];rectangle={(x,y)for y in range(t//256,b//256)for x in range(l//512,r//512)}
        if planned!=rectangle:raise ValueError('Native background crop still has uncaptured interior views')
    for coord in plan['cores']:
        cx, cy = coord
        path = root / 'captures' / f'{cx}_{cy}.png'
        if not path.exists() or not path.with_suffix('.json').exists():
            absent.append(coord)
            continue
        state = json.loads(path.with_suffix('.json').read_text())
        if plan.get('dataset')=='GOG 1.22L':
            if (state.get('provider')!='original_retail_1.22L'
                    or state.get('executable_sha256')!=plan['executable_sha256']
                    or state.get('time_of_day_minutes')!=plan['time_of_day_minutes']):
                raise ValueError(f'Retail capture dataset or clock mismatch: {path}')
            if state.get('native_module')and state['native_module'].casefold()!=plan['module'].casefold():
                raise ValueError(f'Retail mounted module mismatch: {path}')
            if plan['module']!='Ahkuilon'and not state.get('native_module'):
                raise ValueError(f'Retail module mount was not observed: {path}')
            profile=plan.get('lighting_profile')
            if profile and(state['ambient']!=profile['expected_native_ambient']or state['ambient_rgb']!=profile['ambient_rgb']or state['ambient_fade_frames']):
                raise ValueError(f'Retail ambient differs from authored setter target: {path}')
        geyser_blending[state.get('geyser_blend_profile','prior capture outside geyser recapture region')]+=1
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest==retired.get(path.stem):raise ValueError(f'Retired native source was reused: {path}')
        if digest != state['source_png_sha256']:
            raise ValueError(f'Capture provenance mismatch: {path}')
        hashes.append(digest)
        sampling[f'{state.get("temporal_samples",3)} samples; {state.get("temporal_sample_interval_seconds",1/24):.6g} seconds apart']+=1
        if verify_png(path) != (640, 340):
            raise ValueError(f'Capture dimensions: {path}')
        if state['scroll'] != [cx*512-64, cy*256-42] or state['level'] != plan['level']:
            raise ValueError(f'Camera registration mismatch: {path}')
        modes.add(state.get('lighting_mode', 'unrecorded'))
        if (state.get('provider')=='original_retail_1.22L'
                and state.get('executable_sha256')=='28bec27387bf53a553da320dd4883d00ff5bcc5a5f3d2658cca8e8ed586372b5'
                and state.get('shadow_blend_profile')=='retail_original_raster'):
            shadow_blending['pinned_retail_raster_capture']+=1
        elif state.get('shadow_blend_profile')=='rgb565_black_alpha_to_argb1555_v1':
            shadow_blending['format_corrected_capture']+=1
        elif state.get('shadow_blend_validation'):
            shadow_blending['outside_conservative_shadow_bounds_verified']+=1
        else:shadow_blending['requires_shadow_review']+=1
        profile=state.get('visibility_profile')
        if profile=='gameplay_2d_and_3d':visibility[profile]+=1
        elif state.get('visibility_validation'):
            visibility['outside_conservative_marker_bounds_verified']+=1
        else:visibility['requires_visibility_review']+=1
        with Image.open(path) as im:
            array = np.array(im.convert('RGB'))
        with Image.open(root / 'temporal' / path.name) as im:
            dynamic = np.array(im) > 0
        if state.get('provider')=='original_retail_1.22L'and state['camera']!=list(camera_for_core(cx,cy)):
            if state.get('source_registration')!='native_raised_core_v1':raise ValueError('Nonstandard retail core camera lacks registration')
            if state['camera']!=state['requested_camera']or state['camera']!=state['capture_end_camera']or state['scroll']!=state['capture_end_scroll']:raise ValueError('Raised core camera changed')
            reference=state['registration_reference'];rx,ry=map(int,reference.split('_'))
            if(rx,ry)not in planned:raise ValueError('Raised camera reference is not planned')
            key=state.get('registration_reference_key')
            if key:
                if Path(key).name!=key:raise ValueError('Invalid native reference key')
                rp=root/'registration-references'/f'{key}.png';mp=root/'registration-references'/f'{key}-motion.png'
            else:rp=root/'captures'/f'{reference}.png';mp=root/'temporal'/rp.name
            rs=json.loads(rp.with_suffix('.json').read_text())
            reference_sha=hashlib.sha256(rp.read_bytes()).hexdigest()
            if reference_sha!=rs['source_png_sha256']:raise ValueError('Native reference digest differs')
            if key and key!=reference+'-'+reference_sha[:16]+'-'+hashlib.sha256(mp.read_bytes()).hexdigest()[:12]:raise ValueError('Native reference snapshot differs')
            if (rs.get('provider')!='original_retail_1.22L'or rs.get('executable_sha256')!=plan['executable_sha256']or rs['level']!=plan['level']or rs['time_of_day_minutes']!=plan['time_of_day_minutes']):raise ValueError('Native reference dataset or clock differs')
            if rs.get('visibility_profile')!='gameplay_2d_and_3d'or rs.get('shadow_blend_profile')!='retail_original_raster'or rs.get('lighting_mode')!='real_time_grid':raise ValueError('Native reference capture profile differs')
            if rs['capture_end_screen_frame']<=rs['screen_frame']or verify_png(rp)!=(640,340)or verify_png(mp)!=(640,340):raise ValueError('Native reference frame is incomplete')
            if key:
                load_native_reference(root,key,reference,plan)
            elif rs['camera']!=list(camera_for_core(rx,ry))or not all(0<=v<=32768 for v in rs['camera'][:2]):raise ValueError('Raised core requires an ordinary in-world native reference')
            if rs['scroll']!=[rx*512-64,ry*256-42]:raise ValueError('Native reference scroll differs')
            with Image.open(rp)as im:reference_rgb=np.array(im.convert('RGB'))
            with Image.open(mp)as im:reference_mask=np.array(im)>0
            registered_overlap(array,dynamic,state['scroll'],reference_rgb,reference_mask,rs['scroll'],
                recover_black=state.get('registration_recovery')=='native_black_coverage_v1')
        core = array[42:298,64:576]
        for neighbor, edge in [((cx-1,cy),core[:,0]), ((cx+1,cy),core[:,-1]),
                               ((cx,cy-1),core[0]), ((cx,cy+1),core[-1])]:
            if neighbor not in planned and np.any(edge):
                record={'core':coord, 'unplanned_neighbor':list(neighbor),
                    'nonblack_boundary_pixels':int(np.any(edge,axis=1).sum())}
                (background_frontier if background_crop else frontier).append(record)
        for neighbor in ((cx-1, cy), (cx+1, cy), (cx, cy-1)):
            if neighbor in cache:
                seams.append(dict(core=coord, neighbor=list(neighbor), **overlap((array, dynamic), cache[neighbor], coord, neighbor)))
        cache[cx, cy] = array, dynamic
        while len(cache) > 260:
            cache.popitem(last=False)
        if meta and not meta.get('ownership'):
            px, py = cx*512-plan['bounds'][0], cy*256-plan['bounds'][1]
            tx, ty = px//1024, py//1024
            with Image.open(root / 'tiles' / f'{tx}_{ty}.png') as im:
                tile = np.array(im.convert('RGB').crop((px%1024, py%1024, px%1024+512, py%1024+256)))
            if not np.array_equal(tile, array[42:298,64:576]):
                raise ValueError(f'Export pixels differ from original capture: {path}')
            checked += CORE_W * CORE_H
    failures = [s for s in seams if s['static_mismatch_fraction'] > .001]
    # Extra registered viewports can cover a tall 3D object across a narrow
    # coarse-grid overlap. They retain the same native capture requirements.
    if meta and meta.get('ownership'):
        planned_names={f'{x}_{y}'for x,y in plan['cores']}
        for source in json.loads((root/'ownership-sources.json').read_text()):
            name=source['capture']
            if name in planned_names:continue
            path=root/'captures'/f'{name}.png';state=json.loads(path.with_suffix('.json').read_text())
            registration=state.get('source_registration')
            if registration=='native_camera_bridge_v1':
                cx,cy=state['core'];expected_scroll=[cx*512-64,cy*256-42]
                if state['camera']!=list(camera_for_core(cx,cy))or state['scroll']!=expected_scroll:raise ValueError(f'Bridge camera registration mismatch: {name}')
            elif registration=='native_camera_z_bridge_v1':
                if state['camera']!=state['requested_camera']or state['capture_end_camera']!=state['camera']or state['capture_end_scroll']!=state['scroll']:raise ValueError(f'Bridge camera changed: {name}')
                reference=state['bridge_reference']
                if reference not in planned_names:raise ValueError('Bridge registration reference must be a verified coarse-grid capture')
                rp=root/'captures'/f'{reference}.png';rs=json.loads(rp.with_suffix('.json').read_text())
                with Image.open(rp)as im:reference_rgb=np.array(im.convert('RGB'))
                with Image.open(root/'temporal'/rp.name)as im:reference_mask=np.array(im)>0
                with Image.open(path)as im:bridge_rgb=np.array(im.convert('RGB'))
                with Image.open(root/'temporal'/path.name)as im:bridge_mask=np.array(im)>0
                registered_overlap(bridge_rgb,bridge_mask,state['scroll'],reference_rgb,reference_mask,rs['scroll'])
            else:raise ValueError(f'Unknown source registration: {name}')
            if state['level']!=plan['level']or source['scroll']!=state['scroll']:raise ValueError(f'Bridge source registration mismatch: {name}')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if digest!=state['source_png_sha256']or digest!=source['sha256']or verify_png(path)!=(640,340):raise ValueError(f'Bridge provenance mismatch: {name}')
            retail_bridge=(state.get('provider')=='original_retail_1.22L'and state.get('executable_sha256')=='28bec27387bf53a553da320dd4883d00ff5bcc5a5f3d2658cca8e8ed586372b5'and state.get('capture_recipe')=='retail_redraw_bg_barrier_v2')
            if retail_bridge and state.get('time_of_day_minutes')!=plan['time_of_day_minutes']:raise ValueError('Bridge clock differs from its retail map')
            if (state['capture_recipe']!='console_redraw_bg_barrier_v3'and not retail_bridge)or state['capture_end_screen_frame']<=state['screen_frame']:raise ValueError(f'Bridge renderer did not advance: {name}')
            if verify_png(root/'temporal'/path.name)!=(640,340):raise ValueError(f'Bridge motion mask dimensions: {name}')
            visibility[state['visibility_profile']if state.get('visibility_profile')=='gameplay_2d_and_3d'else'requires_visibility_review']+=1
            shadow_blending['pinned_retail_raster_capture'if retail_bridge and state.get('shadow_blend_profile')=='retail_original_raster'else'format_corrected_capture'if state.get('shadow_blend_profile')=='rgb565_black_alpha_to_argb1555_v1'else'requires_shadow_review']+=1
            modes.add(state['lighting_mode']);hashes.append(digest)
            sampling[f'{state.get("temporal_samples",3)} samples; {state.get("temporal_sample_interval_seconds",1/24):.6g} seconds apart']+=1
    pixels = sum(s['static_pixels'] for s in seams)
    mismatches = sum(s['static_mismatches'] for s in seams)
    foreground=sum(s['foreground_static_pixels']for s in seams)
    foreground_errors=sum(s['foreground_static_mismatches']for s in seams)
    quilting=json.loads((root/'quilting.json').read_text())if meta and meta.get('ownership')else None
    nonblack=None
    if quilting:checked,nonblack=verify_ownership(root,meta)
    if nonblack==0 and int(plan.get('source_objects_by_class',{}).get('9',0)):
        raise ValueError('The source map contains scenery, but the original renderer returned no foreground')
    report = {'provider': 'original_game', 'captures': len(hashes), 'missing_captures': absent,
              'lighting_modes': sorted(modes), 'capture_hashes': 'all verified',
              'visibility_validation':dict(visibility),
              'shadow_blending_validation':dict(shadow_blending),
              'geyser_blending_validation':dict(geyser_blending),
              'export_pixels_exactly_equal_to_raw_captures': checked,
              'seam_pairs': len(seams), 'static_overlap_pixels': pixels,
              'static_overlap_mismatches': mismatches,
              'static_overlap_exact_fraction': 1-mismatches/max(1,pixels),
              'foreground_static_overlap_pixels':foreground,
              'foreground_static_overlap_exact_fraction':1-foreground_errors/max(1,foreground),
              'seams_over_0_1_percent_static_difference': len(failures),
              'nonblack_unplanned_boundaries': len(frontier),
              'native_background_crop_boundaries':len(background_frontier),
              'temporal_mask': 'Per-source measured samples, 8 pixel dilation; changing pixels are reported separately',
              'temporal_sampling':dict(sampling),
              'temporal_limitation': 'A stitched snapshot does not synchronize animation phases between captures.',
              'acceptance': 'review_required' if failures or absent or frontier else 'static_seam_threshold_passed'}
    if quilting:
        report.update(stitching=quilting,nonblack_export_pixels_with_native_source=nonblack,
                      all_nonblack_export_pixels_have_native_source=True)
        edges=verify_edges(root,meta);dump(root/'edge-validation.json',edges)
        report['actual_stitched_edges']={k:v for k,v in edges.items()if k not in ('samples','static_samples')}
        report['acceptance']='review_required'if absent or frontier or edges['unmeasured_edges_requiring_review']else'native_pixels_verified; remaining joins are measured animation changes'
        meta['static_boundary_pixels_requiring_review']=edges['unmeasured_edges_requiring_review']
        meta['animated_boundary_pixels']=edges['measured_animation_edges']
        dump(root/'manifest.json',meta)
    if visibility['requires_visibility_review']:report['acceptance']='review_required'
    if shadow_blending['requires_shadow_review']:report['acceptance']='review_required'
    if meta and full:
        if verify_png(root / 'full-resolution.png') != (meta['width'], meta['height']):
            raise ValueError('Full-resolution PNG dimensions')
        report['full_png_crc'] = 'verified'
        report['full_png_samples_equal_tiles'] = verify_samples(root, meta)
    dump(root / 'seams.json', seams)
    dump(root / 'seam-failures.json', failures)
    dump(root / 'frontier.json', frontier)
    dump(root / 'validation.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--no-full', action='store_true')
    args = p.parse_args()
    print(json.dumps(audit(args.directory, not args.no_full), indent=2))

if __name__ == '__main__':
    main()
