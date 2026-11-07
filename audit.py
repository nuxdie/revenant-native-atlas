#!/usr/bin/env python3
"""Validate atlas files, including lossless PNG tile-to-full-image comparisons."""
import argparse,json,math,struct,zlib
from pathlib import Path
import numpy as np
from PIL import Image

def verify_png(path):
    count=0;dims=None
    with path.open('rb')as f:
        if f.read(8)!=b'\x89PNG\r\n\x1a\n':raise ValueError('PNG signature')
        while True:
            n,typ=struct.unpack('>I4s',f.read(8));data=f.read(n);crc=struct.unpack('>I',f.read(4))[0]
            if zlib.crc32(typ+data)&0xffffffff!=crc:raise ValueError(f'{path}: CRC')
            if typ==b'IHDR':dims=struct.unpack('>II',data[:8])
            count+=1
            if typ==b'IEND':break
        if f.read(1):raise ValueError(f'{path}: trailing data')
    return dims

def verify_samples(root,meta):
    w,h=meta['width'],meta['height'];ts=meta['tile_size']
    # Sample native pixels across widely separated occupied tiles, including seams.
    keys=sorted((tuple(map(int,p.stem.split('_'))),p)for p in (root/'tiles').glob('*.png'))
    chosen=keys[::max(1,len(keys)//12)]
    samples={}
    for(tx,ty),p in chosen:
        arr=np.asarray(Image.open(p).convert('RGB'))
        for yy in (0,arr.shape[0]//2,arr.shape[0]-1):
            y=ty*ts+yy
            samples.setdefault(y,[]).append((tx*ts,arr[yy].copy()))
    co=zlib.decompressobj();buf=bytearray();rowbytes=1+w*3;y=0;checked=0
    def consume(raw):
        nonlocal y,checked,buf
        buf.extend(raw)
        while len(buf)>=rowbytes:
            if buf[0]!=1:raise ValueError('expected PNG Sub filter')
            if y in samples:
                encoded=np.frombuffer(buf,dtype=np.uint8,count=w*3,offset=1).reshape(w,3)
                row=np.cumsum(encoded,axis=0,dtype=np.uint8)
                for x,expected in samples[y]:
                    if not np.array_equal(row[x:x+len(expected)],expected):raise ValueError(f'native pixels differ at row {y}, x {x}')
                    checked+=len(expected)
                del encoded,row
            del buf[:rowbytes];y+=1
    with (root/'full-resolution.png').open('rb')as f:
        f.read(8)
        while True:
            n,typ=struct.unpack('>I4s',f.read(8));data=f.read(n);f.read(4)
            if typ==b'IDAT':
                while data:
                    consume(co.decompress(data,2**20));data=co.unconsumed_tail
            if typ==b'IEND':break
    consume(co.flush())
    if buf or y!=h or not co.eof:raise ValueError(f'incomplete pixel stream: {y}/{h}')
    return checked

def main():
    p=argparse.ArgumentParser();p.add_argument('out',nargs='?',type=Path,default=Path(__file__).parent/'output');p.add_argument('--sample-level',type=int,default=0);a=p.parse_args()
    maps=[];total=0;failures={};assets=json.loads((a.out/'assets.json').read_text())
    for mp in sorted(a.out.glob('level-*/manifest.json'),key=lambda p:int(p.parent.name.split('-')[1])):
        m=json.loads(mp.read_text());tiles=list((mp.parent/'tiles').glob('*.png'))
        if len(tiles)!=m['tile_count']:raise ValueError('tile count mismatch')
        for t in tiles:
            tw,th=verify_png(t)
            if not 0<tw<=m['tile_size']or not 0<th<=m['tile_size']:raise ValueError('tile dimensions')
        dims=verify_png(mp.parent/'full-resolution.png')
        if dims!=(m['width'],m['height']):raise ValueError('full dimensions')
        objects=json.loads((mp.parent/'placements.json').read_text())
        missing={o['key']for o in objects if o['key']not in assets}
        if missing:raise ValueError(f'{mp.parent.name}: missing asset metadata for {len(missing)} sprites')
        total+=len(objects)
        if m['statistics']['failed_objects']:failures[str(m['level'])]=m['statistics']['failed_objects']
        maps.append({'level':m['level'],'size':list(dims),'tiles':len(tiles),'objects':len(objects)})
    meta=json.loads((a.out/f'level-{a.sample_level}'/'manifest.json').read_text())
    checked=verify_samples(a.out/f'level-{a.sample_level}',meta)
    report={'maps':maps,'total_placed_scenery':total,'png_crcs':'all verified','source_metadata':'all placements resolved','sampled_native_pixels':checked,'sampled_level':a.sample_level,'omitted_unresolved':failures,'assets_with_clipped_depth':[{'path':m['path'],'state':m['state'],'chunks':m['clipped_depth_chunks']}for m in assets.values()if m.get('clipped_depth_chunks')]}
    (a.out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
