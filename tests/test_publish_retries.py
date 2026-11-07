from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from native.publish_retail import publish_files


class PublishRetryTests(unittest.TestCase):
    def test_failed_file_does_not_block_others_and_catalog_waits(self):
        calls=[];failures=[2]
        class Publisher:
            def upload(self,item):
                calls.append(item['key'])
                if item['key']=='b'and failures[0]:
                    failures[0]-=1;raise RuntimeError('temporary timeout')
        with tempfile.TemporaryDirectory()as directory,patch('native.publish_retail.time.sleep'):
            manifest=dict(complete=True,uploads=[dict(key=k)for k in ['a','b','c','catalog.json']])
            result=publish_files(manifest,Publisher(),Path(directory)/'status.json',passes=3)
            self.assertEqual(calls,['a','b','c','b','b','catalog.json'])
            self.assertTrue(result['catalog_published']);self.assertEqual(result['verified_files'],3)

    def test_exhausted_file_and_incomplete_dataset_both_keep_catalog_held(self):
        class Publisher:
            def upload(self,item):
                if item['key']=='b':raise RuntimeError('unavailable')
                if item['key']=='catalog.json':raise AssertionError('Catalog must stay held')
        with tempfile.TemporaryDirectory()as directory,patch('native.publish_retail.time.sleep'):
            manifest=dict(complete=True,uploads=[dict(key=k)for k in ['a','b','catalog.json']])
            result=publish_files(manifest,Publisher(),Path(directory)/'status.json',passes=2)
            self.assertEqual(result['state'],'held_files');self.assertFalse(result['catalog_published'])
            manifest.update(complete=False,uploads=[dict(key='a'),dict(key='catalog.json')])
            result=publish_files(manifest,Publisher(),Path(directory)/'status.json')
            self.assertEqual(result['state'],'files_verified');self.assertFalse(result['catalog_published'])
