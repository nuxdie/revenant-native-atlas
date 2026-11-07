"""Publish verified maps to the atlas; the upload key is accepted only on hidden stdin."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import getpass
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from atlas import dump
from .publish_pack import prepare

PART = 16 * 1024 * 1024
VERIFY_PART = 4 * 1024 * 1024
USER_AGENT = 'RevenantAtlasPublisher/1.0'


class Publisher:
    def __init__(self, base, secret, state):
        self.base = base.rstrip('/')
        self.secret = secret
        self.state = state
        self.verified = json.loads(state.read_text()) if state.exists() else {}

    def url(self, action, key, **query):
        return self.base + '/api/upload?' + urllib.parse.urlencode(dict(action=action, key=key, **query))

    def request(self, action, key, method='GET', data=None, headers=None, missing=False, **query):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
            headers = {**(headers or {}), 'Content-Type': 'application/json'}
        request = urllib.request.Request(self.url(action, key, **query), data=data, method=method,
            headers={'Authorization': 'Bearer ' + self.secret, 'User-Agent': USER_AGENT, **(headers or {})})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if missing and exc.code == 404:
                    return None
                if exc.code < 429 or attempt == 4:
                    raise RuntimeError(f'{action}: HTTP {exc.code} for {key}') from None
            except (OSError, TimeoutError):
                if attempt == 4:
                    raise RuntimeError(f'{action}: network failure for {key}') from None
            print(f'Retrying {action} for {key} (attempt {attempt+2}/5)',flush=True)
            time.sleep(min(2 ** attempt, 16))

    def verify(self, item):
        key = item['key']
        marker = self.base + '/' + key
        if self.verified.get(marker) == item['sha256']:
            return
        digest = hashlib.sha256()
        count = 0
        for offset in range(0,item['size'],VERIFY_PART):
            length=min(VERIFY_PART,item['size']-offset)
            print(f'Verifying remote bytes {offset}-{offset+length-1}: {key}',flush=True)
            request=urllib.request.Request(self.url('read',key),headers={
                'Authorization':'Bearer '+self.secret,'User-Agent':USER_AGENT,
                'Range':f'bytes={offset}-{offset+length-1}'})
            for attempt in range(3):
                try:
                    deadline=time.monotonic()+120;chunks=[];remaining=length
                    with urllib.request.urlopen(request,timeout=30)as response:
                        expected=f'bytes {offset}-{offset+length-1}/{item["size"]}'
                        if response.status!=206 or response.headers.get('Content-Range')!=expected:
                            raise ValueError(f'Remote verification range differs: {key}')
                        while remaining:
                            if time.monotonic()>deadline:raise TimeoutError('Remote range verification stalled')
                            block=response.read1(min(64*1024,remaining))
                            if not block:raise OSError('Remote range ended before its recorded length')
                            chunks.append(block);remaining-=len(block)
                    data=b''.join(chunks);break
                except(OSError,TimeoutError):
                    if attempt==2:raise RuntimeError(f'Remote range verification failed: {key}, offset {offset}')from None
                    time.sleep(2**attempt)
            digest.update(data);count+=len(data)
        if count != item['size'] or digest.hexdigest() != item['sha256']:
            raise RuntimeError(f'Remote bytes differ: {key}')
        self.verified[marker] = item['sha256']
        dump(self.state, self.verified)
        print(f'Remote bytes verified: {key}',flush=True)

    def upload(self, item):
        key, size, sha = item['key'], item['size'], item['sha256']
        print(f'Checking remote object: {key}',flush=True)
        existing = self.request('head', key, missing=True)
        if existing != dict(size=size, sha256=sha):
            print(f'Uploading {key}: {size:,} bytes', flush=True)
            path = Path(item['path'])
            if size <= PART:
                result = self.request('put', key, method='PUT', data=path.read_bytes(), headers={'X-Content-SHA256': sha})
            else:
                upload_id = self.request('start', key, method='POST', data=dict(size=size, sha256=sha))['uploadId']
                def part(number):
                    with path.open('rb') as stream:
                        stream.seek((number - 1) * PART)
                        data = stream.read(PART)
                    return self.request('part', key, method='PUT', data=data, id=upload_id, part=number)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    parts = list(pool.map(part, range(1, (size + PART - 1) // PART + 1)))
                result = self.request('complete', key, method='POST', data=dict(parts=parts), id=upload_id)
                # R2's hosted multipart completion can omit custom metadata;
                # the completed object's HEAD is the authoritative record.
                if result != dict(size=size, sha256=sha):
                    result = self.request('head', key)
            if result != dict(size=size, sha256=sha):
                raise RuntimeError(f'Remote metadata differs: {key}')
            self.verified.pop(self.base + '/' + key, None)
        self.verify(item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    secret = getpass.getpass('Atlas upload key (hidden): ')
    publisher = Publisher(args.url, secret, Path('runtime/publication/remote-verified.json'))
    while True:
        try:
            manifest = prepare()
            # prepare always places the catalog last, after all files it references.
            for item in manifest['uploads']:
                publisher.upload(item)
            print(f'PUBLIC: {manifest["levels"]}/{manifest["expected_levels"]} maps, all remote object hashes verified', flush=True)
            dump(Path('runtime/publication/published.json'), dict(levels=manifest['levels'], url=args.url, verified_at=time.time()))
            if manifest['levels'] == manifest['expected_levels'] or not args.watch:
                break
        except Exception as exc:
            print(f'Publish retry: {type(exc).__name__}: {exc}', flush=True)
            if not args.watch:
                raise
        time.sleep(30)


if __name__ == '__main__':
    main()
