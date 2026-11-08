"""Execute the injected x86 filter: narrow matching, preserved state and flags."""
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(platform.system() == 'Linux' and platform.machine() in ('x86_64', 'i386', 'i686')
                     and shutil.which('as') and shutil.which('ld'), 'Needs Linux x86 and binutils')
class SpeakerFilterTest(unittest.TestCase):
    def test_only_exact_effect_placeholder_is_skipped(self):
        source = (Path(__file__).parents[1] / 'native/retail_control.c').read_text()
        block = source.split('unsigned char code[]={', 1)[1].split('};', 1)[0]
        block = re.sub(r'/\*.*?\*/', '', block, flags=re.S)
        code = bytes(int(word.strip(), 0) for word in block.split(',') if word.strip())
        self.assertEqual(len(code), 57)
        self.assertEqual(code[39], 0xe9)
        self.assertEqual(code[52], 0xe9)
        cases = [(25, 'speaker', 0, True), (25, 'speaker', 128, True),
                 (9, 'speaker', 0, False), (9, 'speaker', 256, False),
                 (25, 'speaker2', 0, False), (25, 'speak', 128, False),
                 (25, 'WaveM', 0, False), (25, 'Speaker', 256, False),
                 (25, None, 0, False), (25, None, 128, False),
                 (25, '', 0, False), (25, '', 256, False)]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # Relocate only the two external jumps, exactly as the controller does.
            payload = '.byte ' + ','.join(hex(b) for b in code[:40]) + '\n'
            payload += '.long skipped - . - 4\n.byte ' + ','.join(hex(b) for b in code[44:53])
            payload += '\n.long normal - . - 4\n'
            program = ['.intel_syntax noprefix', '.code32', '.global _start', '.text', '_start:']
            data = []
            for index, (cls, name, flags, hidden) in enumerate(cases):
                pointer = '0' if name is None else 'OFFSET info'
                name_pointer = '0' if not name else f'OFFSET name{index}'
                if name is not None:
                    data.append(f'name{index}: .asciz "{name}"')
                program += [f'mov word ptr [object+4],{cls}', f'mov dword ptr [object+8],{flags}',
                            f'mov dword ptr [object+0x4c],{pointer}', f'mov dword ptr [info],{name_pointer}',
                            'mov ebx,OFFSET object', 'mov eax,0x11223344', 'mov edx,0x55667788',
                            'mov esi,esp', 'call filter', 'cmp esp,esi', 'jne failure',
                            'cmp eax,0x11223344', 'jne failure', 'cmp edx,0x55667788', 'jne failure',
                            f'cmp edi,{int(hidden)}', 'jne failure']
                if not hidden:
                    program += ['and ecx,0x40', f'cmp ecx,{0 if flags & 0x180 else 0x40}', 'jne failure']
            program += ['xor ebx,ebx', 'jmp exit', 'failure:', 'mov ebx,1', 'exit:',
                        'mov eax,1', 'int 0x80', 'filter:', payload,
                        'normal:', 'pushfd', 'pop ecx', 'mov edi,0', 'ret',
                        'skipped:', 'mov edi,1', 'ret', '.data', *data,
                        '.bss', '.align 4', 'object: .skip 0x50', 'info: .skip 4']
            (root / 'filter.S').write_text('\n'.join(program) + '\n')
            subprocess.run(['as', '--32', str(root/'filter.S'), '-o', str(root/'filter.o')], check=True)
            subprocess.run(['ld', '-m', 'elf_i386', '-o', str(root/'filter'), str(root/'filter.o')], check=True)
            result = subprocess.run([str(root/'filter')], timeout=5)
            self.assertEqual(result.returncode, 0, 'Injected filter changed an unrelated draw, register or stack')
