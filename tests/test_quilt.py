import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image

from native.quilt import quilt,choose_patch
from native.audit import verify_ownership
from native.edges import verify_edges


def world(rect):
    left,top,right,bottom=rect
    y,x=np.mgrid[top:bottom,left:right]
    return np.stack((x%251,y%241,(x+y)%239),axis=2).astype(np.uint8)


class QuiltTests(unittest.TestCase):
    def test_review_source_ids_include_boundaries_beyond_sample_limit(self):
        with tempfile.TemporaryDirectory()as td:
            root=Path(td)
            for folder in ('captures','temporal','tiles','ownership'):(root/folder).mkdir()
            sources=[];result=np.zeros((340,640,3),np.uint8);owners=np.zeros((340,640),np.uint16)
            for ident,color,l,r in [(1,(240,0,0),0,200),(2,(0,240,0),200,400),(3,(0,0,240),400,640)]:
                frame=np.full((340,640,3),color,np.uint8)
                Image.fromarray(frame).save(root/f'captures/{ident}.png')
                Image.new('L',(640,340)).save(root/f'temporal/{ident}.png')
                result[:,l:r]=frame[:,l:r];owners[:,l:r]=ident
                sources.append(dict(id=ident,capture=str(ident),scroll=[0,0]))
            Image.fromarray(result).save(root/'tiles/0_0.png');Image.fromarray(owners).save(root/'ownership/0_0.png')
            (root/'ownership-sources.json').write_text(json.dumps(sources))
            report=verify_edges(root,dict(bounds=[0,0,640,340],tiles=[[0,0]]))
            self.assertEqual(len(report['static_samples']),40)
            self.assertEqual(report['static_owner_ids'],[1,2,3])

    def test_animation_at_either_kept_edge_endpoint_is_reported(self):
        with tempfile.TemporaryDirectory()as td:
            root=Path(td)
            for directory in ('captures','temporal','tiles','ownership'):(root/directory).mkdir()
            a=np.zeros((340,640,3),np.uint8);a[:]=[240,0,0]
            b=np.zeros_like(a);b[:]=[0,0,240]
            Image.fromarray(a).save(root/'captures/a.png');Image.fromarray(b).save(root/'captures/b.png')
            mask=np.zeros((340,640),np.uint8);mask[:,319]=255
            Image.fromarray(mask).save(root/'temporal/a.png');Image.fromarray(mask*0).save(root/'temporal/b.png')
            merged=a.copy();merged[:,320:]=b[:,320:];Image.fromarray(merged).save(root/'tiles/0_0.png')
            owners=np.ones((340,640),np.uint16);owners[:,320:]=2;Image.fromarray(owners).save(root/'ownership/0_0.png')
            (root/'ownership-sources.json').write_text(json.dumps([dict(id=1,capture='a',scroll=[0,0]),dict(id=2,capture='b',scroll=[0,0])]))
            report=verify_edges(root,dict(bounds=[0,0,640,340],tiles=[[0,0]]))
            self.assertEqual(report['edges_not_reproduced_by_either_native_source'],340)
            self.assertEqual(report['measured_animation_edges'],340)
            self.assertEqual(report['unmeasured_edges_requiring_review'],0)
    def test_four_viewports_preserve_world_pixels_and_trace_each_owner(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'captures').mkdir()
            coords=[[-1,-1],[0,-1],[-1,0],[0,0]]
            plan=dict(level=0,cores=coords,bounds=[-512,-256,512,256],width=1024,height=512)
            (root/'plan.json').write_text(json.dumps(plan))
            meta={k:v for k,v in plan.items()if k!='cores'};meta['tile_size']=1024
            (root/'manifest.json').write_text(json.dumps(meta))
            for cx,cy in coords:
                x,y=cx*512-64,cy*256-42
                path=root/'captures'/f'{cx}_{cy}.png'
                Image.fromarray(world((x,y,x+640,y+340))).save(path)
                path.with_suffix('.json').write_text(json.dumps(dict(scroll=[x,y],source_png_sha256=hashlib.sha256(path.read_bytes()).hexdigest())))
            report=quilt(root)
            self.assertEqual(report['nonmatching_cut_pixels'],0)
            with Image.open(root/'full-resolution.png') as im:
                self.assertTrue(np.array_equal(np.array(im),world(plan['bounds'])))
            meta=json.loads((root/'manifest.json').read_text())
            checked,_=verify_ownership(root,meta)
            self.assertEqual(checked,1024*512)
            path=root/'tiles/0_0.png'
            with Image.open(path)as im:bad=np.array(im)
            bad[0,0,1]^=1;Image.fromarray(bad).save(path)
            with self.assertRaisesRegex(ValueError,'changes original-game source pixels'):
                verify_ownership(root,meta)

    def test_cut_avoids_splitting_two_animation_poses(self):
        old=np.full((340,640,3),20,np.uint8);new=old.copy()
        old[100:180,60:100]=[255,0,0]
        new[100:180,80:120]=[0,0,255]
        owners=np.zeros((340,640),np.uint16);owners[:,:128]=1
        choose,cuts=choose_patch(old,new,owners,True,False)
        merged=old.copy();merged[choose]=new[choose]
        red=np.all(merged==[255,0,0],axis=2).sum()
        blue=np.all(merged==[0,0,255],axis=2).sum()
        self.assertEqual(sum(c['nonmatching_cut_pixels']for c in cuts),0)
        self.assertTrue((red==3200 and blue==0)or(red==0 and blue==3200))

if __name__=='__main__':unittest.main()
