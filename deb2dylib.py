#!/usr/bin/env python3
"""deb2dylib — extrahiert .dylib(s) (+ Filter-Plist) aus einem iOS-Tweak-.deb.

Reines Extraktions-Skript: ein .deb ist nur ein Container (ar + tar),
der eigentliche Code liegt bereits als .dylib in
Library/MobileSubstrate/DynamicLibraries/ (bzw. var/jb/...).

Nutzen:  python3 deb2dylib.py tweak.deb [-o ausgabeordner] [--keep-plist]

Dependencies (Substrate/Ellekit) werden NICHT mitgeliefert — die bringt
die Ziel-App (LiveContainer TweakLoader, ESign, xkvm, ...) mit.
"""

import argparse
import lzma
import os
import shutil
import sys
import tarfile
from pathlib import Path

from deb2config import OUT_DIR  # noqa: E402  (lädt config.env)

# Übliche Pfade innerhalb eines Tweak-Debs
DYLIB_HINTS = (
    "Library/MobileSubstrate/DynamicLibraries/",
    "var/jb/Library/MobileSubstrate/DynamicLibraries/",
    "var/mobile/Library/Preferences/",
    "Library/PreferenceLoader/Preferences/",
)


def extract_deb(deb_path: Path, out_dir: Path, keep_plist: bool) -> list[Path]:
    import subprocess  # ar ist kein Python-Stdlib-Modul

    staging = out_dir / "_stage"
    staging.mkdir(parents=True, exist_ok=True)

    # ar extrahieren (Debian-Paket = ar-Archiv); absolut wegen cwd=staging
    subprocess.run(["ar", "x", str(deb_path.resolve())], cwd=staging, check=True)
    data_archives = [p for p in staging.iterdir() if p.name.startswith("data.tar")]
    if not data_archives:
        raise SystemExit("Kein data.tar.* im deb gefunden — kein gültiges Tweak-Paket?")

    result: list[Path] = []
    for data_archive in data_archives:
        ext = data_archive.suffix  # .gz/.xz/.lzma/.zst/.bz2
        mode = {"": "r", ".gz": "r:gz", ".xz": "r:xz", ".lzma": "r:xz",
                ".bz2": "r:bz2", ".zst": "r"}.get(ext, "r:*")
        with tarfile.open(data_archive, mode) as tar:
            for member in tar.getmembers():
                name = member.name.lstrip("./")
                lower = name.lower()
                if not member.isfile():
                    continue
                is_dylib = lower.endswith(".dylib") or lower.endswith(".dylib/")
                if not is_dylib:
                    continue
                # Nur MobileSubstrate-DynamicLibraries-Pfade, keine Frameworks
                if "DynamicLibraries/" not in lower.replace("//", "/"):
                    if "Frameworks/" in lower:
                        continue
                # Ziel: Name aus dem Pfad
                target = out_dir / Path(name).name
                with tar.extractfile(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                result.append(target)
                print(f"  + {target.name}  ({target.stat().st_size} Bytes)")

            if keep_plist:
                for member in tar.getmembers():
                    name = member.name.lstrip("./")
                    if name.endswith(".plist") and "DynamicLibraries/" in name.replace("//", "/"):
                        target = out_dir / Path(name).name
                        with tar.extractfile(member) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        print(f"  + {target.name}  (Filter-Plist)")

    shutil.rmtree(staging, ignore_errors=True)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Tweak-.deb -> .dylib extrahieren")
    ap.add_argument("deb", type=Path, help="Pfad zur .deb-Datei")
    ap.add_argument("-o", "--out", type=Path, default=OUT_DIR, help="Ausgabeordner (Default: aus config.env)")
    ap.add_argument("--keep-plist", action="store_true", help="Filter-Plist mitkopieren (Bundle-ID-Filter)")
    args = ap.parse_args()

    if not args.deb.exists():
        raise SystemExit(f"Datei nicht gefunden: {args.deb}")

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"Extrahiere {args.deb.name} nach {args.out}/")
    files = extract_deb(args.deb, args.out, args.keep_plist)
    if not files:
        print("  (!) Kein .dylib gefunden — ist das wirklich ein iOS-Tweak-Deb?")
        return 1
    print(f"Fertig: {len(files)} Datei(en). Injizieren z. B. per xkvm / ESign / LiveContainer-Import.")
    return 0


if __name__ == "__main__":
    sys.exit(main())