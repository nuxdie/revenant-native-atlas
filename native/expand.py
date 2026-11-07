"""Extend a native capture plan from corrected placements and nonblack edges."""
import argparse
import json
from pathlib import Path
from atlas import dump
from .plan import create_plan


def expanded(root,baseline):
    plan=json.loads((root/'plan.json').read_text())
    coords=set(map(tuple,plan['cores']));before=len(coords)
    if (baseline/f'level-{plan["level"]}/manifest.json').exists():
        corrected=create_plan(baseline,'runtime/game',plan['level'])
        coords.update(map(tuple,corrected['cores']))
    frontier=root/'frontier.json'
    if frontier.exists():
        coords.update(tuple(f['unplanned_neighbor'])for f in json.loads(frontier.read_text()))
    rows={}
    for x,y in coords:rows.setdefault(y,[]).append(x)
    plan['cores']=[[x,y]for i,y in enumerate(sorted(rows))for x in sorted(rows[y],reverse=bool(i%2))]
    bounds=[min(x for x,y in coords)*512,min(y for x,y in coords)*256,
            (max(x for x,y in coords)+1)*512,(max(y for x,y in coords)+1)*256]
    plan.update(bounds=bounds,width=bounds[2]-bounds[0],height=bounds[3]-bounds[1],core_count=len(coords))
    return plan,len(coords)-before


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--baseline',type=Path,default=Path('output-corrected'))
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    plan,added=expanded(a.directory,a.baseline);dump(a.out,plan)
    print(f'{added} additional views; {plan["core_count"]} total, {plan["width"]} × {plan["height"]}')

if __name__=='__main__':main()
