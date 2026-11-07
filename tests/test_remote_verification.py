import hashlib
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import tempfile
import threading
import unittest

from native.publish_upload import Publisher,VERIFY_PART


class RemoteVerificationTests(unittest.TestCase):
    def test_remote_ranges_cover_whole_file_and_reject_changed_bytes_or_range(self):
        data=b'0123456789abcdef'*(VERIFY_PART//16)+b'final bytes'
        calls=[];mode=['valid']
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                calls.append(self.headers.get('Range'))
                start,end=map(int,self.headers['Range'].removeprefix('bytes=').split('-'))
                body=data[start:end+1]
                if mode[0]=='changed':body=bytes([body[0]^1])+body[1:]
                self.send_response(206)
                self.send_header('Content-Range',f'bytes {start}-{end}/{len(data)+(mode[0]=="bad-range")}')
                self.send_header('Content-Length',str(len(body)));self.end_headers()
                try:self.wfile.write(body)
                except(BrokenPipeError,ConnectionResetError):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory()as directory:
                state=Path(directory)/'verified.json'
                publisher=Publisher(f'http://127.0.0.1:{server.server_port}','test-only',state)
                item=dict(key='map.png',size=len(data),sha256=hashlib.sha256(data).hexdigest())
                publisher.verify(item)
                self.assertEqual(calls,[f'bytes=0-{VERIFY_PART-1}',f'bytes={VERIFY_PART}-{len(data)-1}'])
                self.assertEqual(len(json.loads(state.read_text())),1)
                publisher.verify(item);self.assertEqual(len(calls),2)
                publisher.verified.clear();state.unlink();mode[0]='changed'
                with self.assertRaisesRegex(RuntimeError,'Remote bytes differ'):publisher.verify(item)
                self.assertFalse(state.exists())
                mode[0]='bad-range'
                with self.assertRaisesRegex(ValueError,'range differs'):publisher.verify(item)
                self.assertFalse(state.exists())
        finally:
            server.shutdown();server.server_close();thread.join()
