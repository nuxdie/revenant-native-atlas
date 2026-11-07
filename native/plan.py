"""Plan native captures from actual scenery coverage and every map placement."""
from collections import Counter
import json
import math
from pathlib import Path
import struct

from PIL import Image

from atlas import project, sector_position,parse_legacy

CORE_W, CORE_H = 512, 256


def positions(path):
    data = path.read_bytes()
    magic, version = struct.unpack_from('<4si', data)
    count, = struct.unpack_from('<i', data, 12 if version >= 14 else 8)
    if magic==b'MAP 'and 1<=version<=7:
        objects,_,_,_=parse_legacy(path,data,version,count)
        for obj in objects:
            yield {'class':obj.cls,'uid':obj.uid,'flags':obj.flags,
                   'pos':[obj.x,obj.y,obj.z],'name':obj.name}
        return
    if magic != b'MAP ' or not 8 <= version <= 14 or not 0 <= count < 100000:
        raise ValueError(f'Unsupported map header: {path}')
    offset = 16 if version >= 14 else 12
    for _ in range(count):
        objversion, = struct.unpack_from('<h', data, offset)
        offset += 2
        if objversion < 0:
            continue
        cls, = struct.unpack_from('<h', data, offset)
        offset += 2
        if cls < 0:
            continue
        uid, size = struct.unpack_from('<Ih', data, offset)
        offset += 6
        if version >= 14:
            offset += 2  # Separate inventory size; both blocks are in size.
        end = offset + size
        if size < 0 or end > len(data):
            raise ValueError(f'Invalid object block: {path}')
        body = offset
        # LOAD_BASE prefixes, from TPlayer / TCharacter / TComplexObject.
        # Only positions are needed here; inventory remains inside the block.
        if cls in (11, 12):
            character_version = objversion
            if cls == 11 and objversion > 3:
                character_version = data[body]
                body += 1
            complex_version = 0
            if character_version >= 3:
                complex_version = data[body]
                body += 1
            if complex_version >= 1:
                body += 1
        if body >= end:
            raise ValueError(f'Empty base record: {path}')
        length = data[body]
        base = body + 1 + length
        if base + 16 > end:
            raise ValueError(f'Truncated base record: {path}')
        flags, x, y, z = struct.unpack_from('<Iiii', data, base)
        yield {'class': cls, 'uid': uid, 'flags': flags, 'pos': [x, y, z],
               'name': bytes(c & 127 for c in data[body + 1:base]).decode('latin1')}
        offset = end
    if offset != len(data):
        raise ValueError(f'Trailing map bytes: {path}')


def create_plan(baseline, game, level):
    baseline, game = Path(baseline), Path(game)
    meta = json.loads((baseline / f'level-{level}/manifest.json').read_text())
    cores = set()
    left, top = meta['bounds'][:2]
    for tile in (baseline / f'level-{level}/tiles').glob('*.png'):
        tx, ty = map(int, tile.stem.split('_'))
        x, y = left + tx * meta['tile_size'], top + ty * meta['tile_size']
        with Image.open(tile) as source:
            for cy in range(y // CORE_H, (y + source.height - 1) // CORE_H + 1):
                for cx in range(x // CORE_W, (x + source.width - 1) // CORE_W + 1):
                    rect = (max(0, cx * CORE_W - x), max(0, cy * CORE_H - y),
                            min(source.width, (cx + 1) * CORE_W - x),
                            min(source.height, (cy + 1) * CORE_H - y))
                    if source.crop(rect).getbbox():
                        cores.add((cx, cy))
    static_count = len(cores)
    counts, excluded = Counter(), Counter()
    objects = []
    sectors = game / 'Modules/Ahkuilon/Map'
    for sector in sorted(sectors.iterdir()):
        if sector.suffix.lower() != '.dat' or not sector.name.startswith(f'{level}_'):
            continue
        for obj in positions(sector):
            counts[str(obj['class'])] += 1
            raw = obj['pos']
            x, y, z = sector_position(sector, *raw)
            if list((x,y,z)) != raw:
                excluded['sector_positions_wrapped_into_owning_sector'] += 1
            if not (0 <= x <= 32768 and 0 <= y <= 32768 and -4096 <= z <= 32768):
                excluded['invalid_world_position'] += 1
                continue
            if obj['flags'] & (128 | 256):
                excluded['invisible_or_editor_marker'] += 1
                continue
            objects.append(obj)
            sx, sy, _ = project(x, y, z)
            radius = 1024 if obj['class'] in (11, 12, 25) else 512
            for cy in range((sy - radius) // CORE_H, (sy + radius) // CORE_H + 1):
                for cx in range((sx - radius) // CORE_W, (sx + radius) // CORE_W + 1):
                    cores.add((cx, cy))
    if not cores:
        raise ValueError('No native capture coverage')
    minimum_x = min(x for x, _ in cores) * CORE_W
    minimum_y = min(y for _, y in cores) * CORE_H
    maximum_x = (max(x for x, _ in cores) + 1) * CORE_W
    maximum_y = (max(y for _, y in cores) + 1) * CORE_H
    rows = {}
    for x, y in cores:
        rows.setdefault(y, []).append(x)
    ordered = []
    for i, y in enumerate(sorted(rows)):
        ordered.extend([x, y] for x in sorted(rows[y], reverse=bool(i % 2)))
    return {'level': level, 'names': meta['names'], 'bounds': [minimum_x, minimum_y, maximum_x, maximum_y],
            'width': maximum_x - minimum_x, 'height': maximum_y - minimum_y,
            'core_size': [CORE_W, CORE_H], 'viewport': [640, 340], 'core_count': len(cores),
            'static_coverage_cores': static_count, 'cores': ordered,
            'source_objects_by_class': dict(counts), 'excluded_from_coverage': dict(excluded),
            'retained_source_objects': len(objects)}


def camera_for_core(cx, cy):
    # The even screen X and integer screen Y invert exactly at native Z=0.
    raw_x,raw_y=cx*CORE_W+CORE_W//2,cy*CORE_H+CORE_H//2
    sx,sy=int(raw_x),int(raw_y)
    if sx!=raw_x or sy!=raw_y or sx%2:raise ValueError('Native camera must align to an even horizontal pixel and integer row')
    return sy + sx // 2, sy - sx // 2, 0
