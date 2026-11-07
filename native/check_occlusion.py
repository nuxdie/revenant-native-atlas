"""Verify that covering the Wine desktop cannot enter the captured map pixels."""
import json
import os
import subprocess
import time
import tkinter as tk

import numpy as np

from atlas import dump
from .game import NativeGame,ROOT
from .x11_capture import WindowCapture


def main():
    game=NativeGame()
    desktop=subprocess.check_output(['xdotool','search','--name','^RevenantAtlas - Wine Desktop$'],env=game.env,text=True).split()
    if len(desktop)!=1:raise RuntimeError('Cannot identify Wine desktop')
    geo=subprocess.check_output(['xdotool','getwindowgeometry','--shell',desktop[0]],env=game.env,text=True)
    data=dict(line.split('=',1)for line in geo.splitlines()if '='in line)
    before=game.info()
    window=tk.Tk(screenName=game.display)
    window.overrideredirect(True);window.configure(background='#ff00ff')
    window.geometry(f'640x480+{data["X"]}+{data["Y"]}')
    window.attributes('-topmost',True);window.update()
    try:
        window.after(2500,window.destroy)
        with game.backing_capture() as backing:
            with WindowCapture(window.winfo_id(),game.display) as overlay:
                visible=np.array(overlay.frame())
                source=np.array(backing.frame())
                overlay_magenta=np.all(visible==[255,0,255],axis=2).sum()
                source_magenta=np.all(source==[255,0,255],axis=2).sum()
                backing.frame().save(ROOT/'comparisons/occlusion-backing.png')
            for _ in range(15):window.update();time.sleep(.05)
        after=game.info()
    finally:
        try:window.destroy()
        except tk.TclError:pass
    report={'overlay_pixels':640*480,'overlay_magenta_pixels':int(overlay_magenta),
            'backing_magenta_pixels':int(source_magenta),
            'native_frame_advanced_while_covered':after['screen_frame']>before['screen_frame'],
            'result':'passed'if overlay_magenta==640*480 and source_magenta<1000 and after['screen_frame']>before['screen_frame']else'review_required'}
    dump(ROOT/'comparisons/occlusion-check.json',report);print(json.dumps(report,indent=2))

if __name__=='__main__':main()
