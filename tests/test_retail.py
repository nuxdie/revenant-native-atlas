import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from PIL import Image
from native.bigtiff import build
from native.plan import positions
from native.publish_retail import prepare
from native.retail_dataset import parse_areas
from tools.stage_retail_release import stage


class RetailTests(unittest.TestCase):
    def test_cycle_is_authored_per_area_not_assumed_for_every_level(self):
        areas=parse_areas('''AREA "Town"
BEGIN
LEVEL 0
NIGHTAMBLIGHT 35
END
AREA "Cave"
BEGIN
LEVEL 30
AMBLIGHT 12
END
''')
        self.assertEqual([(a['level'],a['day_night'])for a in areas],[(0,True),(30,False)])

    def test_retail_v15_header_and_separate_inventory_length(self):
        body=b'\x04Lamp'+struct.pack('<Iiii',1,2200,26200,160)
        record=struct.pack('<hhIhh',9,9,0x1234,len(body),0)+body
        data=struct.pack('<4siIi',b'MAP ',15,0xabcdef01,1)+record
        parsed=list(positions(Path('0_2_25.dat'),data))
        self.assertEqual(parsed[0]['pos'],[2200,26200,160])
        self.assertEqual(parsed[0]['name'],'Lamp')

    def test_publication_waits_for_both_real_lighting_files(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory)/'maps';root.mkdir();out=Path(directory)/'publication'
            (root/'dataset.json').write_text(json.dumps(dict(expected_levels=1,
                levels=[dict(level=0,variants=['day','night'])])))
            def variant(name,color):
                p=root/name/'level-0';(p/'tiles').mkdir(parents=True)
                image=Image.new('RGB',(16,16),color);image.save(p/'tiles/0_0.png');image.save(p/'full-resolution.png');image.save(p/'overview.jpg')
                sha=hashlib.sha256((p/'full-resolution.png').read_bytes()).hexdigest()
                meta=dict(level=0,variant=name,module='Ahkuilon',game_time='12:00'if name=='day'else'01:00',
                    names=['Town'],width=16,height=16,bounds=[0,0,16,16],tile_size=16,
                    tiles=[[0,0]],statistics={},provider='original_retail_1.22L')
                (p/'manifest.json').write_text(json.dumps(meta))
                (p/'validation.json').write_text(json.dumps(dict(acceptance='native_pixels_verified',
                    full_png_crc='verified',full_png_sha256=sha)))
                build(p)
            variant('day',(50,60,70));first=prepare(root,out)
            self.assertFalse(first['complete'])
            self.assertNotIn('catalog.json',[u['key']for u in first['uploads']])
            with self.assertRaisesRegex(RuntimeError,'1/2 accepted'):
                stage(root,Path(directory)/'assets',out)
            variant('night',(10,20,60));second=prepare(root,out)
            self.assertTrue(second['complete']);self.assertEqual(second['uploads'][-1]['key'],'catalog.json')
            catalog=json.loads((out/'catalog.json').read_text())
            self.assertEqual(catalog['levels'][0]['variants'][0]['variant'],'day')
            self.assertNotEqual(*[v['revision']for v in catalog['levels'][0]['variants']])
            released=stage(root,Path(directory)/'assets',out)
            self.assertEqual(released['images'],2)
            names={item['asset']for item in released['files']}
            self.assertIn('level-0-day.png',names);self.assertIn('level-0-night.tif',names)
            self.assertTrue(all(not Path(item['path']).is_absolute()for item in released['files']))


if __name__=='__main__':unittest.main()
