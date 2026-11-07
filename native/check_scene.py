"""Compare a fresh original-game viewport with its registered exported crop."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image,ImageFilter

from atlas import dump
from fidelity import compare
from .game import NativeGame
from .live import export_running


def crop(root,meta,scroll,directory='tiles',mode='RGB'):
    left,top=scroll[0]-meta['bounds'][0],scroll[1]-meta['bounds'][1]
    result=Image.new(mode,(640,340));size=meta['tile_size']
    for ty in range(top//size,(top+339)//size+1):
        for tx in range(left//size,(left+639)//size+1):
            path=root/directory/f'{tx}_{ty}.png'
            if path.exists():
                with Image.open(path)as im:result.paste(im.convert(mode),(tx*size-left,ty*size-top))
    return result


def check(root,level,x,y,z,out):
    meta=json.loads((root/'manifest.json').read_text())
    retail=meta.get('provider')=='original_retail_1.22L'
    if not retail and export_running():raise RuntimeError('Wait for the map export before moving its camera')
    out.mkdir(parents=True,exist_ok=True)
    if retail:
        from .retail import RetailGame
        game=RetailGame();game.capture_lighting=meta.get('lighting_profile');game.command('@presentation');game.command('@helpers-off')
        game.mount(meta['module'])
        game.command('@grid');game.command(f'@time {meta["time_of_day_minutes"]}')
    else:
        game=NativeGame();game.command('@presentation');game.command('@normal')
    game.view(level,x,y,z);game.command('mono 0');game.command('@wait')
    state=game.prepare_capture()if retail else game.info();samples=[]
    deadline=time.monotonic()+10
    while state.get('ambient_fade_frames',0):
        if time.monotonic()>deadline:raise RuntimeError('Original ambient transition did not settle')
        game.command('@wait');state=game.info()
    count,interval=(32,.1)if retail else(16,1/24)
    with game.backing_capture()as capture:
        start=time.monotonic()
        for frame in range(count):
            time.sleep(max(0,start+frame*interval-time.monotonic()))
            samples.append(np.array(capture.frame().crop((0,0,640,340))))
    end=game.info()
    if end['screen_frame']<=state['screen_frame']:raise RuntimeError('Game renderer did not advance during comparison')
    if end['camera']!=state['camera']:raise RuntimeError('Game camera changed during comparison')
    reference=Image.fromarray(samples[0]);reference.save(out/'original-game.png')
    candidate=crop(root,meta,state['scroll']);candidate.save(out/'export.png')
    changing=np.any(np.stack(samples)!=samples[0],axis=(0,3))
    if meta.get('ownership'):
        owners=np.array(crop(root,meta,state['scroll'],'ownership','I'))
        sources={s['id']:s for s in json.loads((root/'ownership-sources.json').read_text())}
        for ident in np.unique(owners):
            if ident==0:continue
            source=sources[int(ident)]
            with Image.open(root/'temporal'/f'{source["capture"]}.png')as im:mask=np.array(im)>0
            yy,xx=np.where(owners==ident)
            sx=state['scroll'][0]+xx-source['scroll'][0]
            sy=state['scroll'][1]+yy-source['scroll'][1]
            changing[yy,xx]|=mask[sy,sx]
    changing=np.array(Image.fromarray(changing.astype('uint8')*255).filter(ImageFilter.MaxFilter(17)))>0
    a=np.array(reference);b=np.array(candidate)
    foreground=np.any(a,axis=2)|np.any(b,axis=2)
    valid=foreground&~changing
    Image.fromarray(valid.astype('uint8')*255).save(out/'static-foreground-mask.png')
    all_report=compare(out/'original-game.png',out/'export.png',out/'all-pixels')
    static_report=compare(out/'original-game.png',out/'export.png',out/'static-foreground',mask=out/'static-foreground-mask.png')
    record=dict(state,viewport=[640,340],reference_provider='fresh original executable output',
                temporal_samples=count,temporal_seconds=(count-1)*interval,
                capture_end_screen_frame=end['screen_frame'],
                comparison_mask='nonblack union; measured reference changes and source export masks combined, then dilated by 8 pixels (export masks already have an 8-pixel margin)',
                excluded_black_pixels=int((~foreground).sum()),measured_temporal_pixels=int(changing.sum()),
                foreground_static_comparison=static_report,all_pixel_comparison=all_report)
    dump(out/'capture.json',record)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--camera',nargs=4,type=int,required=True)
    p.add_argument('--atlas',type=Path,default=Path('native-output'));p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();root=a.atlas/f'level-{a.camera[0]}'
    if json.loads((root/'manifest.json').read_text()).get('provider')=='original_retail_1.22L':
        from .retail import RUNTIME
    else:
        from .game import RUNTIME
    import fcntl
    with(RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        record=check(root,*a.camera,a.out)
    print(json.dumps(record['foreground_static_comparison'],indent=2))

if __name__=='__main__':main()
