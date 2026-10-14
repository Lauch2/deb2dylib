#!/usr/bin/env python3
"""deb2dylib-livecontainer — iOS-Tweak-.deb -> LiveContainer-Tweak-Ordner.

Ein .deb ist nur ein Container (ar + tar), der Code liegt bereits als
.dylib in Library/MobileSubstrate/DynamicLibraries/. Dieses Skript:

  1. extrahiert .dylib(s) + Filter-Plist aus dem deb
  2. schreibt Dependency-Load-Pfade auf LiveContainer-kompatible um:
       /usr/lib/..., /System/Library/Frameworks/...  →
         @rpath/usr/lib/..., @rpath/System/Library/Frameworks/...
     (System-Frameworks bleiben unangetastet — die liegen absolut auf
     jedem Gerät; nur Substrate/Hook-Libs sind kritisch: LiveContainer
     lädt CydiaSubstrate global via TweakLoader, @rpath ersetzt absolute
     Substrate-Pfade wie /Library/Frameworks/...)
  3. verarbeitet FAT-Binaries (arm64, armv7, arm64e) korrekt, indem jede
     Arch-Sektion einzeln geparst und umgeschrieben wird (Pure-Python,
     kein externes Tool nötig)

LiveContainer kann KEINE .deb direkt laden (nur .dylib/.framework — siehe
Issue #167 / TweakLoader.m). Nach dem Import: Sign-Button drücken (Signatur
wird von LiveContainer beim Import automatisch erneuert, Issue #597).

Abhängigkeit: `ar`-Kommando (binutils) für die deb-Extraktion.
Nutzen:
  python3 deb2dylib-livecontainer.py tweak.deb -o tweaksOrder/
  # erzeugt: tweaksOrder/<tweak>.dylib (+ <tweak>.plist)
  # Diese Dateien dann in LiveContainer: Tweaks-Tab -> + -> Import (dylib)
"""

import argparse
import os
import shutil
import struct
import subprocess
import sys
import tarfile
from pathlib import Path

SUBSTRATE_REPLACEMENT = "@rpath"

from deb2config import OUT_DIR  # noqa: E402  (lädt config.env)          # LiveContainer lädt Substrate global


# ---------- Mach-O (64-bit LE + FAT) ----------

def _cstr(data: bytes, off: int) -> str:
    end = data.find(b"\x00", off)
    return data[off:end].decode("utf-8", errors="replace") if end != -1 else ""


def _parse_slices(data: bytes):
    """Liefert (offset, size) je Mach-O-Slice; bei FAT alle, sonst [ (0, len) ]."""
    if data[:4] == b"\xca\xfe\xba\xbe":  # FAT
        nfat = struct.unpack_from(">I", data, 4)[0]
        slices = []
        for i in range(nfat):
            _, _, offset, size = struct.unpack_from(">IIII", data, 8 + i * 20)
            slices.append((offset, size))
        return slices
    return [(0, len(data))]


def rewrite_macho_load_paths(dylib_path: Path) -> list[str]:
    """Ersetzt Substrate/Hook-Pfade durch @rpath-Varianten (je Arch-Slice)."""
    data = bytearray(dylib_path.read_bytes())
    changed: list[str] = []
    for offset, size in _parse_slices(bytes(data)):
        buf = data[offset:offset + size]
        if len(buf) < 36 or buf[:4] != b"\xcf\xfa\xed\xfe":
            continue  # kein 64-bit LE-Slice (armv7 übersprungen)
        ncmds, sizeofcmds = struct.unpack_from("<II", buf, 16)
        off = 32
        end = min(32 + sizeofcmds, len(buf))
        for _ in range(ncmds):
            if off + 8 > end:
                break
            cmd, cmdsize = struct.unpack_from("<II", buf, off)
            if cmdsize < 8:
                break
            if cmd == 0x0C:  # LC_LOAD_DYLIB
                name_off = off + 24
                old = _cstr(buf, name_off)
                new = None
                if old.startswith("/Library/MobileSubstrate/"):
                    new = SUBSTRATE_REPLACEMENT + old[len("/Library/MobileSubstrate/"):]
                elif old.startswith("/Library/Frameworks/"):
                    new = SUBSTRATE_REPLACEMENT + "/" + old[len("/Library/Frameworks/"):]
                elif old.startswith("/usr/lib/libsubstrate"):
                    new = SUBSTRATE_REPLACEMENT + "/usr/lib/" + old.rsplit("/", 1)[1]
                elif old.startswith("/var/jb/"):
                    new = SUBSTRATE_REPLACEMENT + old[len("/var/jb/"):]
                if new and new != old:
                    if len(new.encode()) + 1 <= len(old.encode()) + 1:
                        # @rpath-Varianten sind kürzer/gleich lang — sicher ersetzen
                        abs_off = offset + name_off
                        data[abs_off:abs_off + len(old.encode()) + 1] = new.encode() + b"\x00"
                        changed.append(f"[+{offset:#x}] {old} -> {new}")
            off += cmdsize
    if changed:
        dylib_path.write_bytes(bytes(data))
    return changed


