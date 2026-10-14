# deb2dylib

Extract and patch iOS tweak `.deb` packages for use with **LiveContainer** on iPad (no jailbreak required).

LiveContainer loads `.dylib` / `.framework` files directly — it cannot import `.deb` files (see [Issue #167](https://github.com/LiveContainer/LiveContainer/issues/167)). This toolkit extracts the tweak binary, rewrites absolute Substrate dependency paths to `@rpath`-relative ones (FAT-binary aware), and outputs a LiveContainer-ready tweak folder.

---

## The Problem

A `.deb` is just an `ar` archive containing a `data.tar.*` payload. The actual tweak code lives at:

```
Library/MobileSubstrate/DynamicLibraries/<tweak>.dylib
```

Tweak dylibs often reference Substrate via **absolute paths** that don't exist on the device:

| Original (in dylib) | LiveContainer Reality |
|---------------------|----------------------|
| `/Library/MobileSubstrate/DynamicLibraries/foo.dylib` | Substrate loaded globally via `TweakLoader` |
| `/Library/Frameworks/Foo.framework/Foo` | Must be found via `@rpath` |
| `/usr/lib/libsubstrate.dylib` | Global, not at absolute path |

**Solution:** Rewrite all Substrate/Hook-related `LC_LOAD_DYLIB` entries to `@rpath/...` — per architecture slice for FAT binaries (arm64/arm64e).

---

## Features

- ✅ **Full `.deb` → `.dylib` + `.plist` extraction** (no `dpkg` needed)
- ✅ **Automatic `@rpath` rewriting** for Substrate, CydiaSubstrate, framework paths
- ✅ **FAT binary support** — parses `0xcafebabe` header, patches each slice independently
- ✅ **Framework extraction** — preserves `Cephei.framework` etc. with `Info.plist`
- ✅ **GitHub Release scanner** — finds latest `.deb` assets for known tweak repos
- ✅ **Mach-O tooling** — inspect, strip, rewrite, set `LC_ID_DYLIB`
- ✅ **Config-driven** — output dir, GitHub token in gitignored `config.env`

---

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| `ar` (binutils) | Extract `.deb` (ar archive) | `apt install binutils` / `dnf install binutils` |
| Python 3.11+ | All scripts | System package |
| `pycryptodome` | Required only for `fat_strip.py` | `pip install pycryptodome` |

---

## Quick Start

```bash
# 1) Clone & configure
git clone https://github.com/Lauch2/deb2dylib.git
cd deb2dylib
cp config.example.env config.env
$EDITOR config.env   # Set OUT_DIR=./tweaksOrder (default), optional GITHUB_TOKEN

# 2) Convert a tweak .deb → LiveContainer-ready
python3 deb2dylib-livecontainer.py /path/to/tweak.deb -o tweaksOrder/

# 3) Import in LiveContainer
#    Tweaks tab → + → Import (dylib) → select tweaksOrder/<tweak>.dylib
#    ⚠️  CRITICAL: Tap "Sign" in the Tweaks tab after import (Issue #597)
```

---

## Configuration

`config.env` (gitignored):

```bash
# Output directory for extracted/patched tweaks
OUT_DIR=./tweaksOrder

# Optional: GitHub token for tweak_finder.py (5000 req/h vs 60/h unauthenticated)
# GITHUB_TOKEN=ghp_xxxx
```

---

## Scripts Reference

| Script | Description |
|--------|-------------|
| `deb2dylib-livecontainer.py` | **Main** — extract `.dylib` + filter `.plist`, rewrite all Substrate/Hook paths to `@rpath`, FAT-aware |
| `deb2dylib.py` | Extract only — no path rewriting |
| `fat_strip.py` | Extract single arm64 slice from FAT binary (in-place) |
| `inspect_macho.py` | List all load commands (`LC_LOAD_DYLIB`, `LC_RPATH`, etc.) + FAT header |
| `macho_rewrite.py` | Replace a single load path across all arch slices (target ≤ source length) |
| `set_id_dylib.py` | Set or append `LC_ID_DYLIB` (install name) on thin arm64 dylib |
| `tweak_finder.py` | Scan known tweak repos (GitHub Releases) for latest `.deb` assets |

---

## Usage Examples

### Find & convert popular tweaks

```bash
# List current releases from tracked repos
python3 tweak_finder.py

# Download .deb files, then convert:
python3 deb2dylib-livecontainer.py com.dvntm.ytlite_5.2.2_iphoneos-arm64.deb
python3 deb2dylib-livecontainer.py com.test.h5gg_8.0.0_iphoneos-arm.deb
python3 deb2dylib-livecontainer.py com.bandarhl.bhinsta_1.2_iphoneos-arm64.deb
# → tweaksOrder/*.dylib + *.plist
```

### Manual Mach-O inspection & patching

```bash
# Show all load commands (handles FAT)
python3 inspect_macho.py tweaksOrder/Tweak.dylib

# Replace one dependency path globally (all slices)
python3 macho_rewrite.py tweaksOrder/Tweak.dylib \
  "/Library/MobileSubstrate/DynamicLibraries/substrate.dylib" \
  "@rpath/substrate.dylib"

# Set install name so dyld finds it at @rpath
python3 set_id_dylib.py tweaksOrder/Tweak.dylib "@rpath/Tweak.dylib"

# Strip to thin arm64 if needed
python3 fat_strip.py tweaksOrder/Tweak.dylib
```

---

## Supported Repos (via `tweak_finder.py`)

| Tweak | Repo | Arch |
|-------|------|------|
| YTLite (YouTube) | `dayanch96/YTLite` | arm64 |
| H5GG (Mod Engine) | `Mods-Center-iOS/H5GG-Revamped` | arm64 |
| BHInstagram | `BandarHL/BHInstagram` | arm64 |
| Rocket (Instagram) | `annulya/rocket` | arm64 |
| SafariPlus | `opa334/SafariPlus` | arm64 |

---

## Verified Tweaks

| Tweak | Bundle ID / Source | Size | Status |
|-------|-------------------|------|--------|
| YTLite | `com.dvntm.ytlite` | 7.3 MB | ✅ Works |
| H5GG | `com.test.h5gg` | 468 KB | ✅ Works |
| BHInstagram | `com.bandarhl.bhinsta` | 70 KB | ✅ Works |
| Cephei Framework | — | 199 KB | Framework → own folder |
| Rocket | `annulya/rocket` | 1.4 MB | `.deb` available |

---

## Common Pitfalls

| Symptom | Fix |
|---------|-----|
| Tweak loads but hook doesn't fire | **Tap "Sign" in LiveContainer Tweaks tab** (signature renewed on import, [Issue #597](https://github.com/LiveContainer/LiveContainer/issues/597)) |
| `dyld: Library not loaded: /Library/MobileSubstrate/...` | Run `deb2dylib-livecontainer.py` to rewrite paths to `@rpath` |
| `macho_rewrite.py`: "target longer than source" | Target path must be ≤ original (fixed-size slot in Mach-O header) |
| Only one FAT slice patched | Scripts process all slices — verify with `inspect_macho.py` |
| `tweak_finder.py` returns nothing | GitHub rate limit (60/h) — add `GITHUB_TOKEN` to `config.env` |

---

## Framework Handling (Cephei, etc.)

Some tweaks bundle frameworks (e.g., `Cephei.framework`). The main script extracts the full framework directory (`Binary` + `Info.plist` + resources) to `tweaksOrder/Cephei.framework/`.

In LiveContainer, place the framework **alongside** the tweak dylib in the same import folder — dyld resolves `@rpath/Cephei.framework/Cephei` correctly.

---

## Project Structure

```
deb2dylib/
├── deb2config.py                    # Config loader (reads config.env)
├── deb2dylib-livecontainer.py       # Main: .deb → dylib + plist + @rpath rewrites
├── deb2dylib.py                     # Extract only (no rewrites)
├── fat_strip.py                     # FAT → thin arm64
├── inspect_macho.py                 # List load commands + FAT header
├── macho_rewrite.py                 # Single load-path replacement (all slices)
├── set_id_dylib.py                  # Set/append LC_ID_DYLIB
├── tweak_finder.py                  # GitHub Releases scanner for .deb assets
├── config.example.env               # Config template
├── config.env                       # Your config (gitignored)
├── .gitignore                       # Excludes: *.dylib, *.framework/, *.deb, *.ipa, conv_*/, config.env, venv dirs
├── requirements.txt                 # pycryptodome (for fat_strip.py)
├── docs/
│   └── NOTES.md                     # Deep-dive: path mappings, FAT handling, known tweaks, links
└── tweaksOrder/                     # Default output (gitignored)
```

---

## References

- [LiveContainer TweakLoader.m](https://github.com/LiveContainer/LiveContainer/blob/main/LiveContainer/TweakLoader.m) — import logic reference
- [Issue #167](https://github.com/LiveContainer/LiveContainer/issues/167) — `.deb` import not supported
- [Issue #597](https://github.com/LiveContainer/LiveContainer/issues/597) — signature renewed on import, must tap "Sign"

---

## License

MIT License — see [LICENSE](LICENSE) for details.
