"""Control an isolated GOG 1.22L installation; never reuse July addresses."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import time

from .game import DEFAULT_WINE, ROOT
from .x11_capture import WindowCapture

EXE_SHA256 = '28bec27387bf53a553da320dd4883d00ff5bcc5a5f3d2658cca8e8ed586372b5'
RUNTIME = Path(os.environ.get('REVENANT_RETAIL_RUNTIME', ROOT / 'runtime/retail')).resolve()
DESKTOP = os.environ.get('REVENANT_RETAIL_DESKTOP', 'RevenantRetail')
DATA = Path(os.environ.get('REVENANT_RETAIL_DATA', ROOT / 'runtime/retail-extracted')).resolve()


def build():
    RUNTIME.mkdir(parents=True,exist_ok=True)
    source = Path(__file__).with_name('retail_control.c')
    for dll in ('user32','kernel32'):
        subprocess.run(['i686-w64-mingw32-dlltool','-d',str(source.with_name(f'{dll}.def')),
            '-l',str(RUNTIME/f'control-{dll}.a'),'--kill-at'],check=True)
    subprocess.run(['clang-18', '--target=i686-pc-windows-msvc', '-fno-stack-protector',
                    '-c', str(source), '-o', str(RUNTIME/'retail-control.obj')], check=True)
    subprocess.run(['i686-w64-mingw32-ld', '--entry', '_mainCRTStartup', '--subsystem', 'windows',
                    '-o', str(RUNTIME/'native-control.exe.tmp'), str(RUNTIME/'retail-control.obj'),
                    str(RUNTIME/'control-user32.a'), str(RUNTIME/'control-kernel32.a')], check=True)
    (RUNTIME/'native-control.exe.tmp').replace(RUNTIME/'native-control.exe')


def next_sequence(runtime):
    """Keep command IDs monotonic after an interrupted counter write."""
    runtime=Path(runtime);counter=runtime/'control-sequence.txt';values=[0]
    try:values.append(int(counter.read_text()))
    except(FileNotFoundError,ValueError):pass
    try:
        state=struct.unpack('<18I',(runtime/'control-state.bin').read_bytes())
        if state[0]==0x41544c53:values.append(state[10])
    except(FileNotFoundError,struct.error):pass
    sequence=max(values)+1
    temporary=counter.with_suffix('.tmp');temporary.write_text(str(sequence));temporary.replace(counter)
    return sequence


class RetailGame:
    def __init__(self):
        actual = hashlib.sha256((DATA/'Revenant.exe').read_bytes()).hexdigest()
        if actual != EXE_SHA256:
            raise RuntimeError('Retail executable differs; its controller must be reverified')
        self.env = dict(os.environ, DISPLAY=os.environ.get('REVENANT_DISPLAY',os.environ.get('DISPLAY',':0')),
            WINEPREFIX=str(RUNTIME/'prefix'), WINEDEBUG='-all')
        if os.environ.get('REVENANT_AUDIO_SINK'):
            self.env['PULSE_SINK'] = os.environ['REVENANT_AUDIO_SINK']
        self.wine = str(DEFAULT_WINE)

    def command(self, command):
        with (RUNTIME/'control.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            helper=RUNTIME/'native-control.exe'
            source=Path(__file__).with_name('retail_control.c')
            stale=helper.exists()and helper.stat().st_mtime_ns<source.stat().st_mtime_ns
            if stale:
                pidfile=RUNTIME/'control-server.pid'
                try:
                    pid=int(pidfile.read_text());process=Path(f'/proc/{pid}')
                    if (b'native-control'in(process/'cmdline').read_bytes()
                            and b'WINEPREFIX='+str(RUNTIME/'prefix').encode()in(process/'environ').read_bytes().split(b'\0')):
                        os.kill(pid,signal.SIGTERM)
                except(OSError,ValueError):pass
                pidfile.unlink(missing_ok=True)
            if not helper.exists()or stale:
                build()
            pidfile = RUNTIME/'control-server.pid'
            alive = False
            try:
                alive = b'native-control' in Path(f'/proc/{int(pidfile.read_text())}/cmdline').read_bytes()
            except (OSError, ValueError):
                pass
            if not alive:
                (RUNTIME/'control-request.bin').unlink(missing_ok=True)
                with (RUNTIME/'control.log').open('ab') as log:
                    p = subprocess.Popen([self.wine, str(RUNTIME/'native-control.exe'), '--serve'],
                        env=self.env, cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                        start_new_session=True)
                pidfile.write_text(str(p.pid))
            seq = next_sequence(RUNTIME)
            data = command.encode('ascii')
            if len(data) > 253:
                raise ValueError('Native command too long')
            temp = RUNTIME/'control-request.tmp'
            temp.write_bytes(struct.pack('<II', seq, len(data)) + data)
            temp.replace(RUNTIME/'control-request.bin')
            deadline = time.monotonic() + (40 if command=='@wait' else 20)
            while True:
                try:
                    raw = (RUNTIME/'control-state.bin').read_bytes()
                    values = struct.unpack('<18I', raw)
                    if values[0] == 0x41544c53 and values[10] == seq:
                        break
                except (OSError, struct.error):
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError(f'Retail controller timeout: {command}')
                time.sleep(.005)
            if values[1]:
                raise RuntimeError(f'Retail command failed ({values[1]}): {command}')
            signed = lambda v: struct.unpack('<i', struct.pack('<I', v))[0]
            state=dict(level=signed(values[2]), camera=list(map(signed, values[3:6])),
                scroll=list(map(signed, values[6:8])), editor=bool(values[8]),
                visibility_profile='gameplay_2d_and_3d' if values[9] & 0xffff == 0xe9eb else 'incomplete',
                sound_marker_profile='speaker_mesh_hidden_v1' if values[9] & 0x10000 else 'unfiltered',
                shadow_blend_profile='retail_original_raster',
                geyser_blend_profile='retail_authored_blend_controllers',
                lighting_mode='real_time_grid' if values[11] else 'software_dls',
                screen_frame=values[12], time_of_day_minutes=values[13], ambient=values[14],
                ambient_rgb=list(struct.pack('<I', values[15])[:3])[::-1],
                ambient_fade_frames=values[16], current_screen=values[17],
                provider='original_retail_1.22L', executable_sha256=EXE_SHA256,
                rendering_patch='none', command=command)
            if command.startswith('@memory '):state['_memory_hex']=(RUNTIME/'control-memory.bin').read_bytes().hex()
            return state

    def info(self):
        return self.command('@info')

    def module_info(self):
        def memory(address,size):
            return bytes.fromhex(self.command(f'@memory {address:x} {size}')['_memory_hex'])
        for _ in range(3):
            manager=struct.unpack('<8I',memory(0x65a768,32));index=manager[7]
            if index==0xffffffff:return dict(module_index=-1,native_module='')
            if index>=manager[1]or manager[1]>128:raise ValueError('Invalid native module catalog')
            pointer=struct.unpack('<I',memory(manager[5]+index*4,4))[0]
            name=memory(pointer+0x58,260).split(b'\0',1)[0].decode('cp1252')
            after=struct.unpack('<8I',memory(0x65a768,32))
            if manager==after:return dict(module_index=index,native_module=name)
        raise RuntimeError('Native module changed during observation')

    def mount(self,module):
        observed=self.module_info()
        if observed['native_module'].casefold()!=module.casefold():
            # Let the old area's Exit clear its scripts before changing packs.
            # Otherwise retail reloads e.g. keep.s from a deathmatch pack.
            self.command('level 90');self.command('map 10000 10000 0');self.command('@wait')
            self.command(f'setcurmodule "{module}"');self.command('@wait')
            observed=self.module_info()
        if observed['native_module'].casefold()!=module.casefold():
            raise RuntimeError(f'Original engine did not mount the requested module: {observed}')
        self.capture_module_observation=observed
        return observed

    def prepare_capture(self):
        """Select authored ambient through retail setters, avoiding its fade gamma loss."""
        profile=getattr(self,'capture_lighting',None)
        state=self.info()
        if profile:
            if (state['ambient']!=profile['expected_native_ambient']
                    or state['ambient_rgb']!=profile['ambient_rgb']or state['ambient_fade_frames']):
                self.command(f'amb {profile["ambient"]}')
                self.command('ambcolor '+' '.join(map(str,profile['ambient_rgb'])))
                self.command('@wait');state=self.info()
            if (state['ambient']!=profile['expected_native_ambient']
                    or state['ambient_rgb']!=profile['ambient_rgb']or state['ambient_fade_frames']):
                raise RuntimeError('Retail authored ambient did not match the pinned GammaLevel 3 target')
            state['capture_lighting_policy']=profile['policy']
        if getattr(self,'capture_module_observation',None):state.update(self.capture_module_observation)
        return state

    def view(self, level, x, y, z=0):
        state = self.info()
        if not state['editor']:
            self.command('@editor')
        if state['level'] != level:
            self.command(f'level {level}')
            deadline=time.monotonic()+15
            while self.info()['level'] != level:
                if time.monotonic()>deadline:
                    raise RuntimeError('Retail level transition did not finish')
                time.sleep(.05)
            self.command('@wait')
        self.command(f'map {x} {y} {z}')
        deadline = time.monotonic() + 15
        requested=time.monotonic()
        while True:
            state = self.info()
            if state['level'] == level and state['camera'] == [x, y, z]:
                return state
            if time.monotonic() > deadline:
                raise RuntimeError(f'Retail camera did not settle: {state}')
            if time.monotonic()-requested>.5:
                if state['level'] != level:self.command(f'level {level}')
                self.command(f'map {x} {y} {z}')
                requested=time.monotonic()
            time.sleep(.05)

    def desktop_window(self):
        r = subprocess.run(['xwininfo', '-root', '-tree'],
                           env=self.env, check=True, text=True, capture_output=True)
        windows = re.findall(r'(0x[0-9a-f]+) "'+re.escape(DESKTOP)+r' - Wine Desktop"', r.stdout)
        if len(windows) != 1:
            raise RuntimeError('Expected one isolated retail desktop')
        return int(windows[0], 16)

    def window(self):
        r = subprocess.run(['xwininfo', '-id', str(self.desktop_window()), '-tree'],
                           env=self.env, check=True, text=True, capture_output=True)
        windows = re.findall(r'(0x[0-9a-f]+) "Revenant"', r.stdout)
        if len(windows) != 1:
            raise RuntimeError('Expected one original retail game window')
        return int(windows[0], 16)

    def backing_capture(self):
        return RetailCapture(self)


class RetailCapture:
    """Reacquire an XComposite pixmap after a Wine desktop surface changes."""
    def __init__(self,game):
        self.game=game
        self.capture=None
        self.backing_policy='current_pixmap_each_read_v1'

    def frame(self):
        for attempt in range(20):
            try:
                if self.capture is None:
                    window=self.game.desktop_window()
                    # A private capture desktop must stay mapped for XComposite.
                    # Mapping it does not raise it or change the user's focus.
                    subprocess.run(['xdotool','windowmap',str(window)],env=self.game.env,
                        check=True,capture_output=True,timeout=3)
                    self.capture=WindowCapture(window,self.game.env['DISPLAY'],composite=True)
                    # Mapping a Wine desktop can briefly expose the previous
                    # compositor contents. Redraw after mapping, before reading
                    # the first pixmap, rather than trusting a pre-map barrier.
                    self.game.command('mono 0')
                    self.game.command('@wait')
                    self.window_barrier='native_redraw_after_map_v1'
                return self.capture.frame()
            except (RuntimeError,subprocess.SubprocessError):
                self.close()
                time.sleep(.05)
        raise RuntimeError('Retail desktop backing store did not become available')

    def close(self):
        if self.capture:
            self.capture.close()
            self.capture=None

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


if __name__ == '__main__':
    import sys
    game = RetailGame()
    print(json.dumps(game.command(' '.join(sys.argv[1:]) or '@info'), indent=2))
