"""Capture every drawable level; quilt and verify completed levels concurrently."""
import concurrent.futures as futures
import argparse
from collections import deque
import fcntl
import json
import os
from pathlib import Path
import signal
import threading
import time
import traceback

from atlas import dump
from .audit import audit
from .expand import expanded
from .export import run
from .finalize import finalize
from .game import NativeGame,RUNTIME
from .launch import launch
from .plan import create_plan
from .quilt import quilt
from .repair_edges import repair


ROOT=Path('native-output');STATE=RUNTIME/'all-level-build';STATE.mkdir(exist_ok=True)
lock=threading.Lock();status={'started_at':time.time(),'levels':{},'current_level':None}


def update(level,phase,**fields):
    with lock:
        status['levels'].setdefault(str(level),{}).update(phase=phase,**fields)
        status['completed']=sum(v['phase']=='complete'for v in status['levels'].values())
        status['updated_at']=time.time();dump(STATE/'status.json',status)
    print(f'LEVEL {level}: {phase}',flush=True)


def finish(level):
    root=ROOT/f'level-{level}';update(level,'quilting');quilt(root,full=False)
    update(level,'auditing');report=audit(root,full=False)
    if report['nonblack_unplanned_boundaries']:
        return 'expand'
    if report['acceptance']=='review_required'and report.get('actual_stitched_edges',{}).get('unmeasured_edges_requiring_review'):
        update(level,'reviewing joins');repair(root,iterations=2);report=audit(root,full=False)
    if report['acceptance']=='review_required':
        update(level,'review_required',acceptance=report['acceptance']);return 'review_required'
    update(level,'writing PNG');finalize(root)
    update(level,'complete',acceptance=report['acceptance']);return 'complete'


def restart_owned_game():
    target=str((RUNTIME/'game/Revenant.exe').resolve()).encode()
    short=os.environ.get('REVENANT_EXE','').encode()
    prefix=(RUNTIME/'prefix').resolve()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            args=(proc/'cmdline').read_bytes().split(b'\0')
            if args and (args[0]==target or short and args[0]==short):
                environment=dict(entry.split(b'=',1)for entry in (proc/'environ').read_bytes().split(b'\0')if b'='in entry)
                owned=environment.get(b'WINEPREFIX')
                if owned and Path(os.fsdecode(owned)).resolve()==prefix:os.kill(int(proc.name),signal.SIGTERM)
        except (OSError,ProcessLookupError):pass
    time.sleep(1)
    launch();NativeGame().command('@time 487')


def main(selected=None):
    levels=sorted(int(p.parent.name.split('-')[1])for p in Path('output').glob('level-*/manifest.json'))
    if selected is not None:levels=[level for level in levels if level in selected]
    status['total']=len(levels);pending=deque();plans={};attempts={};expansions={};active={}
    for level in levels:
        root=ROOT/f'level-{level}';report=root/'validation.json'
        if report.exists()and(root/'full-resolution.png').exists():
            r=json.loads(report.read_text())
            if r.get('acceptance')!='review_required'and r.get('full_png_crc')=='verified':
                update(level,'complete',acceptance=r['acceptance']);continue
        path=Path('runtime/all-level-plans')/f'level-{level}.json'
        plan=json.loads(path.read_text())if path.exists()else create_plan('output','runtime/game',level)
        dump(path,plan);plans[level]=plan;pending.append(level);update(level,'queued',planned_captures=plan['core_count'])
    with (RUNTIME/'export.lock').open('a')as camera_lock,futures.ThreadPoolExecutor(max_workers=2)as pool:
        fcntl.flock(camera_lock,fcntl.LOCK_EX)
        while pending or active:
            if pending:
                level=pending.popleft();status['current_level']=level;update(level,'capturing')
                try:
                    run(plans[level],ROOT,settle=.1,full=False,fast=False)
                    active[pool.submit(finish,level)]=level
                except Exception as exc:
                    attempts[level]=attempts.get(level,0)+1
                    update(level,'capture_retry'if attempts[level]<3 else'failed',error=str(exc),attempts=attempts[level])
                    traceback.print_exc()
                    if attempts[level]<3:
                        restart_owned_game();pending.appendleft(level)
            for job in list(active):
                if not job.done():continue
                level=active.pop(job)
                try:
                    result=job.result()
                    if result=='expand':
                        expansions[level]=expansions.get(level,0)+1
                        if expansions[level]>4:raise RuntimeError('Native frontier still reaches unplanned coverage')
                        plans[level],added=expanded(ROOT/f'level-{level}',Path('output'))
                        update(level,'extending coverage',additional_captures=added);pending.append(level)
                except Exception as exc:
                    update(level,'failed',error=str(exc));traceback.print_exc()
            if not pending and active:time.sleep(.25)
    status['current_level']=None;status['finished_at']=time.time();dump(STATE/'status.json',status)
    if status['completed']!=len(levels):raise RuntimeError(f'Only {status["completed"]}/{len(levels)} maps passed')
    print('ALL NATIVE LEVELS COMPLETE',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--levels',help='Comma-separated, disjoint level set for an isolated renderer')
    args=parser.parse_args()
    try:main(set(map(int,args.levels.split(',')))if args.levels else None)
    finally:
        try:NativeGame().command('@normal')
        except RuntimeError:pass
