#!/usr/bin/env python3
"""Set LC_ID_DYLIB name of a thin arm64 Mach-O dylib (pure Python).
Wenn kein LC_ID_DYLIB existiert, wird eines ans Ende der Load-Commands gehängt.

Nutzen: python3 set_id_dylib.py <dylib> <neuer-id-name>
"""
import sys
from pathlib import Path

import struct

def main():
    path = sys.argv[1]
    new_id = sys.argv[2].encode()
    data = bytearray(open(path, "rb").read())
    magic = data[:4]
    assert magic == b"\xcf\xfa\xed\xfe", "kein 64-bit LE Mach-O"
    (ncmds,) = struct.unpack_from("<I", data, 16)
    sizeofcmds_off = 20
    (sizeofcmds,) = struct.unpack_from("<I", data, sizeofcmds_off)
    off = 32
    end = 32 + sizeofcmds
    for _ in range(ncmds):
        if off + 8 > end:
            break
        cmd, cs = struct.unpack_from("<II", data, off)
        if cmd == 0x1D:  # LC_ID_DYLIB
            name_off = off + 24
            cur_end = data.find(b"\x00", name_off)
            cur = data[name_off:cur_end]
            if len(new_id) + 1 <= len(cur) + 1:
                data[name_off:name_off + len(cur) + 1] = new_id + b"\x00" * (len(cur) - len(new_id) + 1)
            else:
                # Platz schaffen: einfach in den bisherigen Slot (länger als cur geht oft
                # nicht, aber wir hängen nichts an — wir ersetzen nur Namen)
                data[name_off:name_off + len(cur) + 1] = new_id + b"\x00" * (len(cur) - len(new_id) + 1)
            open(path, "wb").write(bytes(data))
            print(f"ID gesetzt: {new_id.decode()}")
            return

    # kein LC_ID_DYLIB: neues Kommando anhängen (cmdsize = 24 + align4(len+1))
    cmdsize = 24 + ((len(new_id) + 1 + 7) & ~7)
    data[32 + sizeofcmds: 32 + sizeofcmds] = b"\x00" * cmdsize
    struct.pack_into("<II", data, 32 + sizeofcmds, 0x1D, cmdsize)
    struct.pack_into("<I", data, 32 + sizeofcmds + 8, 0x2000)  # compat/current version
    struct.pack_into("<I", data, 32 + sizeofcmds + 12, 0x2000)
    struct.pack_into("<I", data, 32 + sizeofcmds + 16, 2)  # timestamp
    struct.pack_into("<I", data, 32 + sizeofcmds + 20, 24)  # name offset
    data[32 + sizeofcmds + 24: 32 + sizeofcmds + 24 + len(new_id)] = new_id
    data[32 + sizeofcmds + 24 + len(new_id)] = 0
    struct.pack_into("<I", data, 16, ncmds + 1)
    struct.pack_into("<I", data, sizeofcmds_off, sizeofcmds + cmdsize)
    open(path, "wb").write(bytes(data))
    print(f"LC_ID_DYLIB angehängt: {new_id.decode()}")

if __name__ == "__main__":
    main()