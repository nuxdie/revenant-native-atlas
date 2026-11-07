"""Compare original-game saved tile coordinates with the shipped sector data."""
from collections import Counter
import json
from pathlib import Path

from atlas import dump, sector_position
from .game import RUNTIME, ROOT
from .plan import positions


def main():
    checks=[]
    base=RUNTIME/'game/Modules/Ahkuilon/Map'
    files={p.stem.lower():p for p in base.glob('*') if p.suffix.lower()=='.dat'}
    for saved in sorted((RUNTIME/'game/Curmap').glob('0_*.DAT')):
        source=files.get(saved.stem.lower())
        if not source:continue
        actual=Counter((o['class'],o['uid'],*o['pos']) for o in positions(saved) if o['class']==9)
        expected=Counter((o['class'],o['uid'],*sector_position(source,*o['pos'])) for o in positions(source) if o['class']==9)
        checks.append({'sector':saved.stem,'source_tiles':sum(expected.values()),
                       'native_tiles':sum(actual.values()),'matched':sum((actual&expected).values())})
    report={'method':'shipped source coordinates versus coordinates saved by the running original executable',
            'matched_tiles':sum(c['matched'] for c in checks),
            'source_tiles':sum(c['source_tiles'] for c in checks),'sectors':checks}
    dump(ROOT/'comparisons/sector-position-proof.json',report)
    print(json.dumps({k:v for k,v in report.items()if k!='sectors'},indent=2))

if __name__=='__main__':main()