# ---------- deb extrahieren ----------

def extract_deb(deb: Path, out: Path) -> list[Path]:
    staging = out / "_stage"
    staging.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ar", "x", str(deb.resolve())], cwd=staging, check=True)
    archives = [p for p in staging.iterdir() if p.name.startswith("data.tar")]
    if not archives:
        raise SystemExit("Kein data.tar.* im deb — kein gültiges Tweak-Paket?")
    found: list[Path] = []
    for arc in archives:
        mode = {"": "r", ".gz": "r:gz", ".xz": "r:xz", ".lzma": "r:xz",
                ".bz2": "r:bz2", ".zst": "r"}.get(arc.suffix, "r:*")
        with tarfile.open(arc, mode) as tar:
            for m in tar.getmembers():
                if not m.isfile():
                    continue
                name = m.name.lstrip("./")
                low = name.lower()
                if low.endswith(".dylib") and "DynamicLibraries/" in "/" + name:
                    tgt = out / Path(name).name
                    with tar.extractfile(m) as src, open(tgt, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found.append(tgt)
                    print(f"  + {tgt.name}  ({tgt.stat().st_size} Bytes)")
                elif low.endswith(".plist") and "DynamicLibraries/" in "/" + name:
                    tgt = out / Path(name).name
                    with tar.extractfile(m) as src, open(tgt, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    print(f"  + {tgt.name}  (Filter-Plist)")
                elif "/frameworks/" in "/" + low and low.endswith(".framework/") is False:
                    # Framework-Binary: Pfad <Name>.framework/<Binary>
                    if ".framework/" in low and low.endswith(".dylib") is False:
                        fw_dir_name = Path(name).parent.name  # z. B. Cephei.framework
                        tgt_dir = out / fw_dir_name
                        tgt_dir.mkdir(parents=True, exist_ok=True)
                        tgt = tgt_dir / Path(name).name
                        with tar.extractfile(m) as src, open(tgt, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        print(f"  + {fw_dir_name}/{Path(name).name}  ({tgt.stat().st_size} Bytes)")
                        found.append(tgt)
                    elif low.endswith("/info.plist"):
                        fw_dir_name = Path(name).parent.name
                        tgt_dir = out / fw_dir_name
                        tgt_dir.mkdir(parents=True, exist_ok=True)
                        tgt = tgt_dir / Path(name).name
                        with tar.extractfile(m) as src, open(tgt, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        print(f"  + {fw_dir_name}/Info.plist")
    shutil.rmtree(staging, ignore_errors=True)
    return found


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Tweak-.deb -> LiveContainer-Tweak-Ordner (dylib + plist + Rewrites)")
    ap.add_argument("deb", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=OUT_DIR, help="Ausgabeordner (Default: aus config.env)")
    ap.add_argument("--no-rewrite", action="store_true",
                    help="Dependency-Pfade NICHT umschreiben (nur extrahieren)")
    args = ap.parse_args()
    if not args.deb.exists():
        raise SystemExit(f"Datei nicht gefunden: {args.deb}")
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"Extrahiere {args.deb.name} nach {args.out}/")
    files = extract_deb(args.deb, args.out)
    if not files:
        print("  (!) Kein .dylib gefunden — kein iOS-Tweak-Deb?")
        return 1

    if not args.no_rewrite:
        for f in files:
            changes = rewrite_macho_load_paths(f)
            print(f"  Rewrite {f.name}:")
            for c in changes:
                print(f"    {c}")
            if not changes:
                print("    (keine Substrate/Hook-Pfade zu ersetzen)")
    else:
        print("  (--no-rewrite: Load-Pfade unverändert)")

    print("\nFertig. In LiveContainer:")
    print("  Tweaks-Tab -> + -> Import (dylib)  ODER")
    print("  per Dateien-App in den Tweak-Ordner von LiveContainer legen,")
    print("  dann im Tweaks-Tab auf Sign drücken (wichtig! Issue #597).")
    return 0


if __name__ == "__main__":
    sys.exit(main())