"""Preview the hosted atlas UI with this workstation's native map files."""
import argparse
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlparse,parse_qs

ROOT=Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'public-site/public'),**kwargs)
    def log_message(self,*args):pass
    def end_headers(self):self.send_header('Cache-Control','no-store');super().end_headers()
    def do_HEAD(self):self.route(head=True)
    def do_GET(self):self.route()
    def route(self,head=False):
        url=urlparse(self.path);q=parse_qs(url.query)
        if url.path=='/api/catalog':
            catalog=json.loads((ROOT/'runtime/publication/catalog.json').read_text())
            for m in catalog['levels']:
                root=ROOT/'native-output'/f'level-{m["level"]}'
                m['png_bytes']=(root/'full-resolution.png').stat().st_size
                tif=root/'tiff-validation.json'
                if tif.exists():m['tiff_bytes']=json.loads(tif.read_text())['bytes']
            data=json.dumps(catalog).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers()
            if not head:self.wfile.write(data)
            return
        if url.path in ('/api/file','/api/tile'):
            level=q.get('level',[''])[0]
            if not re.fullmatch(r'\d{1,3}',level):return self.send_error(400)
            root=ROOT/'native-output'/f'level-{level}'
            if url.path=='/api/file':
                name=q.get('name',[''])[0]
                if name not in ('overview.jpg','full-resolution.png','full-resolution.tif'):return self.send_error(404)
                return self.file(root/name,'image/png'if name.endswith('.png')else'image/tiff'if name.endswith('.tif')else'image/jpeg',head,name!='overview.jpg')
            x=q.get('x',[''])[0];y=q.get('y',[''])[0]
            if not re.fullmatch(r'\d{1,4}',x)or not re.fullmatch(r'\d{1,4}',y):return self.send_error(400)
            return self.file(root/'tiles'/f'{x}_{y}.png','image/png',head)
        if url.path=='/':self.path='/atlas.html'+('?' + url.query if url.query else'')
        return super().do_HEAD()if head else super().do_GET()
    def file(self,path,mime,head=False,attachment=False):
        if not path.is_file():return self.send_error(404)
        size=path.stat().st_size;start,end=0,size-1;status=200
        raw=self.headers.get('Range')
        if raw:
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',raw)
            if not m or not(m[1]or m[2]):return self.send_error(416)
            if m[1]:start=int(m[1]);end=min(end,int(m[2]))if m[2]else end
            else:start=max(0,size-int(m[2]))
            if not 0<=start<=end<size:return self.send_error(416)
            status=206
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes')
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        if attachment:self.send_header('Content-Disposition',f'attachment; filename="revenant-{path.parent.name}{path.suffix}"')
        self.end_headers()
        if head:return
        try:
            with path.open('rb')as f:
                f.seek(start);remaining=end-start+1
                while remaining:
                    block=f.read(min(65536,remaining))
                    if not block:break
                    self.wfile.write(block);remaining-=len(block)
        except(BrokenPipeError,ConnectionResetError):pass


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8767);a=p.parse_args()
    print(f'Atlas design preview: http://127.0.0.1:{a.port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
