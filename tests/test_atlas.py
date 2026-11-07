import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import atlas


def encoded(rows):
    return bytes(4)+bytes([250,251])+b''.join(row+bytes([250,0])for row in rows)


class Codec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.d=atlas.Decoder()
    def test_lz_reads_encoded_source_instead_of_decoded_output(self):
        # First run expands to 60 output bytes; LZ refers to four *encoded*
        # bytes six bytes back, not the 60-byte expanded prefix.
        row=bytes([250,60,7,8,9,251,2,2,0])
        # source after token - distance - 4 = literal 8,9, giving 64 pixels.
        data=encoded([row]+[bytes([250,64,3])]*63)
        out=self.d.chunk(data,0)
        self.assertEqual(out[0].tolist(),[7]*60+[8,9,8,9])
        self.assertTrue(np.all(out[1:]==3))
    def test_depth_high_byte_and_transparent_skips(self):
        row=bytes([251,0,2,250,32,4,250,160])
        out=self.d.chunk(encoded([row]*64),0,True)
        self.assertTrue(np.all(out[:,:32]==516))
        self.assertTrue(np.all(out[:,32:]==0x7f7f))
    def test_malformed_color_stream_fails_closed(self):
        with self.assertRaises(atlas.FormatError):self.d.chunk(encoded([bytes([250,127,8])]*64),0)
        with self.assertRaises(atlas.FormatError):self.d.chunk(bytes(8),0)
    def test_clipped_legacy_depth_never_writes_past_destination(self):
        data=encoded([bytes([250,65,8])]*64)
        out=self.d.chunk(data,0,True)
        self.assertEqual(out.shape,(64,64))
        self.assertGreater(self.d.clipped_depth_chunks,0)


class Raster(unittest.TestCase):
    def test_rerender_removes_stale_tiles_before_full_png_assembly(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);tiles=root/'level-0/tiles';tiles.mkdir(parents=True)
            Image.new('RGBA',(2,2),(255,0,0,255)).save(tiles/'1_0.png')
            rgba=np.full((2,2,4),255,np.uint8)
            cache=SimpleNamespace(load=lambda _: (rgba,None))
            obj=dict(key='a',x=0,y=0,width=2,height=2,depth=0,flip=False)
            meta=dict(level=0,bounds=[0,0,4,2],width=4,height=2,objects=[obj])
            atlas.render_level(cache,meta,{},root,size=2,full=True)
            self.assertFalse((tiles/'1_0.png').exists())
            with Image.open(root/'level-0/full-resolution.png')as im:
                self.assertEqual(im.getpixel((3,0)),(0,0,0))
    def test_per_pixel_depth_and_horizontal_flip(self):
        a=np.array([[[255,0,0,255],[0,255,0,255]]],np.uint8)
        b=np.array([[[0,0,255,255],[0,0,255,255]]],np.uint8)
        cache=SimpleNamespace(load=lambda k:(a,np.array([[1,9]],np.uint16))if k=='a'else(b,None))
        objs=[dict(key='a',x=0,y=0,width=2,height=1,depth=0,flip=True),dict(key='b',x=0,y=0,width=2,height=1,depth=5,flip=False)]
        got=np.asarray(atlas.raster(cache,objs,(0,0,2,1)))
        self.assertEqual(got.tolist(),[[[0,0,255,255],[255,0,0,255]]])
    def test_tile_seams_match_whole_render(self):
        a=np.zeros((4,7,4),np.uint8);a[:]=[20,70,100,255]
        a[1,2,3]=0
        cache=SimpleNamespace(load=lambda k:(a,None))
        obj=dict(key='x',x=-2,y=-1,width=7,height=4,depth=0,flip=False)
        whole=np.asarray(atlas.raster(cache,[obj],(-3,-2,6,5)))
        left=np.asarray(atlas.raster(cache,[obj],(-3,-2,1,5)))
        right=np.asarray(atlas.raster(cache,[obj],(1,-2,6,5)))
        self.assertTrue(np.array_equal(whole,np.concatenate([left,right],axis=1)))
    def test_streamed_full_png_preserves_pixels_and_missing_tiles(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);(root/'tiles').mkdir()
            img=Image.new('RGB',(2,2),(27,83,149));img.save(root/'tiles/0_0.png')
            img=Image.new('RGB',(1,1),(255,2,3));img.save(root/'tiles/1_1.png')
            p=atlas.write_full_png(root,{'width':3,'height':3},2)
            a=np.asarray(Image.open(p))
            self.assertEqual(a[0,0].tolist(),[27,83,149])
            self.assertEqual(a[0,2].tolist(),[0,0,0])
            self.assertEqual(a[2,2].tolist(),[255,2,3])


