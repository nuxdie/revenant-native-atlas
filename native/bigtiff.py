"""Stream and verify lossless tiled BigTIFFs without allocating whole maps."""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from atlas import dump


def library():
    lib=C.CDLL(ctypes_path:=C.util.find_library('tiff'))
    if not ctypes_path:raise RuntimeError('libtiff is required')
    lib.TIFFOpen.argtypes=[C.c_char_p,C.c_char_p];lib.TIFFOpen.restype=C.c_void_p
    lib.TIFFClose.argtypes=[C.c_void_p]
    lib.TIFFSetField.argtypes=[C.c_void_p,C.c_uint32];lib.TIFFSetField.restype=C.c_int
    lib.TIFFGetField.argtypes=[C.c_void_p,C.c_uint32];lib.TIFFGetField.restype=C.c_int
    for name in('TIFFWriteEncodedTile','TIFFReadEncodedTile'):
        fn=getattr(lib,name);fn.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p,C.c_ssize_t];fn.restype=C.c_ssize_t
    lib.TIFFIsBigTIFF.argtypes=[C.c_void_p];lib.TIFFIsBigTIFF.restype=C.c_int
    return lib


def tile(root,meta,tx,ty):
    size=meta['tile_size'];result=np.zeros((size,size,3),dtype=np.uint8)
    path=root/'tiles'/f'{tx}_{ty}.png'
    if path.exists():
        with Image.open(path)as im:
            rgb=np.asarray(im.convert('RGB'));result[:rgb.shape[0],:rgb.shape[1]]=rgb
    return result


def verify(path,root,meta):
    lib=library();handle=lib.TIFFOpen(str(path).encode(),b'r')
    if not handle:raise RuntimeError('Cannot reopen BigTIFF')
    try:
        assert lib.TIFFIsBigTIFF(handle)==1
        for tag,value in((256,meta['width']),(257,meta['height']),(322,meta['tile_size']),(323,meta['tile_size'])):
            read=C.c_uint32();assert lib.TIFFGetField(handle,tag,C.byref(read))==1 and read.value==value
        for tag,value in((258,8),(259,8),(262,2),(277,3),(284,1),(317,2)):
            read=C.c_uint16();assert lib.TIFFGetField(handle,tag,C.byref(read))==1 and read.value==value
        size=meta['tile_size'];buffer=np.empty((size,size,3),dtype=np.uint8);checked=0
        columns=(meta['width']+size-1)//size;rows=(meta['height']+size-1)//size
        for y in range(rows):
            for x in range(columns):
                assert lib.TIFFReadEncodedTile(handle,y*columns+x,buffer.ctypes.data,buffer.nbytes)==buffer.nbytes
                original=tile(root,meta,x,y)
                if not np.array_equal(buffer,original):raise ValueError(f'BigTIFF changed RGB pixels: tile {x},{y}')
                checked+=min(size,meta['width']-x*size)*min(size,meta['height']-y*size)
        return checked
    finally:lib.TIFFClose(handle)


def build(root):
    meta=json.loads((root/'manifest.json').read_text());validation=json.loads((root/'validation.json').read_text())
    if validation['acceptance']=='review_required':raise ValueError('Resolve native audit before TIFF export')
    path=root/'full-resolution.tif';record=root/'tiff-validation.json'
    if path.exists()and record.exists():
        old=json.loads(record.read_text())
        if old['source_png_sha256']==validation['full_png_sha256'] and old['bytes']==path.stat().st_size:
            with path.open('rb')as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            if digest==old['sha256']:return old
    lib=library();temporary=path.with_suffix('.tif.tmp');handle=lib.TIFFOpen(str(temporary).encode(),b'w8')
    if not handle:raise RuntimeError('Cannot create BigTIFF')
    try:
        for tag,value in((256,meta['width']),(257,meta['height']),(258,8),(259,8),(262,2),(274,1),(277,3),(284,1),
                          (317,2),(322,meta['tile_size']),(323,meta['tile_size']),(339,1),(65557,6)):
            if lib.TIFFSetField(handle,tag,C.c_uint(value))!=1:raise ValueError(f'Unsupported TIFF setting {tag}')
        size=meta['tile_size'];columns=(meta['width']+size-1)//size;rows=(meta['height']+size-1)//size
        for y in range(rows):
            for x in range(columns):
                rgb=tile(root,meta,x,y)
                if lib.TIFFWriteEncodedTile(handle,y*columns+x,rgb.ctypes.data,rgb.nbytes)!=rgb.nbytes:
                    raise RuntimeError(f'BigTIFF tile write failed: {x},{y}')
    finally:lib.TIFFClose(handle)
    checked=verify(temporary,root,meta)
    with temporary.open('rb')as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    temporary.replace(path)
    result=dict(format='BigTIFF',tile_size=meta['tile_size'],compression='Deflate',predictor='horizontal',
                bits_per_sample=8,samples_per_pixel=3,photometric='RGB',size=[meta['width'],meta['height']],
                source_png_sha256=validation['full_png_sha256'],sha256=digest,bytes=path.stat().st_size,
                all_rgb_pixels_equal_native_tiles=checked)
    dump(record,result);print(f'{root.name}: tiled BigTIFF, {checked:,} RGB pixels verified; {path.stat().st_size:,} bytes',flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--levels');parser.add_argument('--exclude');args=parser.parse_args()
    only=set(map(int,args.levels.split(',')))if args.levels else None
    exclude=set(map(int,args.exclude.split(',')))if args.exclude else set()
    for root in sorted(Path('native-output').glob('level-*'),key=lambda p:int(p.name.split('-')[1])):
        n=int(root.name.split('-')[1])
        if n not in exclude and(only is None or n in only):build(root)
