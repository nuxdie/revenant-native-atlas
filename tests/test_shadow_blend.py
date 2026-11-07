"""Regress the format mismatch without requiring Wine or a running game."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest


class Block(C.Structure):
    _fields_=[('srcbitmap',C.c_void_p),('dstsurface',C.c_void_p),('srcflags',C.c_uint),('dstflags',C.c_uint),
              ('dest',C.POINTER(C.c_ushort)),('dzbuffer',C.c_void_p),('dnormals',C.c_void_p),
              ('dbufwidth',C.c_int),('dbufheight',C.c_int),('dstride',C.c_int),('dzstride',C.c_int),
              ('source',C.POINTER(C.c_ushort)),('szbuffer',C.c_void_p),('snormals',C.c_void_p),
              ('sbufwidth',C.c_int),('sbufheight',C.c_int),('sstride',C.c_int),('szstride',C.c_int),
              ('palette',C.c_void_p),('alpha',C.POINTER(C.c_ubyte)),('alias',C.c_void_p),('keycolor',C.c_uint)]


class Param(C.Structure):
    _fields_=[('mode',C.c_uint),('func',C.c_void_p),('callback',C.c_void_p),('data',C.c_void_p)]+[(s,C.c_int)for s in
              ('ox','oy','cx','cy','cw','ch','dx','dy','dw','dh','sx','sy','sw','sh')]+[
              ('color',C.c_uint),('intensity',C.c_uint),('zpos',C.c_ushort),('normal',C.c_ushort)]


class ShadowBlendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        source=Path(__file__).resolve().parents[1]/'native/shadow_blend.c'
        library=Path(cls.tmp.name)/'shadow.so'
        subprocess.run(['cc','-O2','-shared','-fPIC','-DSHADOW_HOST_TEST',str(source),'-o',str(library)],check=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.shadow_pixel.argtypes=[C.c_ushort,C.c_uint];cls.lib.shadow_pixel.restype=C.c_ushort
        cls.lib.shadow_blend.argtypes=[C.POINTER(Block),C.POINTER(Param)]

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_every_rgb555_colour_preserves_coverage_and_never_brightens(self):
        pixel=self.lib.shadow_pixel
        for d in range(65536):
            self.assertEqual(pixel(d,0),d)
            self.assertEqual(pixel(d,31),d&0x8000)
            for a in (1,16,30):
                value=pixel(d,a)
                self.assertEqual(value&0x8000,d&0x8000)
                self.assertLessEqual(value&31,d&31)
                self.assertLessEqual((value>>5)&31,(d>>5)&31)
                self.assertLessEqual((value>>10)&31,(d>>10)&31)
        self.assertEqual(pixel(0xffff,16),0xbdcf)

    def test_stride_clipping_mirrors_and_shadow_intensity(self):
        for flip in (0,0x40,0x80,0xc0):
            dst=(C.c_ushort*48)(*[0xffff]*48)
            src=(C.c_ushort*24)()
            alpha=(C.c_ubyte*24)(*range(24))
            db=Block(srcflags=0x104,dstflags=0x20000,dest=dst,source=src,alpha=alpha,dstride=8,sstride=6)
            dp=Param(mode=0x2100|flip,ox=-1,oy=1,dx=3,dy=1,dw=3,dh=2,sx=1,sy=1,sw=3,sh=2,intensity=25)
            self.assertEqual(self.lib.shadow_blend(C.byref(db),C.byref(dp)),1)
            touched=set()
            for y in range(2):
                for x in range(3):
                    sy=1+(1-y if flip&0x40 else y);sx=1+(2-x if flip&0x80 else x)
                    a=max(0,alpha[sy*6+sx]-6);i=(2+y)*8+2+x;touched.add(i)
                    self.assertEqual(dst[i],self.lib.shadow_pixel(0xffff,a))
            self.assertTrue(all(v==0xffff for i,v in enumerate(dst)if i not in touched))


if __name__=='__main__':unittest.main()