class Maps(unittest.TestCase):
    def test_bounded_block_and_sector_positions(self):
        body=b'\x00'+struct.pack('<IiiiHhhiBBBiBBI',1,1088,2112,64,0,-1,-1,-1,0,0,0,7,0,0,0)
        data=b'MAP '+struct.pack('<ii',13,2)+struct.pack('<hhIh',0,9,123,len(body))+body+struct.pack('<h',-1)
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'0_1_2.dat';p.write_bytes(data)
            objs,ignored,version,count=atlas.parse_sector(p)
            self.assertEqual((len(objs),version,count),(1,13,2))
            self.assertEqual((objs[0].x,objs[0].y),(1088,2112))
            p.write_bytes(data[:-3])
            with self.assertRaises(atlas.FormatError):atlas.parse_sector(p)
    def test_old_v1_sector_without_block_sizes(self):
        # Pre-block-size records include velocity, health and old rotation fields.
        body=b'\x00'+struct.pack('<Iiii',1,1088,2112,64)+bytes(12)+bytes([0,100])+struct.pack('<Bhhh i B',0,0,-1,0,-1,0)
        data=b'MAP '+struct.pack('<ii',1,1)+struct.pack('<hI',9,123)+body
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'0_1_2.dat';p.write_bytes(data)
            objs,ignored,version,count=atlas.parse_sector(p)
            self.assertEqual((len(objs),version,count),(1,1,1))
            self.assertEqual((objs[0].x,objs[0].y),(1088,2112))
    def test_outside_position_wraps_into_owning_sector_like_game(self):
        body=b'\x00'+struct.pack('<IiiiHhhiBBBiBBI',1,1088,2112,64,0,-1,-1,-1,0,0,0,7,0,0,0)
        data=b'MAP '+struct.pack('<ii',13,1)+struct.pack('<hhIh',0,9,123,len(body))+body
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'0_0_0.dat';p.write_bytes(data)
            objs,ignored,_,_=atlas.parse_sector(p)
            self.assertEqual(len(objs),1)
            self.assertEqual((objs[0].x,objs[0].y),(64,64))
            self.assertEqual(ignored['sector_positions_wrapped'],1)
        self.assertEqual(atlas.sector_position(Path('0_3_6.dat'),64,64,0),(3136,6208,0))
        self.assertEqual(atlas.sector_position(Path('0_3_6.dat'),-1,-1,17),(4095,7167,17))
        self.assertEqual(atlas.sector_position(Path('0_0_22.dat'),1024,23552,0),(1024,23552,0))
    def test_duplicate_type_id_uses_first_definition_like_engine(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'class.def'
            p.write_text('CLASS "TILE"\n"First" "Forest/a.i2d" 0x1234\n"Second" "Forest/b.i2d" 0x1234\n')
            self.assertEqual(atlas.parse_types(p)[('TILE',0x1234)]['name'],'First')
    def test_native_projection_keeps_source_pixel_scale(self):
        x,y,z=atlas.project(1024,0,0)
        self.assertEqual((x,y),(1024,512))
        self.assertEqual(atlas.project(0,1024,0)[:2],(-1024,512))
        self.assertEqual(atlas.project(0,0,1000)[:2],(0,-867))

if __name__=='__main__':unittest.main()
