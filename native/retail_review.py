"""Reobserve held retail joins with the matching module and authored clock."""
import argparse
import fcntl
import json
from pathlib import Path
import time

from atlas import dump
from .audit import audit
from .bigtiff import build as bigtiff
from .finalize import finalize
from .edges import verify_edges
from .quilt import quilt
from .recut import recut
from .refresh_sources import refresh
from .repair_edges import repair
from .retail import RUNTIME


def review(root,attempts=6):
    report=json.loads((root/'validation.json').read_text())
    if report['acceptance']!='review_required':return True
    if report['nonblack_unplanned_boundaries']:
        raise RuntimeError('Coverage needs additional registered native cameras')
    for attempt in range(attempts):
        meta=json.loads((root/'manifest.json').read_text())
        edges=verify_edges(root,meta)
        previous_count=edges['unmeasured_edges_requiring_review']
        identifiers=set(edges.get('static_owner_ids',[]))or{i for sample in edges['static_samples']for i in sample['owners']if i}
        sources=json.loads((root/'ownership-sources.json').read_text())
        names=[s['capture']for s in sources if s['id']in identifiers]
        if not names:raise RuntimeError('Held retail map has no static source candidates')
        if any(name.startswith('bridge-')for name in names):
            raise RuntimeError('Inspect the registered bridge separately')
        samples=32 if attempt<2 else 64
        print(f'{root}: attempt {attempt+1}, {len(names)} native sources, {samples} samples at 0.1 s',flush=True)
        archive=RUNTIME/'review-archive'/root.parent.name/root.name/f'{int(time.time())}-{attempt}'
        refresh(root,names,archive,temporal_samples=samples,temporal_interval=.1,
            reason='investigate static retail joins with longer native animation observation')
        if not meta.get('native_viewport_bridges'):quilt(root,full=False)
        report=audit(root,full=False)
        if report['acceptance']=='review_required':
            repair(root,iterations=2);recut(root,iterations=2)
            report=audit(root,full=False)
        if report['acceptance']!='review_required':
            finalize(root);bigtiff(root)
            print(f'REVIEW RESOLVED {root}',flush=True)
            return True
        print(f'STILL HELD {root}: {report["actual_stitched_edges"]["unmeasured_edges_requiring_review"]}',flush=True)
        if report['actual_stitched_edges']['unmeasured_edges_requiring_review']>=previous_count:
            print('Longer native observation did not resolve the static geometry; inspect registered bridge views.',flush=True)
            return False
    return False


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directories',nargs='+',type=Path);p.add_argument('--attempts',type=int,default=6)
    a=p.parse_args();unresolved=[]
    with(RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for root in a.directories:
            if not review(root,a.attempts):unresolved.append(str(root))
    dump(RUNTIME/'review-status.json',dict(unresolved=unresolved,finished_at=time.time()))
    if unresolved:raise RuntimeError(f'Retail maps remain held: {unresolved}')
