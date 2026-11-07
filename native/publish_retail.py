"""Stage a complete retail atlas; switch its catalog only after every map verifies."""
import argparse
from collections import defaultdict
import getpass
import json
from pathlib import Path
import time

from atlas import dump
from .publish_pack import digest
from .publish_upload import Publisher


def prepare(root=Path('retail-output'),out=Path('runtime/retail-publication')):
    dataset=json.loads((root/'dataset.json').read_text())
    expected={(m['level'],variant)for m in dataset['levels']for variant in m['variants']}
    profiles={(m['level'],variant):profile for m in dataset['levels']for variant,profile in m.get('lighting_profiles',{}).items()}
    maps=[];uploads=[];held=[]
    def upload(key,path,sha=None):
        uploads.append(dict(key=key,path=str(path.resolve()),size=path.stat().st_size,sha256=sha or digest(path)))
    for level,variant in sorted(expected):
        directory=root/variant/f'level-{level}'
        if dataset.get('recovery')or(root/'recovery.json').exists()or(directory/'recovery.json').exists():
            held.append(dict(level=level,variant=variant,reason='Recovery changes authored placements; not eligible for the exact edition'))
            continue
        paths=[directory/name for name in ['manifest.json','validation.json','tiff-validation.json','full-resolution.png','full-resolution.tif']]
        if not all(p.exists()for p in paths):continue
        meta,validation,tiff=(json.loads(p.read_text())for p in paths[:3])
        if (not validation.get('acceptance','').startswith('native_pixels_verified')
                or validation.get('full_png_crc')!='verified'
                or validation.get('actual_stitched_edges',{}).get('unmeasured_edges_requiring_review')!=0):continue
        profile=profiles.get((level,variant))
        if profile or meta['module']!='Ahkuilon':
            states=[json.loads(p.read_text())for p in(directory/'captures').glob('*.json')]
            if not states:continue
            if profile and any(s.get('ambient')!=profile['expected_native_ambient']or s.get('ambient_rgb')!=profile['ambient_rgb']or s.get('ambient_fade_frames',0)for s in states):continue
            if meta['module']!='Ahkuilon'and any(s.get('native_module','').casefold()!=meta['module'].casefold()for s in states):continue
        sha=validation['full_png_sha256']
        if tiff['source_png_sha256']!=sha or digest(paths[3])!=sha or digest(paths[4])!=tiff['sha256']:
            raise ValueError(f'Stale retail download: level {level} {variant}')
        revision=f'r-{level}-{variant}-{sha[:20]}'
        target=out/variant/f'level-{level}';target.mkdir(parents=True,exist_ok=True)
        index_path=target/'tiles.json';pack=target/'tiles.pack'
        old=json.loads(index_path.read_text())if index_path.exists()else{}
        if old.get('source_png_sha256')!=sha or not pack.exists():
            index={};offset=0
            with pack.with_suffix('.pack.tmp').open('wb')as stream:
                for tx,ty in sorted(map(tuple,meta['tiles'])):
                    data=(directory/'tiles'/f'{tx}_{ty}.png').read_bytes()
                    import hashlib
                    index[f'{tx}_{ty}']=dict(offset=offset,length=len(data),sha256=hashlib.sha256(data).hexdigest())
                    stream.write(data);offset+=len(data)
            pack.with_suffix('.pack.tmp').replace(pack)
            dump(index_path,dict(pack='tiles.pack',source_png_sha256=sha,tiles=index))
        prefix=f'releases/{revision}/level-{level}/'
        for name,path,known in [('tiles.pack',pack,None),('tiles.json',index_path,None),
            ('overview.jpg',directory/'overview.jpg',None),('full-resolution.png',paths[3],sha),
            ('full-resolution.tif',paths[4],tiff['sha256'])]:upload(prefix+name,path,known)
        maps.append(dict(level=level,module=meta['module'],variant=variant,game_time=meta['game_time'],
            names=meta['names'],width=meta['width'],height=meta['height'],bounds=meta['bounds'],
            tile_size=meta['tile_size'],tiles=meta['tiles'],statistics=meta['statistics'],
            provider=meta['provider'],revision=revision,content_revision=sha[:16],
            png_bytes=paths[3].stat().st_size,sha256=sha,tiff_bytes=paths[4].stat().st_size,tiff_sha256=tiff['sha256']))
    by_level=defaultdict(list)
    for m in maps:by_level[m['level']].append(m)
    levels=[]
    for level,variants in sorted(by_level.items()):
        primary=next((v for v in variants if v['variant']=='day'),variants[0])
        levels.append(dict(primary,variants=variants)if len(variants)>1 else primary)
    complete=len(maps)==len(expected)
    missing=[dict(level=level,variant=variant)for level,variant in sorted(expected-{(m['level'],m['variant'])for m in maps})]
    catalog=out/'catalog.json'
    dump(catalog,dict(revision='retail-1-22l',dataset='GOG 1.22L',levels=levels,
        expected_levels=dataset['expected_levels'],expected_maps=len(expected),ready_maps=len(maps),
        missing_maps=missing,cycling_levels=sorted({m['level']for m in dataset['levels']if 'night'in m['variants']})))
    # The July catalog is a separate edition. Only clock_preview publishes the
    # composed retail catalog, after all referenced files have been verified.
    result=dict(complete=complete,held=held,missing_maps=missing,maps=len(maps),expected_maps=len(expected),levels=len(levels),uploads=uploads)
    dump(out/'upload-manifest.json',result)
    return result


