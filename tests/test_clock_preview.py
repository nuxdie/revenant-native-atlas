import copy
import unittest
from native.clock_preview import compose


class ClockPreviewTests(unittest.TestCase):
    def test_preview_adds_only_real_clock_images_and_leaves_default_catalog_unchanged(self):
        base=dict(expected_maps=39,levels=[dict(level=0,width=100,variants=[
            dict(level=0,variant='day',revision='day'),dict(level=0,variant='night',revision='night')]),
            dict(level=30,variant='fixed',revision='cave')])
        original=copy.deepcopy(base)
        twilight=dict(levels=[dict(level=0,variant='twilight',revision='native-twilight',width=120)])
        result=compose(base,twilight)
        self.assertEqual(base,original);self.assertEqual(result['ready_maps'],4)
        self.assertFalse(result['publication_complete']);self.assertEqual(result['expected_maps'],41)
        self.assertEqual(result['levels'][0]['variants'][2]['width'],120)
        self.assertEqual(len(result['levels'][0]['clock']['hours']),24)
        self.assertNotIn('clock',result['levels'][1])
