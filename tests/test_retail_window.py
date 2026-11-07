import unittest
from unittest.mock import patch
from PIL import Image
from native.retail import RetailCapture


class RetailWindowTests(unittest.TestCase):
    def test_first_frame_is_read_after_post_mapping_native_redraw(self):
        events=[]
        class Game:
            env={'DISPLAY':':test'}
            def desktop_window(self):return 42
            def command(self,command):events.append(command)
        class Drawable:
            def __init__(self,*args,**kwargs):events.append('pixmap')
            def frame(self):
                self_test.assertEqual(events[-2:],['mono 0','@wait'])
                return Image.new('RGB',(640,480),(20,40,60))
            def close(self):pass
        self_test=self
        with patch('native.retail.subprocess.run'),patch('native.retail.WindowCapture',Drawable):
            with RetailCapture(Game())as capture:im=capture.frame()
        self.assertEqual(events,['pixmap','mono 0','@wait']);self.assertEqual(im.getpixel((0,0)),(20,40,60))
