import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from native.audit import verify_ownership,audit
from native.edges import verify_edges
from native.recut import Cut,recut_pair
from native.plan import camera_for_core


class RecutTests(unittest.TestCase):
    def test_fractional_core_keeps_exact_integer_camera_registration(self):
        self.assertEqual(camera_for_core(1.125,-2.25),(-32,-864,0))
        with self.assertRaises(ValueError):camera_for_core(1/512,-2)

    def test_extra_viewport_is_audited_and_wrong_registration_rejected(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory)
            for folder in ['captures','temporal','tiles','ownership']:(root/folder).mkdir()
            image=np.full((340,640,3),20,np.uint8);path=root/'captures/bridge.png';Image.fromarray(image).save(path)
            sha=hashlib.sha256(path.read_bytes()).hexdigest()
            Image.fromarray(np.zeros((340,640),np.uint8)).save(root/'temporal/bridge.png')
            Image.fromarray(image[:64,:64]).save(root/'tiles/0_0.png')
            Image.fromarray(np.ones((64,64),np.uint16)).save(root/'ownership/0_0.png')
            state=dict(source_registration='native_camera_bridge_v1',core=[.125,.1640625],level=0,camera=[330,10,0],scroll=[0,0],
                       source_png_sha256=sha,capture_recipe='console_redraw_bg_barrier_v3',screen_frame=1,capture_end_screen_frame=2,
                       visibility_profile='gameplay_2d_and_3d',shadow_blend_profile='rgb565_black_alpha_to_argb1555_v1',lighting_mode='real_time_grid')
            path.with_suffix('.json').write_text(json.dumps(state))
            (root/'ownership-sources.json').write_text(json.dumps([dict(id=1,capture='bridge',scroll=[0,0],sha256=sha)]))
            meta=dict(level=0,bounds=[0,0,64,64],width=64,height=64,tiles=[[0,0]],tile_size=1024,ownership='ownership-sources.json')
            (root/'manifest.json').write_text(json.dumps(meta));(root/'quilting.json').write_text('{}')
            (root/'plan.json').write_text(json.dumps(dict(level=0,cores=[],bounds=meta['bounds'])))
            report=audit(root,full=False)
            self.assertEqual(report['captures'],1);self.assertNotEqual(report['acceptance'],'review_required')
            state['scroll']=[1,0];path.with_suffix('.json').write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError,'Bridge camera registration mismatch'):audit(root,full=False)

    def test_residual_network_finds_minimum_cut(self):
        edges=[(0,1,3),(0,2,2),(1,2,1),(1,3,2),(2,3,3)]
        graph=Cut(4)
        for a,b,capacity in edges:graph.edge(a,b,capacity)
        side=graph.reachable(0,3)
        self.assertTrue(side[0]);self.assertFalse(side[3])
        self.assertEqual(sum(cap for a,b,cap in edges if side[a]and not side[b]),5)

    def test_recut_removes_split_object_with_exact_source_pixels(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory)
            for folder in ['captures','temporal','tiles','ownership']:(root/folder).mkdir()
            a=np.full((340,640,3),20,np.uint8);b=a.copy();b[20:44,20:44]=[180,80,30]
            records=[]
            for ident,(name,array)in enumerate([('a',a),('b',b)],1):
                path=root/'captures'/f'{name}.png';Image.fromarray(array).save(path)
                Image.fromarray(np.zeros((340,640),np.uint8)).save(root/'temporal'/path.name)
                records.append(dict(id=ident,capture=name,scroll=[0,0],sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            (root/'ownership-sources.json').write_text(json.dumps(records))
            rgb=a[:64,:64].copy();rgb[:,32:]=b[:64,32:64]
            own=np.ones((64,64),np.uint16);own[:,32:]=2
            Image.fromarray(rgb).save(root/'tiles/0_0.png');Image.fromarray(own).save(root/'ownership/0_0.png')
            meta=dict(bounds=[0,0,64,64],tiles=[[0,0]],tile_size=1024)
            self.assertGreater(verify_edges(root,meta)['unmeasured_edges_requiring_review'],0)
            result=recut_pair(root,meta,(1,2))
            self.assertGreater(result['changed'],0)
            self.assertEqual(verify_edges(root,meta)['unmeasured_edges_requiring_review'],0)
            self.assertEqual(verify_ownership(root,meta)[0],4096)


if __name__=='__main__':unittest.main()
