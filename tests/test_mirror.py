"""Independent mirror: native packed tiles, file ranges and route boundaries."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from tools.serve_atlas import Handler,ranged


class MirrorTests(unittest.TestCase):
    def test_range_boundaries(self):
        self.assertEqual(ranged('bytes=3-8',10),(3,8,206))
        self.assertEqual(ranged('bytes=-4',10),(6,9,206))
        self.assertEqual(ranged('bytes=8-99',10),(8,9,206))
        for raw in('bytes=-0','bytes=10-','bytes=8-4','bytes=0-1,3-4','invalid'):
            with self.assertRaises(ValueError):ranged(raw,10)

    def test_packed_tile_tiff_range_and_private_file_rejection(self):
        with tempfile.TemporaryDirectory()as temp:
            data=Path(temp);root=data/'releases/r-test/level-30';root.mkdir(parents=True)
            (data/'catalog.json').write_text('{"edition":"july"}')
            (data/'retail-preview-catalog.json').write_text('{"edition":"retail"}')
            tile=b'original-native-png';(root/'tiles.pack').write_bytes(b'prefix'+tile+b'suffix')
            (root/'tiles.json').write_text(json.dumps(dict(tiles={'0_0':dict(offset=6,length=len(tile),sha256=hashlib.sha256(tile).hexdigest())})))
            image=b'II+\0\x08\0\0\0'+bytes(range(64));(root/'full-resolution.tif').write_bytes(image)
            (root/'validation.json').write_text('{}')
            class TestHandler(Handler):
                def log_message(self,*args):pass
            TestHandler.data=data
            server=ThreadingHTTPServer(('127.0.0.1',0),TestHandler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}/api/'
            try:
                for query,edition in [('', 'july'),('?dataset=july','july'),('?dataset=retail','retail')]:
                    with urllib.request.urlopen(base+'catalog'+query)as r:self.assertEqual(json.load(r)['edition'],edition)
                for edition,label in [('july','july-1999'),('retail','retail-1.22l')]:
                    req=urllib.request.Request(base+f'file?revision=r-test&level=30&variant=night&dataset={edition}&name=full-resolution.tif',method='HEAD')
                    with urllib.request.urlopen(req)as r:self.assertIn(f'revenant-{label}-level-30-night.tif',r.headers['Content-Disposition'])
                with urllib.request.urlopen(base+'tile?revision=r-test&level=30&x=0&y=0')as r:self.assertEqual(r.read(),tile)
                req=urllib.request.Request(base+'file?revision=r-test&level=30&variant=night&name=full-resolution.tif',headers={'Range':'bytes=2-12'})
                with urllib.request.urlopen(req)as r:
                    self.assertEqual(r.status,206);self.assertEqual(r.headers['Content-Type'],'image/tiff');self.assertEqual(r.read(),image[2:13]);self.assertIn('level-30-night.tif',r.headers['Content-Disposition'])
                for route,code in [('file?revision=r-test&level=30&name=validation.json',404),('file?revision=r-test&level=30&variant=../../&name=full-resolution.tif',400),('file?revision=../&level=30&name=full-resolution.tif',400)]:
                    with self.assertRaises(urllib.error.HTTPError)as failure:urllib.request.urlopen(base+route)
                    self.assertEqual(failure.exception.code,code)
            finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
