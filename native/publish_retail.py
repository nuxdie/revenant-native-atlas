"""Stage a complete retail atlas; switch its catalog only after every map verifies."""
import argparse
from collections import defaultdict
import getpass
import json
from pathlib import Path

from atlas import dump
from .publish_pack import digest
from .publish_upload import Publisher


def prepare(root=Path('retail-output'),out=Path('runtime/retail-publication')):
    dataset=json.loads((root/'dataset.json').read_text())
    expected={(m['level'],variant)for m in dataset['levels']for variant in m['variants']}
    maps=[];uploads=[]
    def upload(key,path,sha=None):
        uploads.append(dict(key=key,path=str(path.resolve()),size=path.stat().st_size,sha256=sha or digest(path)))
    for level,variant in sorted(expected):
        directory=root/variant/f'level-{level}'
        paths=[directory/name for name in ['manifest.json','validation.json','tiff-validation.json','full-resolution.png','full-resolution.tif']]
        if not all(p.exists()for p in paths):continue
        meta,validation,tiff=(json.loads(p.read_text())for p in paths[:3])
        if validation['acceptance']=='review_required' or validation.get('full_png_crc')!='verified':continue
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
    catalog=out/'catalog.json'
    dump(catalog,dict(revision='retail-1-22l',dataset='GOG 1.22L',levels=levels,
        expected_levels=dataset['expected_levels'],expected_maps=len(expected),ready_maps=len(maps)))
    # Never replace the existing public atlas with an incomplete retail build.
    if complete:upload('catalog.json',catalog)
    result=dict(complete=complete,maps=len(maps),expected_maps=len(expected),levels=len(levels),uploads=uploads)
    dump(out/'upload-manifest.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('retail-output'))
    p.add_argument('--out',type=Path,default=Path('runtime/retail-publication'))
    p.add_argument('--publish',help='Atlas URL; leave unset to stage locally')
    a=p.parse_args();manifest=prepare(a.root,a.out)
    print(f"Retail maps ready: {manifest['maps']}/{manifest['expected_maps']}; catalog complete: {manifest['complete']}",flush=True)
    if a.publish:
        key=getpass.getpass('Atlas upload key (hidden): ')
        publisher=Publisher(a.publish,key,a.out/'remote-verified.json')
        for item in manifest['uploads']:publisher.upload(item)
        print('PUBLIC RETAIL CATALOG' if manifest['complete'] else 'Files staged; public catalog retained',flush=True)
