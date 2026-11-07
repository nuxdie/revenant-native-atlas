"""Create a private diagnostic pack; omitted authored objects prevent exact publication."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from atlas import dump
from .plan import positions
from .publish_pack import digest


def omit_unmapped_v1(path,raw,uids):
    """Replace only unmapped v1 tile slots with the format's empty-slot marker.

    All surviving record bytes, count, and order are retained. This recovers
    readable scenery, not the absent definitions or the omitted artwork.
    """
    if len(raw)<12 or raw[:4]!=b'MAP 'or struct.unpack_from('<i',raw,4)[0]!=1:
        raise ValueError('Diagnostic recovery accepts only version-1 sectors')
    count=struct.unpack_from('<i',raw,8)[0]
    if not 0<=count<100000:raise ValueError('Invalid legacy slot count')
    offset=12;parts=[raw[:12]];removed=[]
    try:
        for slot in range(count):
            start=offset;cls=struct.unpack_from('<h',raw,offset)[0];offset+=2
            if cls<0:parts.append(raw[start:offset]);continue
            uid=struct.unpack_from('<I',raw,offset)[0];offset+=4
            length=raw[offset];offset+=1+length
            flags,x,y,z=struct.unpack_from('<Iiii',raw,offset)
            offset+=16+12+1+1+12  # base, velocity, state, health, rotation
            if flags&4:offset+=19
            if cls==10:offset+=4
            if offset>len(raw):raise ValueError('Truncated legacy record')
            if uid in uids:
                if cls!=9:raise ValueError('Only unmapped tile records may be omitted')
                parts.append(struct.pack('<h',-1))
                removed.append(dict(slot=slot,uid=hex(uid),position=[x,y,z],byte_range=[start,offset],
                    original_record_sha256=hashlib.sha256(raw[start:offset]).hexdigest()))
            else:parts.append(raw[start:offset])
    except(IndexError,struct.error)as exc:raise ValueError('Truncated legacy record')from exc
    if offset!=len(raw):raise ValueError('Legacy sector has trailing bytes')
    result=b''.join(parts)
    surviving=[o for o in positions(Path(path),raw)if o['uid']not in uids]
    if surviving!=list(positions(Path(path),result)):
        raise ValueError('Diagnostic recovery changed surviving placements')
    return result,removed


def recover_archive(source,destination,dataset):
    source,destination=Path(source),Path(destination)
    if destination.exists():raise ValueError('Diagnostic destination already exists')
    actual=digest(source)
    pack=next(p for p in dataset['packs']if p['module']==source.stem)
    if actual!=pack['sha256']:raise ValueError('Source module differs from the indexed pack')
    unresolved=[r for r in dataset['unresolved_types']if r['module']==source.stem]
    uids={int(r['uid'],16)for r in unresolved};sectors={r['sector']for r in unresolved};reports=[]
    destination.parent.mkdir(parents=True,exist_ok=True);temporary=destination.with_suffix('.tmp')
    try:
        with ZipFile(source)as original,ZipFile(temporary,'w')as output:
            for info in original.infolist():
                raw=original.read(info.filename)
                if info.filename in sectors:
                    fixed,omitted=omit_unmapped_v1(info.filename,raw,uids)
                    reports.append(dict(sector=info.filename,source_sha256=hashlib.sha256(raw).hexdigest(),
                        recovery_sha256=hashlib.sha256(fixed).hexdigest(),omitted=omitted));raw=fixed
                output.writestr(info,raw)
        count=sum(len(r['omitted'])for r in reports)
        if count!=len(unresolved):raise ValueError('Omission count differs from indexed placements')
        temporary.replace(destination)
    finally:temporary.unlink(missing_ok=True)
    report=dict(status='private_partial_recovery_not_eligible_for_exact_release',source_pack_sha256=actual,
        recovery_pack_sha256=digest(destination),omitted_placements=count,sectors=reports)
    dump(destination.parent/'recovery.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--diagnostic-omissions',action='store_true',required=True,
        help='Acknowledge that missing placements are omitted; this cannot produce an exact release')
    a=p.parse_args();r=recover_archive(a.source,a.destination,json.loads(a.dataset.read_text()))
    print(f"Private diagnostic pack: {r['omitted_placements']} omitted placements; not eligible for exact publication")
