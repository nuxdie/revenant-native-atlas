#!/usr/bin/env python3
"""Serve the released viewer and native tile packs without cloud credentials."""
import argparse
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs,urlparse

PUBLIC=Path(__file__).resolve().parents[1]/'public-site/public'


def ranged(value,size):
    if value is None:return 0,size-1,200
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not match or not(match[1]or match[2]):raise ValueError('Invalid range')
    if match[1]:start=int(match[1]);end=min(size-1,int(match[2]))if match[2]else size-1
    else:
        if int(match[2])<=0:raise ValueError('Invalid suffix')
        start=max(0,size-int(match[2]));end=size-1
    if not 0<=start<=end<size:raise ValueError('Unsatisfiable range')
    return start,end,206


class Handler(SimpleHTTPRequestHandler):
    data=Path('data')
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(PUBLIC),**kwargs)
    def do_HEAD(self):self.route(True)
    def do_GET(self):self.route(False)
    def route(self,head):
        url=urlparse(self.path);query=parse_qs(url.query)
        if url.path=='/api/catalog':return self.file(self.data/('retail-preview-catalog.json'if query.get('dataset')==['retail']else'catalog.json'),'application/json',head)
        if url.path.startswith('/api/'):
            level=query.get('level',[''])[0];revision=query.get('revision',[''])[0]
            if not re.fullmatch(r'\d{1,3}',level)or not re.fullmatch(r'[a-z0-9-]{1,48}',revision):return self.send_error(400)
            root=self.data/'releases'/revision/f'level-{level}'
            if url.path=='/api/file':
                name=query.get('name',[''])[0]
                variant=query.get('variant',[''])[0]
                if variant not in('','day','night','twilight','fixed'):return self.send_error(400)
                if name not in('overview.jpg','full-resolution.png','full-resolution.tif'):return self.send_error(404)
                mime='image/png'if name.endswith('.png')else'image/tiff'if name.endswith('.tif')else'image/jpeg'
                edition='retail-1.22l-recovered-'if '-recovered-'in revision else{'retail':'retail-1.22l-','july':'july-1999-'}.get(query.get('dataset',[''])[0],'')
                attachment=f'revenant-{edition}{root.name}'+(f'-{variant}'if variant else'')+Path(name).suffix if name!='overview.jpg'else None
                return self.file(root/name,mime,head,attachment)
            if url.path=='/api/tile':
                x=query.get('x',[''])[0];y=query.get('y',[''])[0]
                if not re.fullmatch(r'\d{1,4}',x)or not re.fullmatch(r'\d{1,4}',y):return self.send_error(400)
                try:
                    index=json.loads((root/'tiles.json').read_text());tile=index['tiles'][x+'_'+y]
                    with(root/'tiles.pack').open('rb')as stream:stream.seek(tile['offset']);data=stream.read(tile['length'])
                except(FileNotFoundError,KeyError):return self.send_error(404)
                if len(data)!=tile['length']:return self.send_error(500)
                self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.send_header('ETag','"'+tile['sha256']+'"');self.end_headers()
                if not head:self.wfile.write(data)
                return
            return self.send_error(404)
        if url.path=='/':self.path='/atlas.html'
        return super().do_HEAD()if head else super().do_GET()
    def file(self,path,mime,head,attachment=False):
        if not path.is_file():return self.send_error(404)
        size=path.stat().st_size
        try:start,end,status=ranged(self.headers.get('Range'),size)
        except ValueError:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('X-Content-Type-Options','nosniff')
        if path.name in('catalog.json','retail-preview-catalog.json'):self.send_header('Cache-Control','no-store')
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        if attachment:self.send_header('Content-Disposition',f'attachment; filename="{attachment}"')
        self.end_headers()
        if head:return
        try:
            with path.open('rb')as stream:
                stream.seek(start);remaining=end-start+1
                while remaining:
                    block=stream.read(min(1024*1024,remaining))
                    if not block:break
                    self.wfile.write(block);remaining-=len(block)
        except(BrokenPipeError,ConnectionResetError):pass


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,default=Path('data'));parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8767);args=parser.parse_args()
    Handler.data=args.data.resolve();print(f'Atlas mirror: http://{args.host}:{args.port}/',flush=True)
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
