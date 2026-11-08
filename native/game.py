"""Control this installation's original editor, with strict binary guards."""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import shutil
import time

from .x11_capture import WindowCapture

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get('REVENANT_RUNTIME', ROOT / 'runtime')).resolve()
DESKTOP = os.environ.get('REVENANT_DESKTOP', 'RevenantAtlas')
DEFAULT_WINE = Path(os.environ.get('REVENANT_WINE', shutil.which('wine') or 'wine'))
EXPECTED_BINARY = json.loads((Path(__file__).parent / 'provider.json').read_text())['executable_sha256']


def build_control():
    # The live worker must not start the helper while its executable is being
    # replaced. Commands and rebuilds share the same cross-process lock.
    with (RUNTIME/'control.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _build_control()


def _build_control():
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            args=(proc/'cmdline').read_bytes().split(b'\0')
            if any(name in args for name in (b'native.export',b'native.refresh_sources',b'native.build_all',b'native.repair_reviews',b'native.bridge',b'native.repair_effects')):
                raise RuntimeError('Cannot rebuild the controller while an original-game export is running')
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    pidfile = RUNTIME / 'control-server.pid'
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text())
            if b'native-control' in Path(f'/proc/{pid}/cmdline').read_bytes():
                os.kill(pid, 15)
                for _ in range(100):
                    try:
                        if not Path(f'/proc/{pid}/cmdline').read_bytes():
                            break
                    except FileNotFoundError:
                        break
                    time.sleep(.01)
        except (FileNotFoundError, ValueError, ProcessLookupError):
            pass
        pidfile.unlink(missing_ok=True)
    sources = Path(__file__).parent
    for name,expected in [('CavFGeyser.i3d','48a4f889b755b7c6c8d383eba1660bb2724580efdffc363cf5e975e4f6bad3e6'),
                          ('CavSGeyser.I3D','34082b08a2e2dc5a895c3f10467b6ed0c68f2b9cca0a6f0f3840eb3675ea042a')]:
        if hashlib.sha256((RUNTIME/'game/Resources/Imagery/Cave'/name).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Geyser compatibility requires the pinned original loose resources')
    subprocess.run(['clang-18','--target=i686-pc-windows-msvc','-O2','-fno-stack-protector',
                    '-fno-builtin','-mno-sse','-mno-sse2','-c',str(sources/'effect_blend.c'),
                    '-o',str(RUNTIME/'effect-blend.obj')],check=True)
    subprocess.run(['i686-w64-mingw32-as',str(sources/'effect_bridge.s'),'-o',str(RUNTIME/'effect-bridge.o')],check=True)
    subprocess.run(['i686-w64-mingw32-ld','-Ttext','0','--image-base','0','--entry','_effect_bridge',
                    '--disable-reloc-section','-o',str(RUNTIME/'effect-blend.exe'),
                    str(RUNTIME/'effect-bridge.o'),str(RUNTIME/'effect-blend.obj')],check=True)
    subprocess.run(['i686-w64-mingw32-objcopy','-O','binary','-j','.text',
                    str(RUNTIME/'effect-blend.exe'),str(RUNTIME/'effect-blend-code.bin')],check=True)
    subprocess.run(['clang-18','--target=i686-pc-windows-msvc','-O2','-fno-stack-protector',
                    '-fno-builtin','-mno-sse','-mno-sse2','-c',str(sources/'shadow_blend.c'),
                    '-o',str(RUNTIME/'shadow-blend.obj')],check=True)
    subprocess.run(['i686-w64-mingw32-as',str(sources/'shadow_bridge.s'),'-o',str(RUNTIME/'shadow-bridge.o')],check=True)
    subprocess.run(['i686-w64-mingw32-ld','-Ttext','0','--image-base','0','--entry','_shadow_bridge',
                    '--disable-reloc-section','-o',str(RUNTIME/'shadow-blend.exe'),
                    str(RUNTIME/'shadow-bridge.o'),str(RUNTIME/'shadow-blend.obj')],check=True)
    subprocess.run(['i686-w64-mingw32-objcopy','-O','binary','-j','.text',
                    str(RUNTIME/'shadow-blend.exe'),str(RUNTIME/'shadow-blend-code.bin')],check=True)
    for dll in ('user32', 'kernel32'):
        subprocess.run(['i686-w64-mingw32-dlltool', '-d', str(sources / f'{dll}.def'),
                        '-l', str(RUNTIME / f'control-{dll}.a'), '--kill-at'], check=True)
    subprocess.run(['clang-18', '--target=i686-pc-windows-msvc', '-fno-stack-protector', '-c',
                    str(sources / 'control.c'), '-o', str(RUNTIME / 'native-control.obj')], check=True)
    subprocess.run(['i686-w64-mingw32-ld', '--entry', '_mainCRTStartup', '--subsystem', 'windows',
                    '-o', str(RUNTIME / 'native-control.exe.tmp'), str(RUNTIME / 'native-control.obj'),
                    str(RUNTIME / 'control-user32.a'), str(RUNTIME / 'control-kernel32.a')], check=True)
    (RUNTIME/'native-control.exe.tmp').replace(RUNTIME/'native-control.exe')


class NativeGame:
    def __init__(self, wine=DEFAULT_WINE, prefix=RUNTIME / 'prefix', display=None):
        display=display or os.environ.get('REVENANT_DISPLAY',os.environ.get('DISPLAY',':0.0'))
        actual = hashlib.sha256((RUNTIME / 'game/Revenant.exe').read_bytes()).hexdigest()
        if actual != EXPECTED_BINARY:
            raise RuntimeError('Original executable differs; native control addresses must be reverified')
        self.env = dict(os.environ, DISPLAY=display, WINEPREFIX=str(prefix), WINEDEBUG='-all')
        if os.environ.get('REVENANT_AUDIO_SINK'):
            self.env['PULSE_SINK'] = os.environ['REVENANT_AUDIO_SINK']
        self.wine = str(wine)
        self.display = display
        self.command_log = []

    def command(self, command):
        with (RUNTIME / 'control.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if command=='@presentation':
                self._command('@blend-fix')
                self._command('@effects-fix')
            return self._command(command)

    def _start_control(self):
        pidfile = RUNTIME / 'control-server.pid'
        if pidfile.exists():
            try:
                pid = int(pidfile.read_text())
                if b'native-control' in Path(f'/proc/{pid}/cmdline').read_bytes():
                    return
            except (FileNotFoundError, ValueError):
                pass
        (RUNTIME / 'control-request.bin').unlink(missing_ok=True)
        with (RUNTIME / 'control-server.log').open('ab') as log:
            process = subprocess.Popen([self.wine, str(RUNTIME / 'native-control.exe'), '--serve'],
                                       env=self.env, cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True)
        pidfile.write_text(str(process.pid))

    def _command(self, command):
        self._start_control()
        statefile = RUNTIME / 'control-state.bin'
        start = time.monotonic()
        counter = RUNTIME / 'control-sequence.txt'
        sequence = ((int(counter.read_text()) if counter.exists() else 0) + 1) & 0xffffffff
        sequence = sequence or 1
        counter.write_text(str(sequence))
        encoded = command.encode('ascii')
        if len(encoded) > 253:
            raise ValueError('Native command too long')
        request = RUNTIME / 'control-request.tmp'
        request.write_bytes(struct.pack('<II', sequence, len(encoded)) + encoded)
        request.replace(RUNTIME / 'control-request.bin')
        while True:
            try:
                data = statefile.read_bytes()
                if len(data) == 72:
                    values = struct.unpack('<18I', data)
                    if values[0] == 0x41544c53 and values[10] == sequence:
                        break
            except FileNotFoundError:
                pass
            if time.monotonic() - start > 15:
                raise RuntimeError(f'Native control response timed out: {command}')
            time.sleep(.005)
        if values[1]:
            raise RuntimeError(f'Native command failed ({values[1]}): {command}')
        signed = lambda x: struct.unpack('<i', struct.pack('<I', x))[0]
        state = {'level': signed(values[2]), 'camera': list(map(signed, values[3:6])),
                 'scroll': list(map(signed, values[6:8])), 'editor': bool(values[8]),
                 'helper_markers_hidden': values[9] == 0xe9eb,
                 'visibility_profile': 'gameplay_2d_and_3d' if values[9] == 0xe9eb else 'incomplete',
                 'lighting_mode': 'real_time_grid' if values[11] else 'software_dls',
                 'screen_frame': values[12], 'time_of_day_minutes': values[13],
                 'ambient': values[14], 'ambient_rgb': list(struct.pack('<I',values[15])[:3])[::-1],
                 'ambient_fade_frames': values[16], 'current_screen': values[17],
                 'command': command, 'seconds': time.monotonic() - start}
        rendering=RUNTIME/'control-rendering.bin'
        fixed=False
        if rendering.exists():
            raw=rendering.read_bytes()
            if len(raw)==16:
                magic,seq,enabled,target=struct.unpack('<4I',raw)
                fixed=magic==0x53484457 and seq==sequence and enabled==1
        state['shadow_blend_profile']='rgb565_black_alpha_to_argb1555_v1'if fixed else'unpatched'
        effects=RUNTIME/'control-effects.bin';effect_fixed=False
        if effects.exists():
            raw=effects.read_bytes()
            if len(raw)==16:
                magic,seq,enabled,target=struct.unpack('<4I',raw)
                effect_fixed=magic==0x47455953 and seq==sequence and enabled==1
        state['geyser_blend_profile']='loose_geyser_mesh_litadd_v2'if effect_fixed else'unpatched'
        self.command_log.append(state)
        return state

    def info(self):
        return self.command('@info')

    def view(self, level, x, y, z=0):
        state = self.info()
        if not state['editor']:
            self.command('@editor')
        if state['level'] != level:
            self.command(f'level {level}')
            deadline=time.monotonic()+10
            while self.info()['level']!=level:
                if time.monotonic()>deadline:raise RuntimeError('Original level transition did not finish')
                time.sleep(.02)
            self.command('@wait')
        # The executable calls this command "map"; the source backup calls
        # it "mappos". It does not require a player on the visible level.
        self.command(f'map {x} {y} {z}')
        last_request=time.monotonic()
        deadline = time.monotonic() + 10
        while True:
            state = self.info()
            if state['level'] == level and state['camera'] == [x, y, z]:
                return state
            if time.monotonic() >= deadline:
                raise RuntimeError(f'Camera did not reach requested position: {state}')
            if time.monotonic()-last_request>.5:
                self.command(f'map {x} {y} {z}')
                last_request=time.monotonic()
            time.sleep(.05)

    def window(self):
        desktop = self.desktop_window()
        result = subprocess.run(['xwininfo', '-id', str(desktop), '-tree'], env=self.env,
                                capture_output=True, text=True, timeout=3, check=True)
        windows = re.findall(r'^\s*(0x[0-9a-fA-F]+) "Revenant":', result.stdout, re.MULTILINE)
        if len(windows) != 1:
            raise RuntimeError('Expected exactly one original game window')
        return int(windows[0], 16)

    def capture(self):
        with WindowCapture(self.window(), self.display) as capture:
            return capture.frame().crop((0, 0, 640, 340))

    def desktop_window(self):
        result = subprocess.run(['xdotool', 'search', '--name', '^' + re.escape(DESKTOP) + ' - Wine Desktop$'],
                                env=self.env, capture_output=True, text=True, timeout=3, check=True)
        windows = result.stdout.split()
        if len(windows) != 1:
            raise RuntimeError('Cannot identify isolated Wine desktop backing store')
        return int(windows[0])

    def backing_capture(self):
        return WindowCapture(self.desktop_window(), self.display, composite=True)
