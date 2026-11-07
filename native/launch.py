"""Launch only the isolated original installation and initialize its map."""
import os
import subprocess
import time

from .game import NativeGame, RUNTIME, ROOT, build_control


def launch():
    game=NativeGame()
    try:
        return game.info()
    except (RuntimeError,subprocess.CalledProcessError):
        pass
    env=dict(game.env,WINEDLLOVERRIDES='ddraw=n,b;d3dimm=b',DXVK_LOG_PATH=str(RUNTIME))
    with (RUNTIME/'d7vk-start.log').open('ab') as log:
        subprocess.Popen([game.wine,os.environ.get('REVENANT_EXE',str(RUNTIME/'game/Revenant.exe')),'EDITOR','FASTLOCK=OFF',
                          'NOPRELOADSECTORS','CHUNKCACHESIZE=24'],env=env,cwd=ROOT,
                         stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    deadline=time.monotonic()+45
    while True:
        try:
            window=game.window();break
        except (RuntimeError,subprocess.CalledProcessError):
            if time.monotonic()>deadline:raise RuntimeError('Original game window did not open')
            time.sleep(.25)
    time.sleep(3)
    # The original executable presents its menu even with EDITOR supplied.
    game.command('@presentation')
    subprocess.run(['xdotool','windowraise',str(game.desktop_window()),'windowactivate','--sync',
                    str(game.desktop_window())],env=env,check=True,timeout=5)
    subprocess.run(['xdotool','mousemove','--window',str(window),'420','163','click','1'],env=env,check=True,timeout=3)
    deadline=time.monotonic()+60
    while True:
        state=game.info()
        if state['current_screen']==0x624bf8:
            break
        if time.monotonic()>deadline:raise RuntimeError('New-game menu did not enter the play screen')
        time.sleep(.5)
    if not state['editor']:game.command('@editor')
    game.command('@helpers-off');game.command('@presentation');game.command('@grid')
    game.command('mono 0');game.command('@wait')
    return game.info()

if __name__=='__main__':
    build_control()
    print(launch())
