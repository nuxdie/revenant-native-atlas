"""Verify anonymous atlas viewing, resumable downloads and complete file bytes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

from atlas import dump


def request(url,**headers):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RevenantAtlasVerifier/1.0',**headers}),timeout=180)


def verify(base,partial=False,only_levels=None):
    with request(base+'/api/catalog?verification='+str(int(time.time())))as response:catalog=json.load(response)
    expected={int(p.parent.name.split('-')[1])for p in Path('output').glob('level-*/manifest.json')}
    published={m['level']for m in catalog['levels']}
    if not partial:assert published==expected,(published,expected)
    assert len(published)==len(catalog['levels'])
    manifest=json.loads(Path('runtime/publication/upload-manifest.json').read_text())
    hashes={u['key']:u['sha256']for u in manifest['uploads']}
    def level(m):
        number=m['level'];revision=m['revision'];prefix=f'releases/{revision}/level-{number}/'
        local=Path('native-output')/f'level-{number}'
        validation=json.loads((local/'validation.json').read_text())
        assert validation['acceptance']!='review_required'
        assert m['sha256']==validation['full_png_sha256']
        def file(name):return base+'/api/file?'+urllib.parse.urlencode(dict(revision=revision,level=number,name=name))
        with request(file('full-resolution.png'),Range='bytes=0-32')as r:
            data=r.read();assert r.status==206;assert r.headers['Content-Range']==f'bytes 0-32/{m["png_bytes"]}'
            assert data[:8]==b'\x89PNG\r\n\x1a\n';assert struct.unpack('>II',data[16:24])==(m['width'],m['height'])
        assert m.get('tiff_bytes') and m.get('tiff_sha256')
        with request(file('full-resolution.tif'),Range='bytes=0-31')as r:
            assert r.status==206 and r.headers['Content-Type']=='image/tiff'
            assert r.headers['Content-Range']==f'bytes 0-31/{m["tiff_bytes"]}'
            assert r.read()[:8]==b'II+\0\x08\0\0\0'
        assert 'zip_bytes' not in m and 'download_archive' not in m
        for retired in ('full-resolution.zip','validation.json'):
            try:
                with request(file(retired)):raise AssertionError('Retired file still public: '+retired)
            except urllib.error.HTTPError as exc:assert exc.code==404
        index=json.loads((Path('runtime/publication')/f'level-{number}'/'tiles.json').read_text())
        key=sorted(index['tiles'])[len(index['tiles'])//2];x,y=key.split('_')
        url=base+'/api/tile?'+urllib.parse.urlencode(dict(revision=revision,level=number,x=x,y=y))
        with request(url)as r:assert hashlib.sha256(r.read()).hexdigest()==index['tiles'][key]['sha256']
        checked={}
        for name in ['full-resolution.png','full-resolution.tif']:
            digest=hashlib.sha256();size=0
            with request(file(name))as r:
                assert r.status==200;assert 'attachment' in r.headers['Content-Disposition']
                while data:=r.read(1024*1024):digest.update(data);size+=len(data)
            assert digest.hexdigest()==hashes[prefix+name]
            assert size==m['png_bytes'if name.endswith('.png')else'tiff_bytes']
            checked[name]=dict(bytes=size,sha256=digest.hexdigest())
        print(f'Anonymous level {number}: exact tile, PNG/BigTIFF ranges and both full download hashes verified; ZIP/checks unavailable',flush=True)
        return dict(level=number,downloads=checked)
    selected=catalog['levels']if only_levels is None else[m for m in catalog['levels']if m['level']in only_levels]
    if only_levels is not None:assert {m['level']for m in selected}==only_levels
    with ThreadPoolExecutor(max_workers=4)as pool:results=list(pool.map(level,selected))
    result=dict(url=base,levels=len(results),published_levels=len(published),expected_levels=len(expected),verified_at=time.time(),results=results)
    dump(Path('runtime/publication/anonymous-verification.json'),result)
    print(f'PUBLIC VERIFICATION PASSED: {len(results)} checked, {len(published)}/{len(expected)} native maps published',flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('url');parser.add_argument('--allow-partial',action='store_true');parser.add_argument('--levels');args=parser.parse_args()
    verify(args.url.rstrip('/'),args.allow_partial,set(map(int,args.levels.split(',')))if args.levels else None)
