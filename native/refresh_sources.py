"""Replace selected native frames and refresh their existing owned pixels."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image

from atlas import dump
from .export import capture_core
from .game import NativeGame,RUNTIME


def refresh(root,names,archive,temporal_samples=3,temporal_interval=1/24,reason='replace stale shoreline band candidates using current native renderer'):
    meta=json.loads((root/'manifest.json').read_text())
    sources=json.loads((root/'ownership-sources.json').read_text())
    selected={s['capture']:s for s in sources if s['capture']in names}
    if set(names)!=set(selected):raise ValueError('Requested capture is not in the ownership index')
    retail=meta.get('provider')=='original_retail_1.22L'
    if retail:
        from .retail import RetailGame
        game=RetailGame()
        game.command('@presentation');game.command('@helpers-off')
        game.command(f'setcurmodule "{meta["module"]}"');game.command('@wait')
        game.command(f'@time {meta["time_of_day_minutes"]}')
    else:
        game=NativeGame();game.command('@presentation');game.command('@normal');game.command('@time 487')
    game.export_level=meta['level'];game.command('@grid')
    changed={};records=[]
    try:
        with game.backing_capture()as capture:
            for name in sorted(selected,key=lambda s:tuple(reversed(tuple(map(int,s.split('_')))))):
                old=root/'captures'/f'{name}.png';previous=json.loads(old.with_suffix('.json').read_text())
                first,array,dynamic,state=capture_core(game,capture,list(map(int,name.split('_'))),.1,temporal_samples,temporal_interval)
                for folder,suffix in [('captures','.png'),('captures','.json'),('temporal','.png')]:
                    source=root/folder/(name+suffix);target=archive/folder/source.name
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.exists():shutil.copy2(source,target)
                if retail and (state['time_of_day_minutes']!=meta['time_of_day_minutes'] or state['visibility_profile']!='gameplay_2d_and_3d'):
                    raise RuntimeError('Retail refresh changed lighting or helper visibility')
                state.update(core=list(map(int,name.split('_'))),captured_at=time.time(),crop=[64,42,576,298],
                             capture_recipe='retail_redraw_bg_barrier_v2'if retail else'console_redraw_bg_barrier_v3',
                             provider='original_retail_1.22L'if retail else'original_game',
                             temporal_samples=temporal_samples,temporal_sample_interval_seconds=temporal_interval,temporal_margin_pixels=8,
                             recapture_reason=reason,
                             previous_source_png_sha256=previous['source_png_sha256'])
                if retail:state.update(module=meta['module'],variant=meta['variant'])
                temporary=old.with_suffix('.png.tmp');first.save(temporary,format='PNG',compress_level=3);temporary.replace(old)
                state['source_png_sha256']=hashlib.sha256(old.read_bytes()).hexdigest();dump(old.with_suffix('.json'),state)
                Image.fromarray(dynamic.astype('uint8')*255).save(root/'temporal'/old.name)
                source=selected[name];source['sha256']=state['source_png_sha256'];changed[source['id']]=(source,array)
                records.append(dict(capture=name,before=previous['source_png_sha256'],after=state['source_png_sha256']))
                if len(records)%20==0:print(f'Recaptured {len(records)}/{len(selected)}',flush=True)
    finally:
        if not retail:game.command('@normal')
    left,top=meta['bounds'][:2];updated=0;modified=[]
    for tx,ty in meta['tiles']:
        path=root/'tiles'/f'{tx}_{ty}.png'
        with Image.open(root/'ownership'/path.name)as im:owners=np.array(im)
        ids=set(map(int,np.unique(owners)))&changed.keys()
        if not ids:continue
        with Image.open(path)as im:rgb=np.array(im.convert('RGB'))
        for ident in ids:
            source,frame=changed[ident];yy,xx=np.where(owners==ident)
            sx=left+tx*1024+xx-source['scroll'][0];sy=top+ty*1024+yy-source['scroll'][1]
            rgb[yy,xx]=frame[sy,sx];updated+=len(xx)
        temporary=path.with_suffix('.png.tmp');Image.fromarray(rgb).save(temporary,format='PNG',compress_level=4);temporary.replace(path)
        modified.append([tx,ty])
    dump(root/'ownership-sources.json',sources)
    # Overview previews are allowed to resample; native tiles remain exact.
    scale=min(1,4096/max(meta['width'],meta['height']))
    preview=Image.open(root/'overview.jpg').convert('RGB')
    for tx,ty in modified:
        with Image.open(root/'tiles'/f'{tx}_{ty}.png')as im:
            x,y=round(tx*1024*scale),round(ty*1024*scale)
            right,bottom=round((tx*1024+im.width)*scale),round((ty*1024+im.height)*scale)
            preview.paste(im.resize((right-x,bottom-y),Image.Resampling.LANCZOS),(x,y))
    preview.save(root/'overview.jpg',quality=94,subsampling=0)
    record=dict(captures=records,replaced_captures=len(records),refreshed_owned_pixels=updated,modified_tiles=modified,
                method='Complete native frame recapture; existing owned pixels re-read from their registered source. No pixel synthesis or colour editing.')
    dump(root/'source-refresh.json',record)
    meta['source_refresh']='source-refresh.json';dump(root/'manifest.json',meta)
    print(json.dumps({k:v for k,v in record.items()if k not in ('captures','modified_tiles')},indent=2),flush=True)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--candidates',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
    import fcntl
    with (RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        refresh(a.directory,[r['capture']for r in json.loads(a.candidates.read_text())],a.archive)
