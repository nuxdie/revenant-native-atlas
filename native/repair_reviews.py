"""Recheck held maps with fresh native frames and a longer motion observation."""
import argparse
import fcntl
import json
from pathlib import Path
import time

from atlas import dump
from .audit import audit
from .finalize import finalize
from .game import RUNTIME,NativeGame
from .quilt import quilt
from .recut import recut
from .refresh_sources import refresh
from .repair_edges import repair


def review(root):
    report=json.loads((root/'validation.json').read_text())
    if report['acceptance']!='review_required':return True
    if report['nonblack_unplanned_boundaries']:raise RuntimeError('Unplanned native coverage requires capture-plan expansion')
    for attempt in range(2):
        edges=json.loads((root/'edge-validation.json').read_text())
        identifiers={ident for sample in edges['static_samples']for ident in sample['owners']if ident}
        sources=json.loads((root/'ownership-sources.json').read_text())
        names=[s['capture']for s in sources if s['id']in identifiers]
        if not names:raise RuntimeError('Held map has no static edge candidates')
        samples=32 if attempt==0 else 64
        print(f'{root.name}: {len(names)} fresh viewports, {samples} measured animation samples per view',flush=True)
        archive=Path('runtime/validation-recaptures')/root.name/f'{int(time.time())}-{attempt}'
        refresh(root,names,archive,temporal_samples=samples,temporal_interval=.1,
                reason='investigate unexplained native ownership joins; observe slow animation without enlarging masks from overlap differences')
        quilt(root,full=False);report=audit(root,full=False)
        if report['acceptance']=='review_required':
            repair(root,iterations=4);recut(root,iterations=2);report=audit(root,full=False)
        if report['acceptance']!='review_required':
            finalize(root)
            print(f'{root.name}: REVIEW RESOLVED, all native checks passed',flush=True)
            return True
        print(f'{root.name}: still held, {report["actual_stitched_edges"]["unmeasured_edges_requiring_review"]} static edges',flush=True)
    return False


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--levels',required=True);args=parser.parse_args()
    unresolved=[]
    print('Waiting for this isolated renderer to finish its capture batch',flush=True)
    with (RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            for level in map(int,args.levels.split(',')):
                root=Path('native-output')/f'level-{level}'
                if not (root/'validation.json').exists():unresolved.append(level);continue
                if not review(root):unresolved.append(level)
        finally:NativeGame().command('@normal')
    dump(RUNTIME/'review-status.json',dict(unresolved=unresolved,finished_at=time.time()))
    if unresolved:raise RuntimeError(f'Native levels still need review: {unresolved}')
    print('ALL ASSIGNED NATIVE REVIEWS RESOLVED',flush=True)


if __name__=='__main__':main()
