"""Publish an opt-in retail clock preview without replacing the complete-atlas catalog."""
import argparse
import copy
import getpass
import json
from pathlib import Path
import time

from atlas import dump
from .publish_retail import prepare,publish_files
from .publish_pack import digest
from .publish_upload import Publisher
from .retail_clock import clock_metadata


def compose(base,twilight):
    catalog=copy.deepcopy(base);by_level={l['level']:l for l in catalog['levels']}
    for addition in twilight.get('levels',[]):
        current=by_level.get(addition['level'])
        if current is None:continue
        variants=current.setdefault('variants',[{k:v for k,v in current.items()if k!='variants'}])
        variants[:]=[v for v in variants if v['variant']!=addition['variant']]+[addition]
    for level in catalog['levels']:
        if level['level']in(0,5):level['clock']=clock_metadata()
    catalog.update(revision='retail-clock-preview',preview=True,publication_complete=False,
        unresolved_levels=[41,42,43],expected_maps=base.get('expected_maps',39)+2,
        ready_maps=sum(len(l.get('variants',[]))or 1 for l in catalog['levels']))
    return catalog


def local_preview(catalog,uploads,target):
    target.mkdir(parents=True,exist_ok=True)
    for item in uploads:
        if item['key']=='catalog.json':continue
        p=target/item['key'];p.parent.mkdir(parents=True,exist_ok=True);source=Path(item['path']).resolve()
        if p.is_symlink()and p.resolve()==source:continue
        if p.exists()or p.is_symlink():raise ValueError(f'Unexpected local preview object: {p}')
        p.symlink_to(source)
    dump(target/'catalog.json',catalog)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish');p.add_argument('--watch',action='store_true')
    p.add_argument('--local',type=Path,default=Path('runtime/retail-preview-data'));a=p.parse_args()
    out=Path('runtime/clock-publication');out.mkdir(parents=True,exist_ok=True)
    publisher=Publisher(a.publish,getpass.getpass('Atlas upload key (hidden): '),out/'remote-verified.json')if a.publish else None
    if publisher:
        # Reuse the already verified immutable baseline files.
        old=Path('runtime/retail-publication/remote-verified.json')
        if old.exists():publisher.verified.update(json.loads(old.read_text()))
    deadline=time.monotonic()+6*3600;prior=None
    while True:
        paths=list(Path('retail-output').glob('*/level-*/validation.json'))+list(Path('retail-clock-output').glob('*/level-*/validation.json'))
        fingerprint=tuple((str(x),x.stat().st_mtime_ns)for x in sorted(paths))
        if fingerprint!=prior:
            base=prepare(Path('retail-output'),Path('runtime/retail-publication'))
            twilight=prepare(Path('retail-clock-output'),out/'twilight')
            b=json.loads(Path('runtime/retail-publication/catalog.json').read_text());t=json.loads((out/'twilight/catalog.json').read_text())
            catalog=compose(b,t);uploads=[x for x in base['uploads']+twilight['uploads']if x['key']!='catalog.json']
            local_preview(catalog,uploads,a.local)
            if publisher:
                result=publish_files(dict(complete=False,uploads=uploads),publisher,out/'upload-status.json',passes=5)
                if result['failed_files']:raise RuntimeError('Preview files remain held; resume the clock preview publisher')
                path=out/'retail-preview-catalog.json';dump(path,catalog)
                publisher.upload(dict(key=path.name,path=str(path.resolve()),size=path.stat().st_size,sha256=digest(path)))
            report=dict(images=catalog['ready_maps'],twilight_images=twilight['maps'],base_images=base['maps'],published=bool(publisher))
            dump(out/'status.json',report);print(report,flush=True);prior=fingerprint
            if twilight['maps']==2 and base['maps']==36:break
        if not a.watch or time.monotonic()>deadline:break
        time.sleep(10)
