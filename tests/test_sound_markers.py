"""Coverage guards must follow actual ownership at sound-emitter positions."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
from native.sound_markers import PROFILE,owned_sources,require_clean_owners,intersects_viewport


class SoundMarkerCoverageTest(unittest.TestCase):
    def test_two_owners_and_unfiltered_neighbour(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'ownership').mkdir();(root/'captures').mkdir()
            (root/'manifest.json').write_text(json.dumps(dict(tile_size=8,width=16,height=8,bounds=[-8,10,8,18])))
            (root/'ownership-sources.json').write_text(json.dumps([dict(id=1,capture='left'),dict(id=2,capture='right')]))
            for x,name in enumerate(['left','right']):
                Image.fromarray(np.full((8,8),x+1,np.uint16)).save(root/'ownership'/f'{x}_0.png')
                (root/'captures'/f'{name}.json').write_text(json.dumps(dict(sound_marker_profile=PROFILE if x==0 else 'unfiltered')))
            points=[dict(screen=[0,12])]
            self.assertEqual(owned_sources(root,points,padding=1),['left','right'])
            with self.assertRaisesRegex(ValueError,'right'):require_clean_owners(root,points)
            (root/'captures/right.json').write_text(json.dumps(dict(sound_marker_profile=PROFILE)))
            self.assertEqual(require_clean_owners(root,points),['left','right'])
            self.assertEqual(owned_sources(root,[dict(screen=[200,200])]),[])

    def test_viewport_padding_includes_apron_sources(self):
        self.assertTrue(intersects_viewport([0,0],[dict(screen=[-63,20])]))
        self.assertTrue(intersects_viewport([0,0],[dict(screen=[700,20])]))
        self.assertFalse(intersects_viewport([0,0],[dict(screen=[800,20])]))
