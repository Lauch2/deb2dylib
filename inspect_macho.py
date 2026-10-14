#!/usr/bin/env python3
"""Print all load commands incl. FAT header handling for a Mach-O dylib.

Nutzen: python3 inspect_macho.py <dylib>
"""
import sys
from pathlib import Path

import struct

path = sys.argv[1]
data = open(path, 'rb').read()

def parse_macho(buf, label):
    magic = buf[:4]
    if magic == b'\xcf\xfa\xed\xfe':  # 64-bit LE
        ncmds, sz = struct.unpack_from('<II', buf, 16)
        off = 32
    elif magic == b'\xce\xfa\xed\xfe':  # 32-bit LE
        ncmds, sz = struct.unpack_from('<II', buf, 16)
        off = 28
    else:
        print(f'{label}: kein Mach-O (magic {magic.hex()})')
        return
    print(f'{label}: {ncmds} cmds')
    for i in range(ncmds):
        if off + 8 > len(buf):
            break
        cmd, cmdsize = struct.unpack_from('<II', buf, off)
        if cmd == 0x0C:  # LC_LOAD_DYLIB
            name_off = off + 24
            end = buf.find(b'\x00', name_off)
            print(f'  LC_LOAD_DYLIB: {buf[name_off:end].decode("utf-8", "replace")}')
        elif cmd == 0x1C:  # LC_RPATH
            name_off = off + 12
            end = buf.find(b'\x00', name_off)
            print(f'  LC_RPATH: {buf[name_off:end].decode("utf-8", "replace")}')
        off += cmdsize

if data[:4] == b'\xca\xfe\xba\xbe':  # FAT
    nfat = struct.unpack_from('>I', data, 4)[0]
    print(f'FAT mit {nfat} Architekturen:')
    for i in range(nfat):
        cpu, _, offset, size = struct.unpack_from('>IIII', data, 8 + i * 20)
        print(f'  Arch cpu={hex(cpu)} off={offset} size={size}')
        parse_macho(data[offset:offset + size], f'  [{hex(cpu)}]')
else:
    parse_macho(data, 'Macho')