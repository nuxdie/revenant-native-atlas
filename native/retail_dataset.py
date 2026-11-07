"""Index the actual retail packs, including their authored day/night areas."""
import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import re
import struct
from zipfile import ZipFile

from atlas import dump, project, sector_position
from .plan import positions, CORE_W, CORE_H
from .retail import DATA, EXE_SHA256, ROOT


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parse_areas(text):
    areas=[]
    for match in re.finditer(r'^AREA\s+"([^"]+)"\s*BEGIN(.*?)^\s*END', text, re.I|re.S|re.M):
        body=match[2]
        level=re.search(r'^\s*LEVEL\s+(\d+)',body,re.I|re.M)
        if not level:
            continue
        areas.append(dict(name=match[1],level=int(level[1]),
            day_night=bool(re.search(r'^\s*NIGHTAMB(?:LIGHT|COLOR)\b',body,re.I|re.M))))
    return areas


def index(data=DATA, out=ROOT/'runtime/retail-index'):
    data, out=Path(data),Path(out)
    if file_digest(data/'Revenant.exe') != EXE_SHA256:
        raise ValueError('Unrecognized retail executable; inspect its data before indexing')
    levels=[];packs=[];excluded=[];unresolved=[]
    with ZipFile(data/'imagery.rvi')as archive:
        names={name.casefold():name for name in archive.namelist()}
        text=archive.read(names['class.def']).decode('cp1252')
    known_ids={int(uid,16)for uid in re.findall(r'^\s*"[^"]*"\s+"[^"]*"\s+(0x[\da-f]+)',text,re.I|re.M)}
    for archive_path in sorted((data/'Modules').glob('*.rvm')):
        module=archive_path.stem
        target=out/'Modules'/module
        objects=defaultdict(list)
        with ZipFile(archive_path) as archive:
            names={name.casefold():name for name in archive.namelist()}
            area_text=archive.read(names['area.def']).decode('cp1252') if 'area.def' in names else ''
            areas=parse_areas(area_text)
            for member in archive.infolist():
                if member.is_dir() or not re.fullmatch(r'Map/\d+_\d+_\d+\.dat',member.filename,re.I):
                    continue
                path=target/member.filename
                level=int(path.stem.split('_')[0])
                sector_data=archive.read(member);version=struct.unpack_from('<i',sector_data,4)[0]
                for obj in positions(path,sector_data):
                    if obj['flags'] & (128|256):
                        continue
                    pos=sector_position(path,*obj['pos'])
                    if obj['uid']not in known_ids:
                        unresolved.append(dict(module=module,sector=member.filename,level=level,
                            uid=hex(obj['uid']),object_class=obj['class'],position=list(pos),
                            map_version=version,native_load='fatal_missing_type_without_block_size'if version<4 else'skipped_missing_type'))
                    if not (0<=pos[0]<=32768 and 0<=pos[1]<=32768 and -4096<=pos[2]<=32768):
                        excluded.append(dict(module=module,sector=member.filename,uid=obj['uid'],
                            name=obj['name'],position=list(pos),reason='off-world authored placement'))
                        continue
                    objects[level].append(dict(obj,pos=list(pos)))
        for level,items in sorted(objects.items()):
            if not items:
                continue
            cores=set()
            for obj in items:
                sx,sy,_=project(*obj['pos'])
                radius=1024 if obj['class'] in (11,12,25) else 512
                for cy in range((sy-radius)//CORE_H,(sy+radius)//CORE_H+1):
                    for cx in range((sx-radius)//CORE_W,(sx+radius)//CORE_W+1):
                        cores.add((cx,cy))
            bounds=[min(x for x,y in cores)*CORE_W,min(y for x,y in cores)*CORE_H,
                    (max(x for x,y in cores)+1)*CORE_W,(max(y for x,y in cores)+1)*CORE_H]
            rows=defaultdict(list)
            for x,y in cores:rows[y].append(x)
            ordered=[[x,y]for i,y in enumerate(sorted(rows))for x in sorted(rows[y],reverse=bool(i%2))]
            current_areas=[a for a in areas if a['level']==level]
            has_night=any(a['day_night']for a in current_areas)
            plan=dict(module=module,level=level,names=list(dict.fromkeys(a['name']for a in current_areas))or[module],
                bounds=bounds,width=bounds[2]-bounds[0],height=bounds[3]-bounds[1],
                core_size=[CORE_W,CORE_H],viewport=[640,340],core_count=len(cores),cores=ordered,
                retained_source_objects=len(items),source_objects_by_class=dict(Counter(str(o['class'])for o in items)),
                dataset='GOG 1.22L',executable_sha256=EXE_SHA256,
                variants=['day','night']if has_night else ['fixed'])
            # All installed retail modules use distinct drawable level IDs.
            if any(p['level']==level for p in levels):
                raise ValueError(f'Level collision across modules: {level}')
            dump(out/'plans'/f'level-{level}.json',plan)
            levels.append({k:v for k,v in plan.items()if k!='cores'})
        packs.append(dict(module=module,sha256=file_digest(archive_path),bytes=archive_path.stat().st_size))
    result=dict(dataset='GOG 1.22L',executable_sha256=EXE_SHA256,packs=packs,
        imagery_sha256=file_digest(data/'imagery.rvi'),resources_sha256=file_digest(data/'resources.rvr'),
        levels=sorted(levels,key=lambda m:m['level']),excluded_placements=excluded,unresolved_types=unresolved,
        expected_levels=len(levels),expected_maps=sum(len(m['variants'])for m in levels))
    dump(out/'dataset.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=DATA)
    p.add_argument('--out',type=Path,default=ROOT/'runtime/retail-index')
    args=p.parse_args();result=index(args.data,args.out)
    print(f"{result['expected_levels']} retail levels, {result['expected_maps']} lighting variants")
    for level in result['levels']:
        print(level['level'],level['module'],level['variants'],level['core_count'],level['width'],level['height'])
