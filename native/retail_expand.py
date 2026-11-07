"""Capture missing native coverage; retain a finite crop of authored backgrounds."""
import json
from pathlib import Path
from zipfile import ZipFile
from .retail import DATA
from .retail_dataset import parse_areas
from .retail_export import capture


def expanded_plan(root):
    plan=json.loads((root/'plan.json').read_text());coords=set(map(tuple,plan['cores']));before=len(coords)
    with ZipFile(DATA/'Modules'/f'{plan["module"]}.rvm')as archive:
        name=next(n for n in archive.namelist()if n.casefold()=='area.def')
        areas=parse_areas(archive.read(name).decode('cp1252'))
    effects=sorted({a['background_effect']for a in areas if a['level']==plan['level']and a['background_effect']})
    if effects:
        left,top,right,bottom=plan['bounds']
        coords.update((x,y)for y in range(top//256,bottom//256)for x in range(left//512,right//512))
        plan.update(background_effects=effects,background_crop=True,
            background_crop_scope='Finite object-placement bounds with original 512–1024 pixel padding; native background continues beyond the image')
    else:
        frontier=root/'frontier.json'
        if frontier.exists():coords.update(tuple(f['unplanned_neighbor'])for f in json.loads(frontier.read_text()))
    rows={}
    for x,y in coords:rows.setdefault(y,[]).append(x)
    plan['cores']=[[x,y]for i,y in enumerate(sorted(rows))for x in sorted(rows[y],reverse=bool(i%2))]
    bounds=[min(x for x,y in coords)*512,min(y for x,y in coords)*256,
        (max(x for x,y in coords)+1)*512,(max(y for x,y in coords)+1)*256]
    plan.update(bounds=bounds,width=bounds[2]-bounds[0],height=bounds[3]-bounds[1],core_count=len(coords))
    return plan,len(coords)-before


def expand(root):
    plan,added=expanded_plan(root)
    if not added and json.loads((root/'plan.json').read_text()).get('background_crop')==plan.get('background_crop'):
        return False
    print(f'{root}: {added} additional native views; background crop {plan.get("background_effects",[])}',flush=True)
    return capture(plan,plan['variant'],root.parent.parent,rebuild_held=True)
