"""Retire captures which may contain 3D editor helpers, using source bounds."""
import argparse
import json
from pathlib import Path
import shutil
from collections import Counter

from atlas import CLASSES,parse_types,project,sector_position,dump
from .plan import positions


def repair(root,destination,padding=256):
    types=parse_types(Path('runtime/game/Resources/class.def'))
    markers=[];classes=Counter()
    for path in Path('runtime/game/Modules/Ahkuilon/Map').glob(f'{root.name.split("-")[1]}_*'):
        for obj in positions(path):
            if obj['class']!=15 and not obj['flags']&(128|256):continue
            info=types.get((CLASSES.get(obj['class']),obj['uid']))
            if obj['class']!=15 and (not info or not info['path'].lower().endswith('.i3d')):continue
            sx,sy,_=project(*sector_position(path,*obj['pos']))
            markers.append((sx,sy));classes[str(obj['class'])]+=1
    moved=[];retained=0
    for meta in list((root/'captures').glob('*.json')):
        state=json.loads(meta.read_text())
        if state.get('visibility_profile')=='gameplay_2d_and_3d':continue
        x,y=state['scroll']
        # Shipped Waypoint and MonsterGen imagery headers are 63×85 and
        # 73×98; the larger margin also covers their native 3D registration.
        dirty=any(x-padding<=sx<=x+640+padding and y-padding-256<=sy<=y+340+padding for sx,sy in markers)
        if dirty:
            for folder,suffix in [('captures','.json'),('captures','.png'),('temporal','.png')]:
                source=root/folder/(meta.stem+suffix)
                if source.exists():
                    target=destination/folder/source.name;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.move(source,target)
            moved.append(meta.stem)
        else:
            state['visibility_validation']='no 3D helper/editor/invisible source object inside conservatively padded viewport'
            state['visibility_padding_pixels']=padding
            dump(meta,state);retained+=1
    report={'retired_captures':moved,'retired_count':len(moved),'retained_outside_marker_bounds':retained,
            'source_markers':len(markers),'source_classes':dict(classes),'padding_pixels':padding}
    dump(destination/'repair.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--quarantine',type=Path,required=True);a=p.parse_args()
    r=repair(a.directory,a.quarantine)
    print(json.dumps({k:v for k,v in r.items()if k!='retired_captures'},indent=2))

if __name__=='__main__':main()
