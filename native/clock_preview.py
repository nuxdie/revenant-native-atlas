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


def compose(base,twilight,recovery=None):
    catalog=copy.deepcopy(base);by_level={l['level']:l for l in catalog['levels']}
    for addition in (recovery or{}).get('levels',[]):
        if addition['level']in by_level:continue  # Prefer an exact native image if one exists.
        if not addition.get('recovery'):raise ValueError('Recovery catalog contains an unlabeled map')
        entry=copy.deepcopy(addition);catalog['levels'].append(entry);by_level[entry['level']]=entry
    catalog['levels'].sort(key=lambda l:l['level'])
    for addition in twilight.get('levels',[]):
        current=by_level.get(addition['level'])
        if current is None:continue
        variants=current.setdefault('variants',[{k:v for k,v in current.items()if k!='variants'}])
        variants[:]=[v for v in variants if v['variant']!=addition['variant']]+[addition]
    cycle_levels=base.get('cycling_levels',[0,5])
    for level in catalog['levels']:
        if level['level']in cycle_levels:level['clock']=clock_metadata()
    available={(l['level'],v['variant'])for l in catalog['levels']for v in l.get('variants',[l])}
    missing=[m for m in base.get('missing_maps',[])if(m['level'],m['variant'])not in available]+[dict(level=level,variant='twilight')for level in cycle_levels if(level,'twilight')not in available]
    expected=base.get('expected_maps',39)+len(cycle_levels);ready=len(available)
    available_complete=ready==expected and not missing
    recovered=[l for l in catalog['levels']if l.get('recovery')]
    complete=available_complete and not recovered
    catalog.update(revision='retail-1-22l-with-recoveries'if recovered else'retail-1-22l-clock'if complete else'retail-clock-preview',preview=not available_complete,publication_complete=complete,
        available_complete=available_complete,recovered_levels=[l['level']for l in recovered],recovered_maps=len(recovered),
        omitted_source_placements=sum(l['recovery']['omitted_placements']for l in recovered),
        unresolved_levels=sorted({m['level']for m in missing}),missing_maps=missing,expected_maps=expected,ready_maps=ready)
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
    p.add_argument('--recovery-root',type=Path,help='Explicitly include audited, labeled recovery maps from this output root')
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
        if a.recovery_root:paths+=list(a.recovery_root.glob('*/level-*/validation.json'))
        fingerprint=tuple((str(x),x.stat().st_mtime_ns)for x in sorted(paths))
        if fingerprint!=prior:
            base=prepare(Path('retail-output'),Path('runtime/retail-publication'))
            twilight=prepare(Path('retail-clock-output'),out/'twilight')
            b=json.loads(Path('runtime/retail-publication/catalog.json').read_text());t=json.loads((out/'twilight/catalog.json').read_text())
            recovered=prepare(a.recovery_root,out/'recovery',labeled_recovery=True)if a.recovery_root else dict(uploads=[])
            r=json.loads((out/'recovery/catalog.json').read_text())if a.recovery_root else None
            catalog=compose(b,t,r);uploads=[x for x in base['uploads']+twilight['uploads']+recovered['uploads']if x['key']!='catalog.json']
            local_preview(catalog,uploads,a.local)
            if publisher:
                result=publish_files(dict(complete=False,uploads=uploads),publisher,out/'upload-status.json',passes=5)
                if result['failed_files']:raise RuntimeError('Preview files remain held; resume the clock preview publisher')
                path=out/'retail-preview-catalog.json';dump(path,catalog)
                publisher.upload(dict(key=path.name,path=str(path.resolve()),size=path.stat().st_size,sha256=digest(path)))
            report=dict(images=catalog['ready_maps'],twilight_images=twilight['maps'],base_images=base['maps'],published=bool(publisher))
            dump(out/'status.json',report);print(report,flush=True);prior=fingerprint
            if catalog.get('available_complete'):break
        if not a.watch or time.monotonic()>deadline:break
        time.sleep(10)
