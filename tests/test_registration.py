import unittest
import hashlib
import json
from pathlib import Path
import tempfile
import numpy as np
from PIL import Image
from native.audit import audit,registered_overlap,load_native_reference
from native.plan import camera_for_core


class NativeRegistrationTests(unittest.TestCase):
    def test_authored_background_crop_requires_every_interior_view(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory)
            (root/'captures').mkdir();(root/'temporal').mkdir()
            path=root/'captures/0_0.png';Image.new('RGB',(640,340),(20,40,60)).save(path)
            Image.new('L',(640,340)).save(root/'temporal/0_0.png')
            state=dict(camera=list(camera_for_core(0,0)),level=51,scroll=[-64,-42],
                source_png_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                visibility_profile='gameplay_2d_and_3d',shadow_blend_profile='rgb565_black_alpha_to_argb1555_v1',
                lighting_mode='real_time_grid')
            path.with_suffix('.json').write_text(json.dumps(state))
            plan=dict(level=51,cores=[[0,0]],bounds=[0,0,512,256])
            p=root/'plan.json';p.write_text(json.dumps(plan))
            self.assertEqual(audit(root,full=False)['acceptance'],'review_required')
            plan.update(background_crop=True,background_effects=['labback']);p.write_text(json.dumps(plan))
            report=audit(root,full=False)
            self.assertNotEqual(report['acceptance'],'review_required')
            self.assertEqual(report['native_background_crop_boundaries'],4)
            plan['bounds']=[0,0,1024,256];p.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError,'uncaptured interior'):audit(root,full=False)

    def test_edge_recovery_chain_keeps_ordinary_anchor_and_rejects_cycles_or_corruption(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);refs=root/'registration-references';refs.mkdir()
            plan=dict(cores=[[0,0],[1,0],[2,0]],level=31,executable_sha256='retail',time_of_day_minutes=720)
            image=Image.new('RGB',(640,340),(20,40,60));mask=Image.new('L',image.size)
            keys=[]
            for cx in range(3):
                name=f'{cx}_0';temporary=refs/'image.png';image.save(temporary)
                motion=refs/'mask.png';mask.save(motion)
                sha=hashlib.sha256(temporary.read_bytes()).hexdigest()
                key=name+'-'+sha[:16]+'-'+hashlib.sha256(motion.read_bytes()).hexdigest()[:12]
                temporary.replace(refs/f'{key}.png');motion.replace(refs/f'{key}-motion.png')
                camera=list(camera_for_core(cx,0))if cx==0 else [1000+cx*256,1000-cx*256,1154]
                scroll=[cx*512-64,-42]
                state=dict(provider='original_retail_1.22L',executable_sha256='retail',level=31,
                    time_of_day_minutes=720,source_png_sha256=sha,camera=camera,scroll=scroll,
                    screen_frame=1,capture_end_screen_frame=33,visibility_profile='gameplay_2d_and_3d',
                    shadow_blend_profile='retail_original_raster',lighting_mode='real_time_grid')
                if cx:state.update(source_registration='native_raised_core_v1',requested_camera=camera,
                    capture_end_camera=camera,capture_end_scroll=scroll,
                    registration_reference=f'{cx-1}_0',registration_reference_key=keys[-1])
                (refs/f'{key}.json').write_text(json.dumps(state));keys.append(key)
            load_native_reference(root,keys[2],'2_0',plan)
            p=refs/f'{keys[0]}.json';original=p.read_text();state=json.loads(original)
            state.update(source_registration='native_raised_core_v1',camera=[1000,1000,864],
                requested_camera=[1000,1000,864],capture_end_camera=[1000,1000,864],capture_end_scroll=[-64,-42],
                registration_reference='0_0',registration_reference_key=keys[0])
            p.write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError,'cyclic'):load_native_reference(root,keys[2],'2_0',plan)
            p.write_text(original)
            Image.new('RGB',(640,340),(20,40,61)).save(refs/f'{keys[0]}.png')
            with self.assertRaisesRegex(ValueError,'snapshot differs'):load_native_reference(root,keys[2],'2_0',plan)

    def test_observed_native_scroll_aligns_without_resampling(self):
        y,x=np.mgrid[:400,:800]
        world=np.stack((x%251,y%241,(x+y)%239),axis=2).astype('uint8')
        a=world[:340,:640];b=world[42:382,64:704];mask=np.zeros((340,640),bool)
        self.assertGreater(registered_overlap(b,mask,[64,42],a,mask,[0,0]),1000)
        with self.assertRaisesRegex(ValueError,'does not match'):
            registered_overlap(b,mask,[65,42],a,mask,[0,0])
        changed=b.copy();changed[100,100,0]^=1
        with self.assertRaisesRegex(ValueError,'does not match'):
            registered_overlap(changed,mask,[64,42],a,mask,[0,0])

    def test_blank_overlap_does_not_establish_geometry_registration(self):
        blank=np.zeros((340,640,3),np.uint8);mask=np.zeros((340,640),bool)
        with self.assertRaisesRegex(ValueError,'does not match'):
            registered_overlap(blank,mask,[64,42],blank,mask,[0,0])

    def test_culling_recovery_keeps_real_foreground_exact(self):
        reference=np.full((340,640,3),[20,40,60],np.uint8);reference[50:100,50:100]=0
        complete=np.full_like(reference,[20,40,60]);mask=np.zeros((340,640),bool)
        with self.assertRaises(ValueError):registered_overlap(complete,mask,[0,0],reference,mask,[0,0])
        self.assertGreater(registered_overlap(complete,mask,[0,0],reference,mask,[0,0],recover_black=True),1000)
        complete[150,150,0]^=1
        with self.assertRaises(ValueError):registered_overlap(complete,mask,[0,0],reference,mask,[0,0],recover_black=True)
