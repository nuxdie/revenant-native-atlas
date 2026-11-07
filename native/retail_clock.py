"""Original retail light states for an hourly clock; capture twilight natively."""
import argparse
import fcntl
import json
from pathlib import Path
import re
from zipfile import ZipFile

from atlas import dump
from .retail import DATA,ROOT,RUNTIME


def daylight(minute,twilight=60):
    if not isinstance(minute,int)or not 0<=minute<1440:raise ValueError('Minute must be 0–1439')
    if not 1<=twilight<=720:raise ValueError('Invalid twilight duration')
    morning=360-twilight//2;evening=1080-twilight//2
    if minute<morning or minute>evening+twilight-1:return 0
    if morning+twilight-1<minute<evening:return 255
    into=minute-morning if minute<=morning+twilight-1 else twilight-(minute-evening)
    return into*255//twilight


def state_for_hour(hour,twilight=60):
    if not isinstance(hour,int)or not 0<=hour<24:raise ValueError('Hour must be 0–23')
    value=daylight(hour*60,twilight)
    return 'night'if value==0 else'day'if value==255 else'twilight'


def profile_for_minute(plan,minute,twilight=60):
    light=daylight(minute,twilight);day=plan['lighting_profiles']['day'];night=plan['lighting_profiles']['night']
    def mix(a,b):return a*light//255+b*(255-light)//255
    ambient=mix(day['ambient'],night['ambient'])
    return dict(policy='authored_setter_gamma3_v1',ambient=ambient,
        ambient_rgb=[mix(a,b)for a,b in zip(day['ambient_rgb'],night['ambient_rgb'])],
        expected_native_ambient=ambient+10,daylight=light)


def clock_metadata(twilight=60):
    return dict(step_minutes=60,twilight_minutes=twilight,
        hours=[dict(hour=h,variant=state_for_hour(h,twilight))for h in range(24)],
        scope='Original authored lighting at whole hours; gameplay and animation phases are not synchronized')


def rules_twilight(data=DATA):
    with ZipFile(data/'resources.rvr')as z:
        name=next(n for n in z.namelist()if n.casefold()=='rules.def')
        match=re.search(r'^\s*TWILIGHT\s+(\d+)\s*,',z.read(name).decode('cp1252'),re.M|re.I)
    if not match:raise ValueError('Missing native twilight rule')
    return int(match[1])


def plan_twilight(plan,twilight=60):
    if 'day'not in plan.get('variants',[])or'night'not in plan['variants']:raise ValueError('This location has no authored day/night cycle')
    profile=profile_for_minute(plan,360,twilight)
    if profile!=profile_for_minute(plan,1080,twilight):raise ValueError('Dawn and dusk need separate native states')
    return dict(plan,variants=['twilight'],time_of_day_minutes=360,
        lighting_profiles={'twilight':profile},clock=clock_metadata(twilight))


def prepare_dataset(index,out):
    dataset=json.loads((index/'dataset.json').read_text());duration=rules_twilight()
    plans=[plan_twilight(json.loads((index/'plans'/f'level-{row["level"]}.json').read_text()),duration)
        for row in dataset['levels']if'day'in row.get('variants',[])and'night'in row['variants']]
    result={**dataset,'levels':[{k:v for k,v in p.items()if k!='cores'}for p in plans],
        'expected_levels':len(plans),'expected_maps':len(plans),'unresolved_types':[]}
    dump(out/'dataset.json',result);return plans


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--level',type=int,required=True)
    p.add_argument('--index',type=Path,default=ROOT/'runtime/retail-index')
    p.add_argument('--out',type=Path,default=ROOT/'retail-clock-output');a=p.parse_args()
    from .retail_batch import restart
    from .retail_export import capture
    from .retail_finish import finish
    plans=prepare_dataset(a.index,a.out);plan=next((p for p in plans if p['level']==a.level),None)
    if plan is None:raise ValueError('Selected location has no authored day/night cycle')
    with(RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);restart();capture(plan,'twilight',a.out,rebuild_held=True)
    finish({a.level},a.out)
