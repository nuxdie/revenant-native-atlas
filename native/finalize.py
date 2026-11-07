"""Write and verify the full PNG after a successful native tile audit."""
import argparse
import hashlib
import json
from pathlib import Path

from atlas import dump,write_full_png
from audit import verify_png,verify_samples


def finalize(root):
    meta=json.loads((root/'manifest.json').read_text())
    report=json.loads((root/'validation.json').read_text())
    if report['acceptance']=='review_required':raise ValueError('Resolve native audit findings before finalizing')
    path=write_full_png(root,meta,meta['tile_size'])
    if verify_png(path)!=(meta['width'],meta['height']):raise ValueError('Full PNG dimensions differ')
    samples=verify_samples(root,meta)
    with path.open('rb')as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    report.update(full_png_crc='verified',full_png_samples_equal_tiles=samples,full_png_sha256=digest)
    report.pop('full_png_zip',None)
    dump(root/'validation.json',report)
    print(f'{path}: CRC, dimensions and {samples:,} sampled tile pixels verified',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args()
    finalize(a.directory)
