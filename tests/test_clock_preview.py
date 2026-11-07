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

    def test_completed_clock_catalog_clears_actual_missing_levels(self):
        base=dict(expected_maps=4,cycling_levels=[0],missing_maps=[],levels=[
            dict(level=0,variants=[dict(level=0,variant='day'),dict(level=0,variant='night')]),
            dict(level=41,variant='fixed'),dict(level=42,variant='fixed')])
        result=compose(base,dict(levels=[dict(level=0,variant='twilight')]))
        self.assertTrue(result['publication_complete']);self.assertFalse(result['preview'])
        self.assertEqual(result['unresolved_levels'],[]);self.assertEqual(result['ready_maps'],5)
        self.assertEqual(result['expected_maps'],5)
        base['missing_maps']=[dict(level=43,variant='fixed')];base['expected_maps']=5
        result=compose(base,dict(levels=[dict(level=0,variant='twilight')]))
        self.assertFalse(result['publication_complete']);self.assertEqual(result['unresolved_levels'],[43])

    def test_opted_in_recoveries_complete_availability_without_claiming_exactness(self):
        base=dict(expected_maps=2,cycling_levels=[],missing_maps=[dict(level=41,variant='fixed')],levels=[dict(level=30,variant='fixed')])
        recovery=dict(levels=[dict(level=41,variant='fixed',recovery=dict(omitted_placements=10))])
        result=compose(base,dict(levels=[]),recovery)
        self.assertTrue(result['available_complete']);self.assertFalse(result['publication_complete'])
        self.assertFalse(result['preview']);self.assertEqual(result['recovered_levels'],[41])
        self.assertEqual(result['omitted_source_placements'],10);self.assertEqual(result['missing_maps'],[])
