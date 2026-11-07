"""Prepare and launch a private retail capture copy without editing the source install."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from .retail import EXE_SHA256, ROOT


def silent_sink():
    """Use a dedicated muted output, leaving the user's normal audio untouched."""
    if not shutil.which('pactl'):
        return None
    name='revenant_atlas_silent'
    try:
        sinks=json.loads(subprocess.check_output(['pactl','-f','json','list','sinks'],stderr=subprocess.DEVNULL))
        if not any(s['name']==name for s in sinks):
            subprocess.run(['pactl','load-module','module-null-sink',f'sink_name={name}',
                'sink_properties=device.description=RevenantAtlasSilent'],check=True,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['pactl','set-sink-mute',name,'1'],check=True,stderr=subprocess.DEVNULL)
        return name
    except (OSError,ValueError,subprocess.SubprocessError):
        return None


def prepare(data,runtime,desktop,wine,ddraw,ini=None,prefix_template=None):
    data,runtime,ddraw=map(lambda p:Path(p).resolve(),(data,runtime,ddraw))
    files={p.name.casefold():p for p in data.iterdir()}
    if hashlib.sha256(files['revenant.exe'].read_bytes()).hexdigest()!=EXE_SHA256:
        raise ValueError('This controller supports the pinned English GOG 1.22L executable only')
    for name in ['resources.rvr','imagery.rvi','modules']:
        if name not in files:raise ValueError(f'Missing retail content: {name}')
    runtime.mkdir(parents=True,exist_ok=True);game=runtime/'game';game.mkdir(exist_ok=True)
    ignored={'curmap','save','revenant.ini','revboot.log','tmp','app','commonappdata','ddraw.dll'}
    for source in data.iterdir():
        if source.name.casefold()in ignored or source.suffix.casefold()=='.log':continue
        target=game/source.name
        if not target.exists():target.symlink_to(source,target_is_directory=source.is_dir())
    if ini is None:
        ini=files.get('revenant.ini')or(data/'__support/app/revenant.ini')
    ini=Path(ini)
    if not ini.is_file():raise ValueError('Supply the retail Revenant.ini with --ini')
    config=configparser.ConfigParser(interpolation=None,strict=False);config.optionxform=str
    config.read(ini,encoding='cp1252')
    if not config.has_section('Options'):config.add_section('Options')
    for key,value in dict(RealTimeLight='Yes',Software3D='No',GammaLevel='3',PlaySpeech='No',
                           PlayMusic='No',ShortEditorDisplay='No',WaitMapUpdate='No').items():
        config.set('Options',key,value)
    with(game/'Revenant.ini').open('w')as stream:config.write(stream)
    for name in ['Curmap','Save']:(game/name).mkdir(exist_ok=True)
    target=game/'DDraw.dll'
    if not target.exists():shutil.copy2(ddraw,target)
    elif hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(ddraw.read_bytes()).digest():
        raise ValueError('Capture copy already has a different D7VK DLL')
    env=dict(os.environ,DISPLAY=os.environ.get('DISPLAY',':0'),WINEPREFIX=str(runtime/'prefix'),
        WINEDEBUG='-all',WINEDLLOVERRIDES='ddraw=n,b;d3dimm=b',DXVK_LOG_PATH=str(runtime),
        REVENANT_RETAIL_RUNTIME=str(runtime),REVENANT_RETAIL_DATA=str(game),REVENANT_RETAIL_DESKTOP=desktop)
    sink=silent_sink()
    if sink:env.update(PULSE_SINK=sink,REVENANT_AUDIO_SINK=sink)
    prefix=runtime/'prefix'
    new_prefix=not prefix.exists()
    if new_prefix:
        if prefix_template:shutil.copytree(prefix_template,prefix,symlinks=True)
        else:subprocess.run([str(wine),'wineboot','--init'],env=env,check=True)
    drive=prefix/'dosdevices/g:'
    if drive.is_symlink()and drive.resolve()!=game:
        if new_prefix:drive.unlink()
        else:raise ValueError('Private prefix G: points elsewhere')
    if not drive.exists():drive.symlink_to(game,target_is_directory=True)
    for key,name,value in [('HKCU\\Software\\Wine\\Explorer','Desktop',desktop),
        ('HKCU\\Software\\Wine\\Explorer\\Desktops',desktop,'640x480')]:
        subprocess.run([str(wine),'reg','add',key,'/v',name,'/d',value,'/f'],env=env,check=True,
            stdout=subprocess.DEVNULL)
    record=dict(runtime=str(runtime),data=str(game),desktop=desktop,source_data=str(data),
        executable_sha256=EXE_SHA256,ddraw_sha256=hashlib.sha256(ddraw.read_bytes()).hexdigest(),audio_sink=sink)
    (runtime/'instance.json').write_text(json.dumps(record,indent=2)+'\n')
    return record,env


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--runtime',type=Path,default=ROOT/'runtime/retail')
    p.add_argument('--desktop',default='RevenantRetail')
    p.add_argument('--wine',type=Path,required=True)
    p.add_argument('--ddraw',type=Path,required=True,help='32-bit D7VK DDraw.dll')
    p.add_argument('--ini',type=Path);p.add_argument('--prefix-template',type=Path)
    p.add_argument('--launch',action='store_true')
    a=p.parse_args();record,env=prepare(a.data,a.runtime,a.desktop,a.wine,a.ddraw,a.ini,a.prefix_template)
    print(json.dumps(record,indent=2))
    if a.launch:
        with(Path(record['runtime'])/'launch.log').open('ab')as log:
            process=subprocess.Popen([str(a.wine),'explorer',f'/desktop={a.desktop},640x480',
                'G:\\Revenant.exe','EDITOR','FASTLOCK=OFF','NOPRELOADSECTORS','CHUNKCACHESIZE=24'],
                env=env,cwd=record['data'],stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
        print('Started isolated editor:',process.pid)
