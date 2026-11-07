#!/usr/bin/env python3
"""Capture a reproducible classic-port scene and the matching static atlas crop.

Port captures are candidates, never retail reference evidence. Comparison with
the static exporter exposes omissions; it is not a fidelity acceptance test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from PIL import Image

from atlas import project
from fidelity import compare


def atlas_crop(root, level, center, size):
    meta = json.loads((root / f'level-{level}/manifest.json').read_text())
    sx, sy, _ = project(*center)
    left = sx - size[0] // 2 - meta['bounds'][0]
    top = sy - size[1] // 2 - meta['bounds'][1]
    result = Image.new('RGB', size)
    ts = meta['tile_size']
    for ty in range(top // ts, (top + size[1] - 1) // ts + 1):
        for tx in range(left // ts, (left + size[0] - 1) // ts + 1):
            tile = root / f'level-{level}/tiles/{tx}_{ty}.png'
            if tile.exists():
                with Image.open(tile) as image:
                    result.paste(image.convert('RGB'), (tx * ts - left, ty * ts - top))
    return result


def capture(binary, game, assets, output, camera, size=(640, 340), frames=60, seed=1, atlas=None):
    binary, game, assets, output = (Path(p).resolve() for p in (binary, game, assets, output))
    output.mkdir(parents=True, exist_ok=True)
    save = output / 'save'
    save.mkdir(exist_ok=True)
    ini = (game / 'revenant.ini').read_text(encoding='latin1')
    # Keep a separate user-data tree. The original install is never the save root.
    ini += '\n[Revisited]\nLightingMode=0\n'
    (save / 'Revenant.ini').write_text(ini, encoding='latin1')
    frame = output / 'classic-port.png'
    frame.unlink(missing_ok=True)
    command = [str(binary), '--test=sector', '--scene-camera=' + ','.join(map(str, camera)),
               '--scene-viewport=' + ','.join(map(str, size)),
               f'--resolution={size[0]}x{max(480, size[1])}', '--headless', '--fixedstep',
               f'--seed={seed}', f'--snapwarmup={frames}', f'--snap={frame}', '--max-runtime=60']
    env = dict(os.environ, REVENANT_DATA_PATH=str(game), REVENANT_SAVE_PATH=str(save),
               REVENANT_ASSETS_PATH=str(assets))
    with (output / 'engine.log').open('w') as log:
        process = subprocess.run(command, env=env, cwd=output, stdout=log,
                                 stderr=subprocess.STDOUT, timeout=90)
    record = {'provider': 'RevenantRevisited classic port; not original executable',
              'camera': list(camera), 'viewport': list(size), 'warmup_frames': frames,
              'seed': seed, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'ini_sha256': hashlib.sha256((save / 'Revenant.ini').read_bytes()).hexdigest(),
              'command': command, 'returncode': process.returncode, 'captured': frame.exists()}
    (output / 'capture.json').write_text(json.dumps(record, indent=2) + '\n')
    if process.returncode or not frame.exists():
        raise RuntimeError(f'Capture failed; inspect {output / "engine.log"}')
    with Image.open(frame) as image:
        image.crop((0, 0, *size)).save(output / 'viewport.png')
    if atlas:
        atlas_crop(Path(atlas), camera[0], camera[1:], size).save(output / 'static-baseline.png')
        compare(output / 'viewport.png', output / 'static-baseline.png', output / 'baseline-difference')
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('binary', 'game', 'assets', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--camera', type=int, nargs=4, metavar=('LEVEL', 'X', 'Y', 'Z'), required=True)
    p.add_argument('--size', type=int, nargs=2, default=(640, 340))
    p.add_argument('--frames', type=int, default=60)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--atlas', type=Path)
    a = p.parse_args()
    print(json.dumps(capture(a.binary, a.game, a.assets, a.out, a.camera, a.size, a.frames, a.seed, a.atlas), indent=2))


if __name__ == '__main__':
    main()
