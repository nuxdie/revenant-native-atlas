"""A/B the native shadow correction, retaining direct frames and pixel deltas."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image,ImageFilter

from atlas import dump
from .game import NativeGame
from .live import export_running


def check(camera,out,region=None):
    if export_running():raise RuntimeError('Wait for the native export before moving the camera')
    out.mkdir(parents=True,exist_ok=True);g=NativeGame()
    g.command('@presentation');g.command('@normal');g.view(*camera)
    arrays={};states={}
    try:
        for name,command in [('before','@blend-off'),('after','@blend-fix')]:
            g.command('@wait');g.command(command);g.command('mono 0');g.command('@wait')
            deadline=time.monotonic()+10
            while g.info()['ambient_fade_frames']:
                if time.monotonic()>deadline:raise RuntimeError('Ambient fade did not finish')
                time.sleep(.05)
            states[name]=g.info();frames=[]
            with g.backing_capture()as cap:
                for _ in range(32):
                    frames.append(np.array(cap.frame().crop((0,0,640,340))));time.sleep(1/24)
            arrays[name]=np.stack(frames)
            Image.fromarray(frames[0]).save(out/f'validated-{name}.png')
    finally:
        g.command('@blend-fix');g.command('mono 0');g.command('@wait')
    a,b=arrays['before'][0],arrays['after'][0]
    dynamic=np.any(arrays['before']!=a,axis=(0,3))|np.any(arrays['after']!=b,axis=(0,3))
    dynamic=np.array(Image.fromarray(dynamic.astype('uint8')*255).filter(ImageFilter.MaxFilter(17)))>0
    changed=np.any(a!=b,axis=2)&~dynamic
    expected=np.zeros((340,640),bool)
    if region:
        x0,y0,x1,y1=region;expected[y0:y1,x0:x1]=True
    ys,xs=np.where(changed)
    report=dict(states=states,changed_static_pixels=int(changed.sum()),
                changed_static_bounds=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]if len(xs)else None,
                outside_shadow_region=int((changed&~expected).sum()),measured_animation_pixels=int(dynamic.sum()),
                shadow_region=region,method='32 native frames per mode; union of measured animation differences with 8px margin',
                root_cause='RGB565 Alpha at 0x495160 receives an ARGB1555 destination (0x20000) and RGB565/alpha source (0x104).')
    dump(out/'fix-validation.json',report)
    if region:
        x0,y0,x1,y1=region
        detail=np.concatenate((a[y0:y1,x0:x1],b[y0:y1,x0:x1]),axis=1)
        Image.fromarray(detail).resize((detail.shape[1]*4,detail.shape[0]*4),Image.Resampling.NEAREST).save(out/'fixed-detail.png')
    if report['outside_shadow_region']:raise ValueError(f'Correction changes unexplained static pixels: {report}')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--camera',nargs=4,type=int,default=[0,2012,27407,0])
    p.add_argument('--region',nargs=4,type=int);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(check(a.camera,a.out,a.region),indent=2))
