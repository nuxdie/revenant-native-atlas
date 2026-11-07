"""Local live map window, backed exclusively by the original game renderer."""
import argparse
from collections import deque
from concurrent.futures import Future
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import queue
import threading
import time
from urllib.parse import urlparse

from .game import NativeGame, ROOT, RUNTIME


def export_running():
    for proc in Path('/proc').iterdir():
        if proc.name==str(os.getpid()):continue
        if not proc.name.isdigit():
            continue
        try:
            args = (proc / 'cmdline').read_bytes().split(b'\0')
            if any(name in args for name in (b'native.export',b'native.refresh_sources',b'native.build_all',b'native.repair_reviews',b'native.bridge',b'native.repair_effects',b'native.clip',b'native.check_scene')):
                return True
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return False


class LiveRenderer:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = queue.Queue()
        self.frame = None
        self.state = {'status': 'starting'}
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.is_set():
            try:
                self._run_session()
            except Exception as exc:
                with self.lock:self.state={'status':'error','message':str(exc)}
                self.stop.wait(1)

    def _run_session(self):
        capture = None
        game = NativeGame()
        frames = 0
        last_state = 0
        last_native_frame=None
        last_advance=time.monotonic()
        try:
            while not self.stop.is_set():
                start = time.monotonic()
                if export_running():
                    with self.lock:
                        self.state = {'status': 'exporting', 'message': 'Native map capture and validation own the camera until the batch finishes.'}
                    self.stop.wait(.5)
                    continue
                try:
                    while True:
                        command, result = self.requests.get_nowait()
                        try:
                            state = game.view(**command)
                            game.command('mono 0')
                            game.command('@wait')
                            result.set_result(state)
                        except Exception as exc:
                            result.set_exception(exc)
                except queue.Empty:
                    pass
                if capture is None:
                    game.command('@normal')
                    game.command('@presentation')
                    game.command('@helpers-off')
                    game.command('mono 0')
                    game.command('@wait')
                    capture = game.backing_capture()
                if time.monotonic() - last_state > 1:
                    state = game.info()
                    last_state = time.monotonic()
                    if state['screen_frame']!=last_native_frame:
                        last_native_frame=state['screen_frame'];last_advance=last_state
                image = capture.frame().crop((0, 0, 640, 340))
                out = BytesIO()
                image.save(out, format='PNG', compress_level=1)
                frames += 1
                with self.lock:
                    self.frame = out.getvalue()
                    alive=time.monotonic()-last_advance<3
                    self.state = dict(state, status='live'if alive else'paused', frame=frames,
                                      message=''if alive else'The original game renderer has stopped advancing frames.',
                                      provider='original game', viewport=[640, 340])
                self.stop.wait(max(0, 1/24 - (time.monotonic() - start)))
        except Exception as exc:
            with self.lock:
                self.state = {'status': 'error', 'message': str(exc)}
            self.stop.wait(1)
        finally:
            if capture:
                capture.close()

    def view(self, command):
        if export_running():
            raise RuntimeError('Native map capture or validation is using the camera; wait for it to finish.')
        future = Future()
        self.requests.put((command, future))
        return future.result(timeout=20)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'native-output'), **kwargs)

    def log_message(self, *_):
        pass

    def send(self, code, data, content_type):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            return self.send(200, (ROOT / 'native/live.html').read_bytes(), 'text/html; charset=utf-8')
        if path == '/state.json':
            with self.server.renderer.lock:
                data = json.dumps(self.server.renderer.state).encode()
            return self.send(200, data, 'application/json')
        if path == '/frame.png':
            with self.server.renderer.lock:
                frame = self.server.renderer.frame
            return self.send(200, frame, 'image/png') if frame else self.send(503, b'Frame not ready', 'text/plain')
        if path == '/levels.json':
            maps = []
            for manifest in sorted((ROOT / 'output').glob('level-*/manifest.json')):
                m = json.loads(manifest.read_text())
                maps.append({k: m[k] for k in ('level', 'names', 'bounds', 'width', 'height')})
            return self.send(200, json.dumps(sorted(maps, key=lambda m: m['level'])).encode(), 'application/json')
        if path == '/CREDITS.md':
            return self.send(200, (ROOT / 'CREDITS.md').read_bytes(), 'text/plain; charset=utf-8')
        return super().do_GET()

    def do_POST(self):
        # Only same-origin requests with JSON are accepted; never expose a raw
        # command console to websites or to the network.
        expected = f'http://127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}' or self.headers.get('Origin') not in (None, expected):
            return self.send(403, b'Local same-origin requests only', 'text/plain')
        if self.path != '/view' or self.headers.get('Content-Type') != 'application/json':
            return self.send(400, b'Expected a JSON camera request', 'text/plain')
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 256:
                raise ValueError('Invalid request size')
            request = json.loads(self.rfile.read(size))
            if set(request) != {'level', 'x', 'y', 'z'} or any(type(v) is not int for v in request.values()):
                raise ValueError('Camera requires integer level, x, y, z')
            if not 0 <= request['level'] <= 255 or any(not -65536 <= request[k] <= 65536 for k in ('x','y','z')):
                raise ValueError('Camera outside supported world bounds')
            state = self.server.renderer.view(request)
            return self.send(200, json.dumps(state).encode(), 'application/json')
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return self.send(400, str(exc).encode(), 'text/plain')
        except Exception as exc:
            return self.send(409, str(exc).encode(), 'text/plain')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8766)
    args = p.parse_args()
    renderer = LiveRenderer()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.renderer = renderer
    print(f'Original-game live atlas: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        renderer.stop.set()
        renderer.thread.join(timeout=3)
        server.server_close()

if __name__ == '__main__':
    main()