def publish_files(manifest,publisher,status,passes=3):
    """Retry individual failures without blocking unrelated verified assets."""
    if not 1<=passes<=10:raise ValueError('Upload passes must be between 1 and 10')
    catalogs=[x for x in manifest['uploads']if x['key']=='catalog.json']
    pending=[x for x in manifest['uploads']if x['key']!='catalog.json']
    total=len(pending);finished=0;failures=[]
    for attempt in range(passes):
        failures=[];next_pending=[]
        for item in pending:
            try:publisher.upload(item);finished+=1
            except Exception as exc:
                next_pending.append(item);failures.append(dict(key=item['key'],error=str(exc)))
                print('File held for retry:',item['key'],str(exc),flush=True)
            dump(status,dict(state='uploading',pass_number=attempt+1,verified_files=finished,
                total_files=total,failed_files=failures,catalog_published=False))
        pending=next_pending
        if not pending:break
        if attempt+1<passes:time.sleep(5)
    published=False
    if not pending and manifest['complete']:
        for item in catalogs:publisher.upload(item)
        published=bool(catalogs)
    report=dict(state='held_files'if pending else'files_verified',verified_files=finished,total_files=total,
        failed_files=failures,retail_complete=manifest['complete'],catalog_published=published)
    dump(status,report);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('retail-output'))
    p.add_argument('--out',type=Path,default=Path('runtime/retail-publication'))
    p.add_argument('--publish',help='Atlas URL; leave unset to stage locally')
    p.add_argument('--resume-staged',action='store_true',help='Resume the existing staged upload manifest')
    p.add_argument('--passes',type=int,default=3,help='Retry failed files in up to this many passes (1–10)')
    a=p.parse_args();manifest=json.loads((a.out/'upload-manifest.json').read_text())if a.resume_staged else prepare(a.root,a.out)
    print(f"Retail maps ready: {manifest['maps']}/{manifest['expected_maps']}; catalog complete: {manifest['complete']}",flush=True)
    if a.publish:
        key=getpass.getpass('Atlas upload key (hidden): ')
        publisher=Publisher(a.publish,key,a.out/'remote-verified.json')
        result=publish_files(manifest,publisher,a.out/'upload-status.json',a.passes)
        if result['failed_files']:raise RuntimeError('Some files remain held; resume the staged upload manifest')
        print('Retail files verified; publish the edition catalog with native.clock_preview',flush=True)
