"""Publish PNG-only metadata and remove its redundant, verified map ZIPs."""
import getpass
import json
from pathlib import Path
import time

from atlas import dump
from .publish_pack import prepare
from .publish_upload import Publisher


def main():
    base='https://revenant-native-atlas-2026.lithepond4.chatgpt.site'
    publisher=Publisher(base,getpass.getpass('Atlas upload key (hidden): '),Path('runtime/publication/remote-verified.json'))
    manifest=prepare()
    assert manifest['levels']==33
    for item in manifest['uploads']:publisher.upload(item)
    archive=Path('runtime/publication/retired-zip-objects.json');retired=json.loads(archive.read_text())
    deleted=[]
    for item in retired['objects']:
        key=item['key'];assert key.endswith('/full-resolution.zip')
        png=key[:-3]+'png';expected=publisher.verified.get(base+'/'+png)
        assert expected,'The matching public PNG has no complete readback verification'
        head=publisher.request('head',png)
        assert head['sha256']==expected and head['size']>0
        publisher.request('delete-zip',key,method='POST',data={})
        assert publisher.request('head',key,missing=True)is None
        deleted.append(key)
        local=Path(item['path'])
        if local.name=='full-resolution.zip'and local.is_file():local.unlink()
        print('Removed redundant ZIP:',key,flush=True)
    dump(Path('runtime/publication/zip-cleanup.json'),dict(deleted=deleted,matching_png_hashes_verified=True,finished_at=time.time()))
    dump(Path('runtime/publication/published.json'),dict(levels=33,url=base,png_only=True,verified_at=time.time()))
    print('PNG-only publication complete; 33 redundant ZIPs removed',flush=True)


if __name__=='__main__':main()
