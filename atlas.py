#!/usr/bin/env python3
"""Render Revenant's retail world from its map objects and native sprite pixels.

No game installation files are changed. Input is an extracted retail install.
The outdoor island is level 0; interiors and other areas remain separate levels.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from functools import lru_cache
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import zlib
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
DEFAULT_GAME=Path(os.environ.get('REVENANT_GAME', HERE/'runtime/game'))
WORLD_Z_OFFSET=0x3900+0x7fff
CLASSES={0:'ITEM',1:'WEAPON',2:'ARMOR',3:'TALISMAN',4:'FOOD',5:'CONTAINER',6:'LIGHTSOURCE',7:'TOOL',8:'MONEY',9:'TILE',10:'EXIT',11:'PLAYER',12:'CHARACTER',13:'TRAP',14:'SHADOW',15:'HELPER',16:'KEY',17:'INVCONTAINER',18:'POISON',19:'UNUSED1',20:'UNUSED2',21:'AMMO',22:'SCROLL',23:'RANGEDWEAPON',24:'UNUSED3',25:'EFFECT',26:'MAPSCROLL'}

class FormatError(ValueError):pass

def dump(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    temporary.replace(path)

def project(x,y,z):
    # C++ integer division truncates toward zero, including negative coordinates.
    return x-y, int((x+y)/2)-int(z*867/1000), (WORLD_Z_OFFSET-int(z/2)-int((x+y)*867/1000))&65535

def sector_position(path, x, y, z):
    # TSector::KeepInside in the game wraps coordinates into their owning
    # sector. Some shipped maps contain sector-local or displaced positions.
    _,sx,sy=map(int,Path(path).stem.split('_'))
    def inside(v, sector):
        lo=sector*1024;hi=lo+1024
        # This executable retains the upper boundary itself. A modulo-only
        # implementation incorrectly moves a tile at hi back to lo.
        if v<lo:v+=((lo-v+1023)//1024)*1024
        elif v>hi:v-=((v-hi+1023)//1024)*1024
        return v
    return inside(x,sx), inside(y,sy), z

@dataclass
class Placement:
    uid:int
    cls:int
    flags:int
    x:int
    y:int
    z:int
    state:int
    facing:int
    sector:str
    name:str=''


def parse_sector(path:Path):
    b=path.read_bytes()
    if len(b)<12 or b[:4]!=b'MAP ':raise FormatError(f'{path}: not MAP')
    version,count=struct.unpack_from('<ii',b,4)
    if version<8:return parse_legacy(path,b,version,count)
    if version>13:raise FormatError(f'{path}: unsupported MAP version {version}')
    if not 0<=count<100000:raise FormatError(f'{path}: invalid object count')
    o=12;objects=[];ignored=Counter()
    for _ in range(count):
        if o+2>len(b):raise FormatError(f'{path}: truncated slot')
        ov=struct.unpack_from('<h',b,o)[0];o+=2
        if ov<0:continue
        if o+8>len(b):raise FormatError(f'{path}: truncated object header')
        cls,uid,size=struct.unpack_from('<hIh',b,o);o+=8
        if size<0 or o+size>len(b):raise FormatError(f'{path}: invalid block length {size}')
        end=o+size
        # CHARACTER prepends subclass data; it is not static map artwork.
        # Skip its whole bounded block rather than interpreting it as base data.
        if cls in (11,12,15,25):ignored[CLASSES.get(cls,str(cls))]+=1;o=end;continue
        n=b[o];o+=1;name=b[o:o+n].decode('latin1');o+=n
        if o+18>end:raise FormatError(f'{path}: truncated base object')
        flags,x,y,z=struct.unpack_from('<Iiii',b,o);o+=16
        if not flags&1:o+=12
        state=struct.unpack_from('<H'if version>=9 else'<B',b,o)[0];o+=2 if version>=9 else 1
        if flags&(1<<19):o+=2 if version>=9 else 1
        if o+15>end:raise FormatError(f'{path}: truncated rotation')
        invent,invindex,shadow,rx,ry,rz,mi=struct.unpack_from('<hhiBBBi',b,o)
        if invent>=0:ignored['inventory']+=1
        elif flags&128:ignored['invisible']+=1
        else:
            _,sector_x,sector_y=map(int,path.stem.split('_'))
            fixed=sector_position(path,x,y,z)
            if fixed!=(x,y,z):ignored['sector_positions_wrapped']+=1
            x,y,z=fixed
            if not (0<=x<=32768 and 0<=y<=32768 and -4096<=z<=32768):
                ignored['outside_world_coordinates']+=1
            else:
                objects.append(Placement(uid,cls,flags,x,y,z,state,rz,path.stem,name))
        o=end
    if o!=len(b):raise FormatError(f'{path}: {len(b)-o} unparsed bytes')
    return objects,ignored,version,count


def parse_legacy(path,b,version,count):
    """Retail includes old dungeon sectors using the original v1 base record."""
    if not 1<=version<=7:raise FormatError(f'{path}: unsupported old MAP {version}')
    o=12;objects=[];ignored=Counter()
    for _ in range(count):
        cls=struct.unpack_from('<h',b,o)[0];o+=2
        if cls<0:continue
        uid=struct.unpack_from('<I',b,o)[0];o+=4
        end=None
        if version>=4:
            size=struct.unpack_from('<h',b,o)[0];o+=2;end=o+size
            if size<0 or end>len(b):raise FormatError('bad legacy block')
            if cls in (11,12,15,25):ignored[CLASSES[cls]]+=1;o=end;continue
        n=b[o];o+=1;name=b[o:o+n].decode('latin1');o+=n
        flags,x,y,z=struct.unpack_from('<Iiii',b,o);o+=16
        if version<6 or not flags&1:o+=12
        state=b[o];o+=1
        if version>=6 and flags&(1<<19):o+=1
        if version<5:o+=1 # obsolete health byte
        if version<3:
            rz=b[o];o+=12;invent=-1
        else:
            invent,invindex,shadow,rx,ry,rz,mi=struct.unpack_from('<hhiBBBi',b,o);o+=15
        if version>=5:
            if version<6 or flags&(1<<14):o+=4
            o+=1;nstats=b[o];o+=1+nstats*8
        if flags&4:o+=19
        if cls in (5,10) and 2<=version<5:o+=8
        if cls==10:o+=4 # TExit::exitflags
        if version>=3 and end is None:raise FormatError('legacy inventory requires bounded record')
        if end is not None:o=end
        if o>len(b):raise FormatError('truncated legacy object')
        if flags&128:ignored['invisible']+=1
        elif invent>=0:ignored['inventory']+=1
        else:
            _,sx,sy=map(int,path.stem.split('_'))
            fixed=sector_position(path,x,y,z)
            if fixed!=(x,y,z):ignored['sector_positions_wrapped']+=1
            x,y,z=fixed
            if 0<=x<=32768 and 0<=y<=32768 and -4096<=z<=32768:
                objects.append(Placement(uid,cls,flags,x,y,z,state,rz,path.stem,name))
            else:ignored['outside_world_coordinates']+=1
    if o!=len(b):raise FormatError(f'{path}: legacy parse ends at {o}, size {len(b)}')
    return objects,ignored,version,count


def parse_types(path):
    types={};cls=''
    for line in path.read_text(errors='replace').splitlines():
        m=re.match(r'CLASS\s+"([^"]+)"',line)
        if m:cls=m[1]
        m=re.match(r'\s*"([^"]+)"\s+"([^"]+)"\s+(0x[\da-fA-F]+)',line)
        if m:
            uid=int(m[3],16);key=(cls,uid)
            value={'name':m[1],'path':m[2].replace('\\','/'),'class':cls}
            # The engine FindObjType selects the first matching unique ID.
            types.setdefault(key,value)
    return types


class Game:
    def __init__(self,path):
        self.path=Path(path).resolve()
        self.types=parse_types(self.path/'Resources/class.def')
        self.imagery=self.path/'Resources/Imagery'
        self.files={p.relative_to(self.imagery).as_posix().casefold():p for p in self.imagery.rglob('*')if p.is_file()}
        self.sectors=defaultdict(list)
        for p in (self.path/'Modules/Ahkuilon/Map').iterdir():
            if p.suffix.lower()!='.dat':continue
            m=re.fullmatch(r'(\d+)_(\d+)_(\d+)',p.stem)
            if m:self.sectors[int(m[1])].append(p)
        self.areas=defaultdict(list)
        text=(self.path/'Modules/Ahkuilon/area.def').read_text(errors='replace')
        for name,level in re.findall(r'AREA\s+"([^"]+)"\s*BEGIN.*?\bLEVEL\s+(\d+)',text,re.S):
            if name.strip()not in self.areas[int(level)]:self.areas[int(level)].append(name.strip())
    def type(self,obj):
        result=self.types.get((CLASSES.get(obj.cls),obj.uid))
        if not result:
            found=[v for (c,u),v in self.types.items()if u==obj.uid]
            if len(found)==1:result=found[0]
        if not result:raise FormatError(f'unknown object type {obj.cls} {obj.uid:x}')
        return result
    def level(self,level):
        objects=[];ignored=Counter();versions=Counter();slots=0
        for p in sorted(self.sectors[level],key=lambda p:tuple(map(int,p.stem.split('_')))):
            o,i,v,n=parse_sector(p);objects.extend(o);ignored.update(i);versions[v]+=1;slots+=n
        return objects,{'sectors':len(self.sectors[level]),'map_versions':dict(versions),'object_slots':slots,'scenery_objects':len(objects),'excluded':dict(ignored)}


class Decoder:
    def __init__(self):
        lib=HERE/'_codec.so';src=HERE/'codec.cpp'
        if not lib.exists()or lib.stat().st_mtime<src.stat().st_mtime:
            subprocess.run(['g++','-std=c++17','-O3','-shared','-fPIC',str(src),'-o',str(lib)],check=True)
        self.clipped_depth_chunks=0
        self.lib=ctypes.CDLL(str(lib));self.fn=self.lib.rev_chunk
        self.fn.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_int]
        self.fn.restype=ctypes.c_int
    def chunk(self,b,start,depth=False):
        out=np.empty((64,64),np.uint16)
        rc=self.fn(b,len(b),start,out.ctypes.data,int(depth))
        if rc==1 and depth:self.clipped_depth_chunks+=1
        elif rc:raise FormatError(f'chunk at {start}: decoder error {rc}')
        return out
    def plane(self,b,start,w,h,depth=False):
        typ,nc,nr=struct.unpack_from('<III',b,start)
        if typ!=5 or nc!=math.ceil(w/64)or nr!=math.ceil(h/64):
            raise FormatError(f'chunk grid {(typ,nc,nr)} does not fit {w}x{h}')
        if start+12+4*nc*nr>len(b):raise FormatError('truncated chunk table')
        out=np.full((nr*64,nc*64),0x7f7f if depth else 0,np.uint16)
        for k in range(nc*nr):
            pos=start+12+4*k;off=struct.unpack_from('<I',b,pos)[0]
            if off:
                block=self.chunk(b,pos+off,depth)
                out[k//nc*64:(k//nc+1)*64,k%nc*64:(k%nc+1)*64]=block
        return out[:h,:w].copy()
    def sprite(self,path,state=0):
        self.clipped_depth_chunks=0
        b=path.read_bytes()
        if len(b)<104 or b[:4]!=b'CGSR':raise FormatError('not CGSR')
        _,nbm,comp,version,ds,objsize,hs=struct.unpack_from('<4sHBBIII',b)
        if comp!=0:raise FormatError(f'unsupported resource compression {comp}')
        handler,nstates=struct.unpack_from('<II',b,20)
        if handler!=0:raise FormatError(f'not animation imagery: {handler}')
        if not 0<=state<nstates:raise FormatError(f'state {state} exceeds {nstates}')
        # SImageryStateHeader is packed, 76 bytes; relative walkmap follows it.
        sh=28+state*76
        w,h,regx,regy,regz=struct.unpack_from('<5h',b,sh+44)
        base=20+hs+nbm*4;field=base+state*20
        rel=struct.unpack_from('<I',b,field)[0]
        if not rel:return None
        bm=field+rel
        if bm+72>len(b):raise FormatError('bitmap outside file')
        m=struct.unpack_from('<18I',b,bm);bw,bh=m[:2];flags=m[4]
        if not(0<bw<=8192 and 0<bh<=8192):raise FormatError('invalid bitmap dimensions')
        if flags&0x800: return None
        if flags&1:
            if flags&0x8000:indices=self.plane(b,bm+72,bw,bh)
            elif flags&0x4000:raise FormatError('non-chunked compressed bitmap')
            else:
                stride=m[17]//bh
                if stride<bw:raise FormatError('short pixel rows')
                indices=np.frombuffer(b,np.uint8,count=stride*bh,offset=bm+72).reshape(bh,stride)[:,:bw]
            palpos=bm+64+m[16]
            pal=np.frombuffer(b,dtype='<u2',count=256,offset=palpos)
            rgba_pal=np.stack([((pal>>10)&31)<<3,((pal>>5)&31)<<3,(pal&31)<<3,np.where(np.arange(256)==m[6],0,255)],axis=1).astype(np.uint8)
            rgba=rgba_pal[indices]
        elif flags&6:
            stride=m[17]//(2*bh)
            words=np.frombuffer(b,dtype='<u2',count=stride*bh,offset=bm+72).reshape(bh,stride)[:,:bw]
            greenmask=63 if flags&4 else 31;greenshift=5
            redshift=11 if flags&4 else 10
            rgba=np.stack([((words>>redshift)&31)<<3,((words>>greenshift)&greenmask)<<(2 if flags&4 else 3),(words&31)<<3,np.where(words==m[6],0,255)],axis=-1).astype(np.uint8)
        else:raise FormatError(f'unsupported bitmap flags {flags:x}')
        depth=None
        if flags&0x20 and m[11]:
            zstart=bm+48+m[12]
            if flags&0x8000:depth=self.plane(b,zstart,bw,bh,True)
            else:depth=np.frombuffer(b,dtype='<u2',count=bw*bh,offset=zstart).reshape(bh,bw).copy()
            rgba[depth==0x7f7f,3]=0
        stateflags=struct.unpack_from('<I',b,field+16)[0]
        return rgba,depth,{'regx':regx,'regy':regy,'regz':regz,'width':bw,'height':bh,'state_width':w,'state_height':h,'flags':flags,'state_flags':stateflags,'clipped_depth_chunks':self.clipped_depth_chunks,'source_sha256':hashlib.sha256(b).hexdigest()}


class SpriteCache:
    def __init__(self,game,out):
        self.game=game;self.root=out/'sprites';self.root.mkdir(parents=True,exist_ok=True)
        self.decoder=Decoder()
        self.meta=json.loads((out/'assets.json').read_text())if(out/'assets.json').exists()else{}
        self.failures={};self.empty=[]
    def key(self,path,state):return hashlib.sha256((path.casefold()+':'+str(state)).encode()).hexdigest()[:20]
    def prepare(self,path,state):
        key=self.key(path,state)
        source=self.game.files.get(path.casefold())
        if not source:raise FormatError('missing imagery '+path)
        if key in self.meta and (self.root/(key+'.png')).exists():
            if self.meta[key].get('source_sha256')==hashlib.sha256(source.read_bytes()).hexdigest():return key
        result=self.decoder.sprite(source,state)
        if result is None:self.empty.append({'path':path,'state':state});return None
        rgba,depth,meta=result;meta.update(path=path,state=state)
        Image.fromarray(rgba).save(self.root/(key+'.png'))
        if depth is not None:np.save(self.root/(key+'-z.npy'),depth)
        self.meta[key]=meta
        return key
    @lru_cache(maxsize=128)
    def load(self,key):
        rgba=np.asarray(Image.open(self.root/(key+'.png')).convert('RGBA'))
        zp=self.root/(key+'-z.npy')
        depth=np.load(zp,mmap_mode='r')if zp.exists()else None
        return rgba,depth


def collect(game,cache,level):
    objects,stats=game.level(level);items=[];failed=Counter();nodraw=Counter();prepared={}
    for obj in objects:
        try:typ=game.type(obj)
        except FormatError:
            failed[f'unknown_type_{obj.cls}_{obj.uid:08x}']+=1
            continue
        path=typ['path'];ref=(path.casefold(),obj.state)
        if not path.lower().endswith('.i2d'):nodraw['3d_geometry']+=1;continue
        # Light marker imagery is an illumination effect, not static terrain.
        if obj.flags&4:nodraw['light_effect']+=1;continue
        if ref not in prepared:
            try:prepared[ref]=cache.prepare(path,obj.state)
            except (ValueError,IndexError,struct.error,OverflowError) as e:
                cache.failures[str(ref)]={'path':path,'state':obj.state,'error':str(e)};prepared[ref]=False
        key=prepared[ref]
        if key is False:failed[path]+=1;continue
        if key is None:nodraw['no_still_image']+=1;continue
        m=cache.meta[key];sx,sy,sz=project(obj.x,obj.y,obj.z)
        x=sx-m['regx'];y=sy-m['regy'];z=sz-m['regz']
        items.append({'key':key,'x':x,'y':y,'depth':z,'flip':bool(obj.flags&512),'width':m['width'],'height':m['height'],'sector':obj.sector,'uid':obj.uid})
    stats.update(rendered_objects=len(items),failed_objects=dict(failed),omitted=dict(nodraw),decoded_assets=len(cache.meta))
    if not items:return None,stats
    bounds=[min(o['x']for o in items),min(o['y']for o in items),max(o['x']+o['width']for o in items),max(o['y']+o['height']for o in items)]
    return {'level':level,'names':game.areas[level],'bounds':bounds,'width':bounds[2]-bounds[0],'height':bounds[3]-bounds[1],'objects':items},stats


def raster(cache,items,rect):
    x0,y0,x1,y1=rect;w=x1-x0;h=y1-y0
    rgb=np.zeros((h,w,4),np.uint8);zbuf=np.full((h,w),np.iinfo(np.int32).max,np.int32)
    for o in items:
        l=max(x0,o['x']);t=max(y0,o['y']);r=min(x1,o['x']+o['width']);b=min(y1,o['y']+o['height'])
        if l>=r or t>=b:continue
        rgba,depth=cache.load(o['key'])
        if o['flip']:
            rgba=rgba[:,::-1]
            if depth is not None:depth=depth[:,::-1]
        src=rgba[t-o['y']:b-o['y'],l-o['x']:r-o['x']]
        dest=rgb[t-y0:b-y0,l-x0:r-x0]
        dz=zbuf[t-y0:b-y0,l-x0:r-x0]
        sz=depth[t-o['y']:b-o['y'],l-o['x']:r-o['x']].astype(np.int32)+o['depth']if depth is not None else o['depth']
        mask=(src[:,:,3]>0)&(sz<=dz)
        dest[mask]=src[mask]
        if isinstance(sz,np.ndarray):dz[mask]=sz[mask]
        else:dz[mask]=sz
    return Image.fromarray(rgb,'RGBA')


def png_chunk(f,typ,data):
    f.write(struct.pack('>I',len(data)));f.write(typ);f.write(data)
    f.write(struct.pack('>I',zlib.crc32(typ+data)&0xffffffff))


def write_full_png(leveldir,manifest,size):
    # Stream tile strips, keeping at most width * tile_size * 3 bytes in memory.
    w,h=manifest['width'],manifest['height'];path=leveldir/'full-resolution.png'
    temporary=path.with_suffix('.png.tmp')
    co=zlib.compressobj(6);pending=bytearray()
    with temporary.open('wb')as f:
        f.write(b'\x89PNG\r\n\x1a\n');png_chunk(f,b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))
        for ty in range(math.ceil(h/size)):
            strip=np.zeros((min(size,h-ty*size),w,3),np.uint8)
            for tx in range(math.ceil(w/size)):
                p=leveldir/'tiles'/f'{tx}_{ty}.png'
                if p.exists():
                    a=np.asarray(Image.open(p).convert('RGB'));strip[:a.shape[0],tx*size:tx*size+a.shape[1]]=a
            # PNG Sub filter: preserve pixel precision, improve compression of terrain.
            for row in strip:
                raw=row.reshape(-1);filtered=raw.copy();filtered[3:]=raw[3:]-raw[:-3]
                pending.extend(co.compress(b'\x01'+filtered.tobytes()))
                if len(pending)>2**20:png_chunk(f,b'IDAT',bytes(pending));pending.clear()
        pending.extend(co.flush());png_chunk(f,b'IDAT',bytes(pending));png_chunk(f,b'IEND',b'')
    temporary.replace(path)
    return path


def render_level(cache,manifest,stats,out,size=1024,full=True):
    leveldir=out/f'level-{manifest["level"]}';tiles=leveldir/'tiles';tiles.mkdir(parents=True,exist_ok=True)
    left,top,right,bottom=manifest['bounds'];w,h=manifest['width'],manifest['height']
    buckets=defaultdict(list)
    for o in manifest['objects']:
        for ty in range((o['y']-top)//size,(o['y']-top+o['height']-1)//size+1):
            for tx in range((o['x']-left)//size,(o['x']-left+o['width']-1)//size+1):buckets[tx,ty].append(o)
    expected={f'{tx}_{ty}.png'for tx,ty in buckets}
    for previous in tiles.glob('*.png'):
        if previous.name not in expected:previous.unlink()
    scale=min(1,4096/max(w,h));preview=Image.new('RGB',(math.ceil(w*scale),math.ceil(h*scale)))
    seen=0;start=time.time()
    for(tx,ty),objects in sorted(buckets.items(),key=lambda kv:(kv[0][1],kv[0][0])):
        rect=(left+tx*size,top+ty*size,min(left+(tx+1)*size,right),min(top+(ty+1)*size,bottom))
        image=raster(cache,objects,rect);image.save(tiles/f'{tx}_{ty}.png')
        px,py=round(tx*size*scale),round(ty*size*scale)
        px1,py1=round((tx*size+image.width)*scale),round((ty*size+image.height)*scale)
        if px1>px and py1>py:preview.paste(image.convert('RGB').resize((px1-px,py1-py),Image.Resampling.LANCZOS),(px,py))
        seen+=1
        if seen%50==0:print(f'level {manifest["level"]}: {seen}/{len(buckets)} tiles, {time.time()-start:.0f}s',flush=True)
    preview.save(leveldir/'overview.jpg',quality=94,subsampling=0)
    public={k:v for k,v in manifest.items()if k!='objects'}
    public.update(tile_size=size,tile_count=len(buckets),tiles=[list(k)for k in sorted(buckets)],statistics=stats,pixel_scale='one decoded source pixel per output pixel',lighting='unlit source artwork; no runtime lighting simulation',dynamic_objects='characters, helpers and 3D effects excluded')
    dump(leveldir/'manifest.json',public);dump(leveldir/'placements.json',manifest['objects'])
    print(f'level {manifest["level"]}: {w} x {h}, {len(buckets)} tiles, {len(manifest["objects"])} objects',flush=True)
    if full:
        p=write_full_png(leveldir,manifest,size);print(f'exported {p} ({p.stat().st_size/2**20:.1f} MiB)',flush=True)
    return public


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--game',type=Path,default=DEFAULT_GAME);ap.add_argument('--out',type=Path,default=HERE/'output');ap.add_argument('--levels',default='0');ap.add_argument('--inventory',action='store_true');ap.add_argument('--tile-size',type=int,default=1024);ap.add_argument('--no-full-png',action='store_true');args=ap.parse_args()
    game=Game(args.game);args.out.mkdir(parents=True,exist_ok=True);cache=SpriteCache(game,args.out)
    levels=sorted(game.sectors)if args.levels=='all'else list(map(int,args.levels.split(',')))
    reports=[]
    for level in levels:
        manifest,stats=collect(game,cache,level)
        print(json.dumps({'level':level,'size':[manifest['width'],manifest['height']]if manifest else None,**stats}),flush=True)
        if manifest:
            if args.inventory:
                dump(args.out/f'level-{level}'/'placements.json',manifest);reports.append(stats)
            else:reports.append(render_level(cache,manifest,stats,args.out,args.tile_size,not args.no_full_png))
        dump(args.out/'assets.json',cache.meta);dump(args.out/'decode-failures.json',cache.failures);dump(args.out/'empty-assets.json',cache.empty)
    if not args.inventory:
        reports=[json.loads(p.read_text())for p in sorted(args.out.glob('level-*/manifest.json'),key=lambda p:int(p.parent.name.split('-')[1]))]
    dump(args.out/'atlas.json',{'game':'Revenant','module':'Ahkuilon','levels':reports,'game_directory':str(game.path)})
if __name__=='__main__':main()
