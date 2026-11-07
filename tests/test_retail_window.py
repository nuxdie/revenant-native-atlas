import unittest
from unittest.mock import patch
from PIL import Image
from native.retail import RetailCapture
from native.x11_capture import WindowCapture


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

    def test_read_renames_backing_store_even_when_old_pixmap_stays_readable(self):
        events=[]
        class Call:
            def __call__(self,*args):events.append(('free',args))
        class X:
            XFreePixmap=Call()
            def XGetImage(self,display,window,*args):events.append(('read',window));return None
        class Composite:
            ids=iter([202,303])
            def XCompositeNameWindowPixmap(self,display,window):
                events.append(('name',window));return next(self.ids)
        capture=WindowCapture.__new__(WindowCapture)
        capture.x=X();capture._composite=Composite();capture.display=1
        capture._redirected_window=42;capture.pixmap=101;capture.window=101
        with self.assertRaises(RuntimeError):capture.frame(2,2)
        self.assertEqual(capture.window,202)
        with self.assertRaises(RuntimeError):capture.frame(2,2)
        self.assertEqual(capture.window,303)
        self.assertEqual(events,[('name',42),('free',(1,101)),('read',202),('name',42),('free',(1,202)),('read',303)])
