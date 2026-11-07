"""Recapture geyser viewports through complete mesh/controller blending."""
import fcntl
import argparse
import json
from pathlib import Path
import time

from atlas import dump
from .audit import audit
from .finalize import finalize
from .game import NativeGame,RUNTIME
from .quilt import quilt
from .recut import recut
from .refresh_sources import refresh
from .repair_edges import repair
from .repair_reviews import review


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--levels',default='30,31')
    parser.add_argument('--keep-ownership',action='store_true')
    parser.add_argument('--all-captures',action='store_true')
    parser.add_argument('--samples',type=int,default=8)
    args=parser.parse_args();levels=list(map(int,args.levels.split(',')))
    with (RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for level in levels:
            root=Path('native-output')/f'level-{level}'
            selection=root/'ownership-sources.json'if args.all_captures else RUNTIME/f'effect-refresh-{level}.json'
            names=[r['capture']for r in json.loads(selection.read_text())]
            print(f'LEVEL {level}: recapturing {len(names)} geyser viewports',flush=True)
            archive=RUNTIME/'effect-v2-before'/f'level-{level}'
            refresh(root,names,archive,temporal_samples=args.samples,temporal_interval=1/24,
                    reason='Native geyser mesh litadd across particle-controller cleanup and restored templates; original animation and lighting retained')
            for name in names:
                state=json.loads((root/'captures'/f'{name}.json').read_text())
                assert state['geyser_blend_profile']=='loose_geyser_mesh_litadd_v2'
            print(f'LEVEL {level}: checking native pixel ownership and joins',flush=True)
            if not args.keep_ownership:quilt(root,full=False)
            report=audit(root,full=False)
            if report['acceptance']=='review_required':
                repair(root,iterations=4);recut(root,iterations=2);report=audit(root,full=False)
            if report['acceptance']=='review_required':
                if args.keep_ownership:
                    # Retain the Z-registered geometry bridge on level 39.
                    # Observe slow motion afresh without discarding its owners.
                    for attempt in range(2):
                        edge=json.loads((root/'edge-validation.json').read_text())
                        ids={i for row in edge['static_samples']for i in row['owners']if i}
                        sources=json.loads((root/'ownership-sources.json').read_text())
                        retry=[s['capture']for s in sources if s['id']in ids]
                        refresh(root,retry,archive/f'review-{attempt}',temporal_samples=32*(attempt+1),temporal_interval=.1,
                                reason='Observe slow native effects at remaining ownership joins while retaining registered geometry')
                        report=audit(root,full=False)
                        if report['acceptance']=='review_required':
                            repair(root,iterations=4);recut(root,iterations=2);report=audit(root,full=False)
                        if report['acceptance']!='review_required':break
                    if report['acceptance']=='review_required':raise RuntimeError(f'Level {level} still has unresolved joins')
                elif not review(root):raise RuntimeError(f'Level {level} still has unresolved joins')
            finalize(root)
            print(f'LEVEL {level}: corrected PNG complete',flush=True)
        dump(RUNTIME/('effect-repair-status-'+args.levels.replace(',','-')+'.json'),dict(levels=levels,complete=True,finished_at=time.time()))
        NativeGame().view(30,10536,10736,0)


if __name__=='__main__':main()
