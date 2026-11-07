"""Resume an isolated native retail batch after a renderer/driver failure."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from atlas import dump
from .retail import DATA,DESKTOP,ROOT,RUNTIME,RetailGame
from .retail_instance import silent_sink


def restart():
    game=RetailGame()  # Verify the executable before touching this prefix.
    env=dict(game.env,WINEDLLOVERRIDES='ddraw=n,b;d3dimm=b',DXVK_LOG_PATH=str(RUNTIME))
    sink=silent_sink()
    if sink:env.update(PULSE_SINK=sink,REVENANT_AUDIO_SINK=sink)
    server=str(Path(game.wine).with_name('wineserver'))
    for option in ('-k','-w'):
        result=subprocess.run([server,option],env=env,timeout=30)
        # wineserver returns 1 when this private prefix has no server yet.
        if result.returncode not in(0,1):result.check_returncode()
    (RUNTIME/'control-server.pid').unlink(missing_ok=True)
    with(RUNTIME/'launch.log').open('ab')as log:
        process=subprocess.Popen([game.wine,'explorer',f'/desktop={DESKTOP},640x480',
            'G:\\Revenant.exe','EDITOR','FASTLOCK=OFF','NOPRELOADSECTORS','CHUNKCACHESIZE=24'],
            cwd=DATA,env=env,stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        try:
            state=game.info()
            if state['editor']and state['current_screen']==0x65caf0 and state['screen_frame']>0:
                game.command('@presentation');game.command('@wait')
                print('Original retail renderer restarted',process.pid,flush=True)
                return env
        except RuntimeError:
            pass
        time.sleep(.5)
    raise RuntimeError('Isolated retail renderer did not initialize')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--levels',required=True);p.add_argument('--retries',type=int,default=3)
    p.add_argument('--index',type=Path,default=ROOT/'runtime/retail-index')
    p.add_argument('--out',type=Path,default=ROOT/'retail-output')
    a=p.parse_args();selected=set(map(int,a.levels.split(',')))
    (RUNTIME/'batch.pid').write_text(str(os.getpid()))
    dataset=json.loads((a.index/'dataset.json').read_text())
    broken={r['level']for r in dataset.get('unresolved_types',[])if r['native_load'].startswith('fatal')}
    held=sorted(selected&broken);selected-=broken
    if held:print('HELD: native loader cannot resolve legacy types on levels',held,flush=True)
    dump(RUNTIME/'batch-status.json',dict(state='running',held_levels=held,levels=sorted(selected)))
    if not selected:
        dump(RUNTIME/'batch-status.json',dict(state='held',held_levels=held))
        sys.exit(0)
    for attempt in range(a.retries+1):
        try:
            env=restart()
            subprocess.run([sys.executable,'-m','native.retail_export','--levels',','.join(map(str,sorted(selected))),
                '--index',str(a.index),'--out',str(a.out)],cwd=ROOT,env=env,check=True)
            dump(RUNTIME/'batch-status.json',dict(state='captures_finished',held_levels=held,
                note='Inspect validation.json for held joins; a finished batch is not publication acceptance.'))
            break
        except(subprocess.SubprocessError,RuntimeError)as exc:
            print(f'Native retry {attempt+1}/{a.retries+1}: {exc}',flush=True)
            if attempt==a.retries:
                dump(RUNTIME/'batch-status.json',dict(state='failed',held_levels=held,error=str(exc)))
                raise
