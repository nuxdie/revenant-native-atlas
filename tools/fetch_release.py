#!/usr/bin/env python3
"""Download an independently hosted atlas release; verify every selected file."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

REPOSITORY='nuxdie/revenant-native-atlas'


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RevenantAtlasMirror/1.0'}),timeout=180)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',default='latest',help='GitHub release tag, or latest')
    parser.add_argument('--output',type=Path,default=Path('data'))
    parser.add_argument('--levels',help='Comma-separated levels; default all')
    parser.add_argument('--formats',default='png,tif',help='png,tif; empty string for viewer only')
    parser.add_argument('--viewer',action='store_true',help='Also download native tile packs, indexes and overviews')
    args=parser.parse_args();selected=set(map(int,args.levels.split(',')))if args.levels else None
    formats=set(filter(None,args.formats.split(',')))
    if not formats<=set(('png','tif')):parser.error('formats must be png and/or tif')
    endpoint=f'https://api.github.com/repos/{REPOSITORY}/releases/'+('latest'if args.release=='latest'else'tags/'+args.release)
    with request(endpoint)as response:release=json.load(response)
    assets={a['name']:a for a in release['assets']}
    with request(assets['release-manifest.json']['browser_download_url'])as response:manifest=json.load(response)
    args.output.mkdir(parents=True,exist_ok=True)
    checked=[]
    for item in manifest['files']:
        level=item.get('level');kind=item['kind']
        if level is not None and selected is not None and level not in selected:continue
        if kind not in formats and not(args.viewer and kind in('tilepack','tileindex','overview'))and kind!='catalog':continue
        target=args.output/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists()and target.stat().st_size==item['bytes']:
            with target.open('rb')as f:existing=hashlib.file_digest(f,'sha256').hexdigest()
            if existing==item['sha256']:print('Verified existing',target,flush=True);checked.append(item);continue
        partial=target.with_suffix(target.suffix+'.part');digest=hashlib.sha256();size=0
        with request(assets[item['asset']]['browser_download_url'])as response,partial.open('wb')as out:
            while block:=response.read(1024*1024):out.write(block);digest.update(block);size+=len(block)
        if size!=item['bytes']or digest.hexdigest()!=item['sha256']:
            partial.unlink(missing_ok=True);raise RuntimeError('Download differs from release manifest: '+item['asset'])
        partial.replace(target);checked.append(item);print('Downloaded and verified',target,flush=True)
    if args.viewer and selected is not None:
        path=args.output/'catalog.json';catalog=json.loads(path.read_text());catalog['levels']=[m for m in catalog['levels']if m['level']in selected]
        path.write_text(json.dumps(catalog,indent=2)+'\n')
    print(f'{len(checked)} release files verified in {args.output}',flush=True)


if __name__=='__main__':main()
