import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from fidelity import compare
from snapshot import atlas_crop


class FidelityTests(unittest.TestCase):
    def test_single_channel_error_is_reported_without_normalization(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = np.zeros((2, 2, 3), dtype=np.uint8)
            b = a.copy()
            b[1, 0, 2] = 1
            Image.fromarray(a).save(root / 'a.png')
            Image.fromarray(b).save(root / 'b.png')
            report = compare(root / 'a.png', root / 'b.png', root / 'result')
            self.assertEqual(report['exact_pixel_fraction'], .75)
            self.assertEqual(report['maximum_channel_error'], 1)
            self.assertAlmostEqual(report['mean_absolute_channel_error'], 1 / 12)
            self.assertEqual(report['mismatch_bounds'], [0, 1, 1, 2])
            self.assertFalse(report['resampled'])
            Image.fromarray(np.array([[255, 255], [0, 255]], dtype=np.uint8)).save(root / 'mask.png')
            masked = compare(root / 'a.png', root / 'b.png', root / 'masked', mask=root / 'mask.png')
            self.assertEqual(masked['compared_pixels'], 3)
            self.assertEqual(masked['exact_pixel_fraction'], 1)
            self.assertIsNotNone(masked['mask'])

    def test_native_crop_retains_world_registration_across_four_tiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            level = root / 'level-0'
            (level / 'tiles').mkdir(parents=True)
            (level / 'manifest.json').write_text(json.dumps({'bounds': [-2, -2, 2, 2], 'tile_size': 2}))
            for y in range(2):
                for x in range(2):
                    Image.new('RGB', (2, 2), (10 + x, 20 + y, 30)).save(level / f'tiles/{x}_{y}.png')
            crop = np.asarray(atlas_crop(root, 0, (0, 0, 0), (2, 2)))
            self.assertEqual(crop.tolist(), [[[10, 20, 30], [11, 20, 30]], [[10, 21, 30], [11, 21, 30]]])


if __name__ == '__main__':
    unittest.main()
