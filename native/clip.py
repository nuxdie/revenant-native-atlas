"""Record a lossless animated PNG from a stationary original-game camera."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from atlas import dump
from .game import NativeGame
from .live import export_running


def record(level, x, y, z, out, seconds=4, fps=24,retail_meta=None):
    if not retail_meta and export_running():
        raise RuntimeError('Wait for the island export before moving the camera')
    out.mkdir(parents=True, exist_ok=True)
    if retail_meta:
        from .retail import RetailGame
        game=RetailGame();game.capture_lighting=retail_meta.get('lighting_profile');game.command('@presentation');game.command('@helpers-off')
        game.mount(retail_meta['module'])
        game.command('@grid');game.command(f'@time {retail_meta["time_of_day_minutes"]}')
    else:
        game = NativeGame();game.command('@presentation');game.command('@normal')
    game.view(level, x, y, z)
    game.command('mono 0')
    game.command('@wait')
    initial=game.prepare_capture()if retail_meta else game.info()
    deadline=time.monotonic()+10
    while initial.get('ambient_fade_frames',0):
        if time.monotonic()>deadline:raise RuntimeError('Original ambient transition did not settle')
        game.command('@wait');initial=game.info()
    frames, records = [], []
    start = time.monotonic()
    with game.backing_capture() as capture:
        for i in range(round(seconds*fps)):
            time.sleep(max(0, start+i/fps-time.monotonic()))
            image = capture.frame().crop((0,0,640,340))
            frames.append(image)
            records.append({'frame':i, 'elapsed_seconds':time.monotonic()-start,
                            'rgb_sha256':hashlib.sha256(image.tobytes()).hexdigest()})
    final=game.info()
    if final['screen_frame']<=initial['screen_frame']:raise RuntimeError('Game renderer did not advance while recording')
    if final['camera']!=initial['camera']:raise RuntimeError('Camera changed while recording')
    durations = [max(1, round((records[i+1]['elapsed_seconds']-r['elapsed_seconds'])*1000))
                 if i+1<len(records) else round(1000/fps) for i,r in enumerate(records)]
    path = out/'animation.apng'
    frames[0].save(path, format='PNG', save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, disposal=0, blend=0, compress_level=4)
    # Reopen every decoded frame and verify exact RGB identity; APNG's
    # compression may merge unchanged frames, so compare its timeline.
    from PIL import Image
    checked = 0
    with Image.open(path) as animation:
        for i in range(animation.n_frames):
            animation.seek(i)
            digest = hashlib.sha256(animation.convert('RGB').tobytes()).hexdigest()
            if digest not in {r['rgb_sha256'] for r in records}:
                raise ValueError('Animated PNG contains pixels absent from source frames')
            checked += 1
    meta = dict(final, provider='original_retail_1.22L'if retail_meta else'original_game', viewport=[640,340],
                capture_start_screen_frame=initial['screen_frame'],capture_end_screen_frame=final['screen_frame'],
                target_fps=fps, recorded_frames=len(frames), stored_frames=checked,
                distinct_frames=len({r['rgb_sha256'] for r in records}),
                rgb_preservation='all stored frames exactly match source frames',
                animation_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), timeline=records)
    dump(out/'capture.json', meta)
    frames[0].save(out/'reference.png')
    return meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--camera',type=int,nargs=4,required=True,metavar=('LEVEL','X','Y','Z'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=float,default=4)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--atlas',type=Path,help='Retail output variant directory, to use its matching module and clock')
    a = p.parse_args()
    if not .1 <= a.seconds <= 30 or not 1 <= a.fps <= 60:
        p.error('Use 0.1–30 seconds at 1–60 fps')
    retail_meta=json.loads((a.atlas/f'level-{a.camera[0]}'/'manifest.json').read_text())if a.atlas else None
    if retail_meta:
        if retail_meta.get('provider')!='original_retail_1.22L':p.error('--atlas expects an accepted or held retail map directory')
        from .retail import RUNTIME
    else:
        from .game import RUNTIME
    import fcntl
    with(RUNTIME/'export.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        meta = record(*a.camera,a.out,a.seconds,a.fps,retail_meta)
    print(json.dumps({k:v for k,v in meta.items() if k!='timeline'},indent=2))

if __name__=='__main__':main()
