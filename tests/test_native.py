import struct
import tempfile
import unittest
from pathlib import Path
import numpy as np
from native.plan import positions, camera_for_core
from native.export import overlap


class NativeCaptureTests(unittest.TestCase):
    def test_actor_load_base_prefixes(self):
        # TPlayer(v>3) adds a Character version, Character(v>=3) adds
        # a Complex version, Complex(v>=1) adds a base version.
        records = []
        for cls, prefix, pos in [(12, b'\x01\x09', (120,340,5)),
                                 (11, b'\x03\x01\x09', (800,900,17)),
                                 (9, b'', (30,60,2))]:
            body = prefix+b'\x04Test'+struct.pack('<Iiii', 1, *pos)
            records.append(struct.pack('<hhIh', 9, cls, cls*10, len(body))+body)
        with tempfile.TemporaryDirectory() as td:
            f = Path(td)/'map.dat'
            f.write_bytes(struct.pack('<4sii', b'MAP ',13,3)+b''.join(records))
            parsed = list(positions(f))
        self.assertEqual([p['pos'] for p in parsed], [[120,340,5],[800,900,17],[30,60,2]])
        self.assertEqual([p['class'] for p in parsed], [12,11,9])

    def test_native_camera_inverse_at_negative_coordinates(self):
        for cx,cy in [(-63,-2),(-27,29),(54,107),(0,0)]:
            x,y,z=camera_for_core(cx,cy)
            self.assertEqual(x-y-320,cx*512-64)
            self.assertEqual((x+y)//2-170,cy*256-42)
            self.assertEqual(z,0)

    def test_seam_comparison_preserves_mismatches_and_temporal_mask(self):
        a=np.zeros((340,640,3),np.uint8);b=a.copy()
        b[0,0,1]=1
        clear=np.zeros((340,640),bool)
        result=overlap((a,clear),(b,clear),(0,0),(1,0))
        self.assertEqual(result['static_mismatches'],1)
        self.assertEqual(result['maximum_static_channel_error'],1)
        moving=clear.copy();moving[0,0]=True
        result=overlap((a,clear),(b,moving),(0,0),(1,0))
        self.assertEqual(result['static_mismatches'],0)
        self.assertEqual(result['temporal_pixels'],1)
        self.assertGreater(result['mean_absolute_channel_error'],0)

if __name__=='__main__':unittest.main()
