import unittest
from unittest.mock import patch

from PIL import Image

from native.export import capture_core
from native.plan import camera_for_core


class CaptureProgressTests(unittest.TestCase):
    def capture(self,advance,move=False,ambient_change=False):
        class Game:
            export_level=0
            capture_lighting=dict(expected_native_ambient=40,ambient_rgb=[250,250,250])if ambient_change else None
            calls=0
            def view(self,*args):pass
            def command(self,*args):pass
            def info(self):
                self.calls+=1
                camera=list(camera_for_core(0,0))
                if move and self.calls>1:camera[0]+=1
                return dict(camera=camera,scroll=[-64,-42],ambient_fade_frames=0,
                            ambient=35 if ambient_change and self.calls>1 else 40,ambient_rgb=[250,250,250],
                            screen_frame=10+(advance if self.calls>1 else 0))
        class Capture:
            def frame(self):return Image.new('RGB',(640,340))
        with patch('native.export.time.sleep'):
            return capture_core(Game(),Capture(),(0,0),0)

    def test_frozen_renderer_is_not_a_valid_capture(self):
        with self.assertRaisesRegex(RuntimeError,'stopped advancing'):self.capture(0)

    def test_camera_changes_invalidate_capture(self):
        with self.assertRaisesRegex(RuntimeError,'camera changed'):self.capture(2,True)

    def test_stationary_artwork_with_advancing_renderer_is_valid(self):
        _,_,mask,state=self.capture(2)
        self.assertFalse(mask.any())
        self.assertEqual(state['capture_end_screen_frame'],12)

    def test_native_ambient_drift_invalidates_an_advancing_capture(self):
        with self.assertRaisesRegex(RuntimeError,'ambient changed'):self.capture(2,ambient_change=True)


if __name__=='__main__':unittest.main()
