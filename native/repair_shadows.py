"""Recapture source-bounded alpha-shadow regions after the format correction."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from atlas import CLASSES,Game,dump,project,sector_position
from .plan import positions


def repair(root,destination,padding=256):
    game=Game('runtime/game');level=int(root.name.split('-')[1])
    shadow_names={t['name'].casefold()for (cls,uid),t in game.types.items()if cls=='SHADOW'}
    points=set();classes=Counter()
    for folder in (game.path/'Modules/Ahkuilon/Map',game.path/'Curmap'):
        for sector in folder.rglob(f'{level}_*.dat'):
            for obj in positions(sector):
                typ=game.types.get((CLASSES.get(obj['class']),obj['uid']))
                if typ is None:
                    candidates=[t for (cls,uid),t in game.types.items()if uid==obj['uid']]
                    if len(candidates)==1:typ=candidates[0]
                if obj['class']!=14 and (not typ or 'shadow_'+typ['name'].casefold()not in shadow_names):continue
                sx,sy,_=project(*sector_position(sector,*obj['pos']))
                points.add((sx,sy));classes[str(obj['class'])]+=1
    moved=[];retained=0
    for path in sorted((root/'captures').glob('*.json')):
        state=json.loads(path.read_text())
        if state.get('shadow_blend_profile')=='rgb565_black_alpha_to_argb1555_v1':continue
        x,y=state['scroll']
        dirty=any(x-padding<=sx<=x+640+padding and y-padding-256<=sy<=y+340+padding for sx,sy in points)
        if dirty:
            for folder,suffix in [('captures','.json'),('captures','.png'),('temporal','.png')]:
                source=root/folder/(path.stem+suffix)
                if source.exists():
                    target=destination/folder/source.name;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.move(source,target)
            moved.append(path.stem)
        else:
            state['shadow_blend_validation']='outside conservative source and saved-runtime shadow bounds'
            state['shadow_blend_padding_pixels']=padding
            dump(path,state);retained+=1
    report=dict(level=level,retired_captures=moved,retired_count=len(moved),retained_outside_shadow_bounds=retained,
                source_shadow_positions=sorted(points),source_classes=dict(classes),padding_pixels=padding,
                correction='RGB565 black alpha -> ARGB1555, preserve destination coverage and native 15-bit rounding')
    dump(destination/'repair.json',report)
    dump(root/'shadow-repair.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--quarantine',type=Path,required=True);a=p.parse_args()
    r=repair(a.directory,a.quarantine)
    print(json.dumps({k:v for k,v in r.items()if k not in ('retired_captures','source_shadow_positions')},indent=2))
