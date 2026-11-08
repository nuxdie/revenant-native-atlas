"""Identify ambient-sound presentation meshes and audit their native owners."""
from collections import OrderedDict
import json
from pathlib import Path
import re
from zipfile import ZipFile

import numpy as np
from PIL import Image

from atlas import project, sector_position
from .plan import positions

SPEAKER_ID = 0xad92bc10
PROFILE = 'speaker_mesh_hidden_v1'
PADDING = 64


def speaker_positions(pack, level):
    result = []
    with ZipFile(pack) as archive:
        for name in archive.namelist():
            if not re.fullmatch(rf'Map/{level}_\d+_\d+\.dat', name, re.I):
                continue
            for obj in positions(Path(name), archive.read(name)):
                if obj['class'] != 25 or obj['uid'] != SPEAKER_ID or obj['flags'] & 0x180:
                    continue
                point = sector_position(Path(name), *obj['pos'])
                result.append(dict(position=list(point), screen=list(project(*point)[:2])))
    return result


def intersects_viewport(scroll, points, padding=PADDING):
    x, y = scroll
    return any(x-padding <= p['screen'][0] < x+640+padding and
               y-padding <= p['screen'][1] < y+340+padding for p in points)


def owned_sources(root, points, padding=PADDING):
    root = Path(root)
    meta = json.loads((root/'manifest.json').read_text())
    size = meta['tile_size']
    left, top = meta['bounds'][:2]
    owners, cache = set(), OrderedDict()
    for point in points:
        x, y = point['screen']
        l, t = max(0, x-left-padding), max(0, y-top-padding)
        r, b = min(meta['width'], x-left+padding+1), min(meta['height'], y-top+padding+1)
        if r <= l or b <= t:
            continue
        for ty in range(t//size, (b-1)//size+1):
            for tx in range(l//size, (r-1)//size+1):
                path = root/'ownership'/f'{tx}_{ty}.png'
                if not path.exists():
                    continue
                key = tx, ty
                if key not in cache:
                    with Image.open(path) as image:
                        cache[key] = np.array(image)
                    while len(cache) > 16:
                        cache.popitem(last=False)
                a = cache[key]
                region = a[max(0,t-ty*size):min(a.shape[0],b-ty*size),
                           max(0,l-tx*size):min(a.shape[1],r-tx*size)]
                owners.update(map(int, np.unique(region)))
    return [s['capture'] for s in json.loads((root/'ownership-sources.json').read_text())
            if s['id'] in owners]


def require_clean_owners(root, points):
    names = owned_sources(root, points)
    dirty = [name for name in names if
             json.loads((Path(root)/'captures'/f'{name}.json').read_text()).get('sound_marker_profile') != PROFILE]
    if dirty:
        raise ValueError(f'Unfiltered sound-marker source owners remain: {dirty[:12]}')
    return names
