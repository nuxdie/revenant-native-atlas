"""Review completed retail captures in one idle isolated instance; retain every hold."""
import argparse
import fcntl
import json
from pathlib import Path
import time

from atlas import dump
from .bigtiff import build as bigtiff
from .bridge import bridge
from .retail import ROOT,RUNTIME
from .retail_batch import restart
from .retail_raise_cores import raise_cores
from .retail_review import review
from .retail_expand import expand
from .retail_export import capture


def wait_for_batch():
    while True:
        try:
            pid=int((RUNTIME/'batch.pid').read_text())
            alive=b'native.retail_batch'in Path(f'/proc/{pid}/cmdline').read_bytes()
        except(OSError,ValueError):alive=False
        if not alive:return
        time.sleep(5)


def finish(levels,root=ROOT/'retail-output'):
    dataset=json.loads((root/'dataset.json').read_text());records=[];started=False
    with(RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for item in dataset['levels']:
            if item['level']not in levels:continue
            for variant in item['variants']:
                directory=root/variant/f'level-{item["level"]}'
                row=dict(level=item['level'],variant=variant)
                try:
                    path=directory/'validation.json'
                    if not path.exists():row['state']='held_missing_capture';records.append(row);continue
                    validation=json.loads(path.read_text())
                    meta=json.loads((directory/'manifest.json').read_text())
                    if meta['module']!='Ahkuilon':
                        states=[json.loads(p.read_text())for p in(directory/'captures').glob('*.json')]
                        if any(s.get('native_module','').casefold()!=meta['module'].casefold()for s in states):
                            if not started:restart();started=True
                            plan=json.loads((directory/'plan.json').read_text())
                            capture(plan,variant,root,rebuild_held=True);validation=json.loads(path.read_text())
                    if validation.get('nonblack_unplanned_boundaries'):
                        if not started:restart();started=True
                        for _ in range(3):
                            expand(directory);validation=json.loads(path.read_text())
                            if not validation.get('nonblack_unplanned_boundaries'):break
                    if validation['acceptance']=='review_required':
                        if not started:restart();started=True
                        if not review(directory,attempts=2):
                            for _ in range(3):
                                if raise_cores(directory):break
                                edges=json.loads((directory/'edge-validation.json').read_text())
                                samples=edges['static_samples']
                                if not samples:break
                                point=samples[0]['world_pixel']
                                sources={s['id']:s for s in json.loads((directory/'ownership-sources.json').read_text())}
                                ref=next((sources[i]['capture']for i in samples[0]['owners']if i and not sources[i]['capture'].startswith('bridge-')),None)
                                if ref is None:break
                                state=json.loads((directory/'captures'/f'{ref}.json').read_text())
                                progress=False
                                for height in [192,418]:
                                    camera=[*state['camera'][:2],state['camera'][2]+height]
                                    try:
                                        bridge(directory,camera=camera,reference=ref,point=point,partial=True)
                                        progress=True;break
                                    except(RuntimeError,ValueError)as exc:print('Registered bridge retained its hold:',str(exc),flush=True)
                                validation=json.loads(path.read_text())
                                if validation['acceptance']!='review_required'or not progress:break
                    validation=json.loads(path.read_text())
                    if validation['acceptance']!='review_required'and(directory/'full-resolution.png').exists():
                        bigtiff(directory);row['state']='accepted'
                    else:row['state']='held_for_review'
                except Exception as exc:
                    row.update(state='held_error',error=str(exc));print('REVIEW HOLD',row,flush=True)
                records.append(row);dump(RUNTIME/'finish-status.json',dict(state='reviewing',maps=records))
    report=dict(state='finished',maps=records,held=[r for r in records if r['state']!='accepted'],
        note='Review completed for assigned captures. Held or missing maps remain unpublished.')
    dump(RUNTIME/'finish-status.json',report);print(json.dumps(report),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--levels',required=True)
    p.add_argument('--wait-for-batch',action='store_true');a=p.parse_args()
    if a.wait_for_batch:wait_for_batch()
    finish(set(map(int,a.levels.split(','))))
