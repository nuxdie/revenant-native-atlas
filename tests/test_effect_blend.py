"""Regress geyser blending through particle-controller template restoration."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest


class EffectBlendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        lib=Path(cls.tmp.name)/'effect.so'
        subprocess.run(['cc','-O2','-shared','-fPIC','-DEFFECT_HOST_TEST',
                        str(Path(__file__).resolve().parents[1]/'native/effect_blend.c'),'-o',str(lib)],check=True)
        cls.lib=C.CDLL(str(lib));cls.fn=cls.lib.effect_surface
        cls.fn.argtypes=[C.c_uint]*3+[C.POINTER(C.c_uint)]*2

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def run_surface(self,t,n,i,flags=0xa0000000,mode=0):
        f=C.c_uint(flags);m=C.c_uint(mode);self.fn(t,n,i,C.byref(f),C.byref(m));return f.value,m.value

    def test_all_geyser_mesh_surfaces_but_not_other_effects(self):
        for t,count,base in [(0x730019,5,4),(0x720019,3,2)]:
            for i in range(count):
                self.assertEqual(self.run_surface(t,count,i),(0xa1000000,16))
            self.assertEqual(self.run_surface(t,count,count),(0xa0000000,0))
        for t in (0x710019,0x740019,0x730009,0x73000d,0):
            self.assertEqual(self.run_surface(t,5,4),(0xa0000000,0))
        for count in (0,1,4,6,256):
            self.assertEqual(self.run_surface(0x730019,count,4),(0xa0000000,0))

    def test_explicit_blend_modes_preserved_and_unrelated_flags_unchanged(self):
        for mode in range(128):
            self.assertEqual(self.run_surface(0x730019,5,4,0xabcdef01,mode),
                             (0xabcdef01|0x1000000,mode|16)if mode in(0,16,64,80)else(0xabcdef01,mode))
        self.assertEqual(self.run_surface(0x730019,5,4,*self.run_surface(0x730019,5,4)),(0xa1000000,16))

    def test_controller_cleanup_does_not_restore_an_opaque_template(self):
        for type,count in((0x730019,5),(0x720019,3)):
            for index in range(count):
                # PartSys close restores pre-controller flags and mode.
                original_flags=0xa000e000 if index in(0,2)else 0x80000000
                self.assertEqual(self.run_surface(type,count,index,original_flags,0),(original_flags|0x1000000,16))
                # A subsequent reset of flags alone also retains litadd.
                self.assertEqual(self.run_surface(type,count,index,original_flags,16),(original_flags|0x1000000,16))


if __name__=='__main__':unittest.main()
