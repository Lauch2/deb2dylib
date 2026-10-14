#!/usr/bin/env python3
"""Rewrite Mach-O LC_LOAD_DYLIB dependency strings (FAT-aware), pure Python.

Ersetzt im Binary alle Vorkommen von <alt> durch <neu> in den Load-Pfaden,
GLEICH LANG oder kürzer (Header-Slots sind fix; kürzer wird mit NUL gepolstert).
Nutzen:  python3 macho_rewrite.py <dylib> "<alt>" "<neu>"
Beispiel: ersetzt @rpath/Cephei.framework/Cephei durch @loader_path/Cephei.dylib
"""
import sys
from pathlib import Path

import struct

def cstr(data: bytes, off: int) -> str:
    end = data.find(b"\x00", off)
    return data[off:end].decode("utf-8", "replace") if end != -1 else ""

def slices(data: bytes):
    if data[:4] == b"\xca\xfe\xba\xbe":  # FAT
        n = struct.unpack_from(">I", data, 4)[0]
        return [(struct.unpack_from(">IIII", data, 8 + i * 20)[2],
                 struct.unpack_from(">IIII", data, 8 + i * 20)[3]) for i in range(n)]
    return [(0, len(data))]

def main():
    path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
    data = bytearray(open(path, "rb").read())
    ob, nb = old.encode(), new.encode()
    if len(nb) > len(ob):
        raise SystemExit(f"Ziel '{new}' länger als '{old}' — geht nicht in den fixen Slot")
    changes = 0
    for off, size in slices(bytes(data)):
        buf = data[off:off + size]
        if len(buf) < 36 or buf[:4] != b"\xcf\xfa\xed\xfe":
            continue
        ncmds, sizeofcmds = struct.unpack_from("<II", buf, 16)
        p = 32
        end = min(32 + sizeofcmds, len(buf))
        for _ in range(ncmds):
            if p + 8 > end:
                break
            cmd, cmdsize = struct.unpack_from("<II", buf, p)
            if cmdsize < 8:
                break
            if cmd == 0x0C:  # LC_LOAD_DYLIB
                name_off = p + 24
                cur = cstr(buf, name_off)
                if cur == old:
                    abs_off = off + name_off
                    data[abs_off:abs_off + len(ob) + 1] = nb + b"\x00" * (len(ob) - len(nb) + 1)
                    changes += 1
            p += cmdsize
    open(path, "wb").write(bytes(data))
    print(f"{changes} Vorkommen von '{old}' -> '{new}' ersetzt in {path}")

if __name__ == "__main__":
    main()