"""Exercise tiled BigTIFF with sparse coverage and partial edge tiles."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
from native.bigtiff import build,verify


class BigTIFFTests(unittest.TestCase):
    def test_lossless_sparse_rgb_and_partial_edges(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);(root/'tiles').mkdir()
            meta=dict(width=35,height=19,tile_size=16)
            (root/'manifest.json').write_text(json.dumps(meta))
            (root/'validation.json').write_text(json.dumps(dict(acceptance='native_pixels_verified',full_png_sha256='a'*64)))
            expected=np.zeros((19,35,3),dtype=np.uint8)
            for y in range(2):
                for x in range(3):
                    if(x,y)==(1,0):continue
                    h=min(16,19-y*16);w=min(16,35-x*16)
                    yy,xx=np.indices((h,w));rgb=np.stack([(xx*19+x*81)%256,(yy*29+y*93)%256,(xx+yy*17+71)%256],axis=2).astype(np.uint8)
                    Image.fromarray(rgb).save(root/'tiles'/f'{x}_{y}.png');expected[y*16:y*16+h,x*16:x*16+w]=rgb
            record=build(root);path=root/'full-resolution.tif'
            self.assertEqual(path.read_bytes()[:8],b'II+\0\x08\0\0\0')
            self.assertEqual(record['all_rgb_pixels_equal_native_tiles'],35*19)
            with Image.open(path)as image:
                self.assertEqual(image.size,(35,19));np.testing.assert_array_equal(np.asarray(image),expected)
            # Re-reading must catch a changed source tile, including edge pixels.
            Image.new('RGB',(3,3),(17,29,41)).save(root/'tiles/2_1.png')
            with self.assertRaisesRegex(ValueError,'changed RGB'):verify(path,root,meta)


if __name__=='__main__':unittest.main()
