#!/usr/bin/env python3
"""Strip an arm64 slice out of a FAT Mach-O, pure Python.

Nutzen: python3 fat_strip.py <dylib>
"""
import sys
from pathlib import Path

import struct

def main():
    path = sys.argv[1]
    data = open(path, "rb").read()
    assert data[:4] == b"\xca\xfe\xba\xbe", "not FAT"
    n = struct.unpack_from(">I", data, 4)[0]
    chosen = None
    for i in range(n):
        cpu, _, off, size = struct.unpack_from(">IIII", data, 8 + i * 20)
        # 0x100000c = arm64e (caps), 0xC = arm64
        if cpu in (0x100000C, 0xC):
            chosen = (off, size)
    if not chosen:
        raise SystemExit("kein arm64/arm64e-Slice gefunden")
    off, size = chosen
    open(path, "wb").write(data[off:off + size])
    print(f"{path}: {size} Bytes arm64-Slice extrahiert")

if __name__ == "__main__":
    main()