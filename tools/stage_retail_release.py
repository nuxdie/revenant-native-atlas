#!/usr/bin/env python3
"""Stage individually named retail release files after complete native acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from atlas import dump
from native.publish_retail import prepare


def stage(root,out,publication):
    prepared=prepare(root,publication)
    if not prepared['complete']:
        raise RuntimeError(f"Retail release held: {prepared['maps']}/{prepared['expected_maps']} accepted images; no release manifest staged")
    catalog=json.loads((publication/'catalog.json').read_text())
    maps=[variant for level in catalog['levels']for variant in level.get('variants',[level])]
    identities={(m['revision'],m['level']):m for m in maps}
    kinds={'tiles.pack':('tilepack','tiles.pack'),'tiles.json':('tileindex','tiles.json'),
        'overview.jpg':('overview','overview.jpg'),'full-resolution.png':('png','png'),'full-resolution.tif':('tif','tif')}
    files=[];out.mkdir(parents=True,exist_ok=True)
    for item in prepared['uploads']:
        key=item['key'];source=Path(item['path'])
        if key=='catalog.json':
            asset='catalog.json';kind='catalog';level=variant=None
        else:
            parts=key.split('/');level=int(parts[2].removeprefix('level-'))
            variant=identities[parts[1],level]['variant'];kind,suffix=kinds[parts[3]]
            asset=f'level-{level}-{variant}.{suffix}'
        target=out/asset
        if target.is_symlink():target.unlink()
        elif target.exists():raise ValueError(f'Refusing to replace an unrelated regular file: {target}')
        target.symlink_to(source.resolve())
        files.append(dict(asset=asset,path=key,kind=kind,level=level,variant=variant,
            bytes=item['size'],sha256=item['sha256']))
    manifest=dict(dataset=catalog['dataset'],locations=len(catalog['levels']),images=len(maps),
        files=files,rendering='Original retail 1.22L executable, native resolution; separately rendered authored day/night states')
    dump(out/'release-manifest.json',manifest)
    print(f'Staged {len(files)} verified assets plus release-manifest.json in {out}',flush=True)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('retail-output'))
    p.add_argument('--out',type=Path,default=Path('release-assets'))
    p.add_argument('--publication',type=Path,default=Path('runtime/retail-publication'))
    a=p.parse_args();stage(a.root,a.out,a.publication)
