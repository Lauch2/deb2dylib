# deb2dylib — iOS-Tweak-.deb für LiveContainer nutzbar machen

Werkzeuge zum Extrahieren und Anpassen von iOS-Tweak-.deb-Paketen, damit sie in
**LiveContainer** (Tweaks-Tab → Import dylib → Sign) laufen.

Läuft komplett lokal auf Linux/macOS. Keine Apple-ID, keine Signierung nötig.

## Das Problem

LiveContainer kann **keine .deb direkt laden** (nur `.dylib` / `.framework`,
siehe Issue #167 / TweakLoader.m). Ein .deb ist nur ein Container (ar + tar);
der eigentliche Code liegt als `.dylib` in
`Library/MobileSubstrate/DynamicLibraries/`. Zudem enthalten Tweak-dylibs oft
absolute Load-Pfade (`/Library/MobileSubstrate/...`, `/usr/lib/libsubstrate...`),
die auf dem Gerät so nicht existieren — LiveContainer lädt Substrate global
über `TweakLoader`, daher müssen absolute Substrate-Pfade auf `@rpath/...`
umgebogen werden.

## Was die Skripte machen

| Skript | Zweck |
|---|---|
| `deb2dylib-livecontainer.py` | **Haupt-Skript**: extrahiert `.dylib` + Filter-`.plist` aus dem .deb, schreibt **alle Substrate/Hook-Pfade** auf `@rpath/...` um (FAT-Binary-fähig, arm64/arm64e), schreibt Ergebnis nach `tweaksOrder/`. |
| `deb2dylib.py` | Einfache Variante: nur extrahieren, **keine** Pfad-Umschreibung. |
| `fat_strip.py` | Zieht einen arm64-Slice aus einem FAT-Binary (in-place). |
| `inspect_macho.py` | Listet alle Load-Commands (`LC_LOAD_DYLIB`, `LC_RPATH`, …) inkl. FAT-Header. |
| `macho_rewrite.py` | Ersetzt **einzelnen** Load-Pfad in einer dylib (alle Arch-Slices, gleich lang/kürzer). |
| `set_id_dylib.py` | Setzt/ergänzt `LC_ID_DYLIB` (Install-Name) einer thin arm64 dylib. |
| `tweak_finder.py` | Scannt bekannte Tweak-Repos (GitHub Releases) nach aktuellen `.deb`-Assets. |

## Voraussetzungen

| Tool | Zweck |
|---|---|
| `ar` (binutils) | .deb entpacken (ar-Archiv) |
| Python 3.11+ | alle Skripte |
| `pycryptodome` | nur für `fat_strip.py` (optional) |

```bash
# Debian/Ubuntu/Fedora
sudo apt install binutils python3         # oder: sudo dnf install binutils python3

# Python-Deps (nur falls fat_strip genutzt wird)
pip install pycryptodome
```

## Benutzung

```bash
# 1) Config anpassen (einmalig)
cp config.example.env config.env
$EDITOR config.env        # OUT_DIR=./tweaksOrder  (oder anderer Ordner)

# 2) Tweak-.deb -> LiveContainer-fertig
python3 deb2dylib-livecontainer.py /pfad/tweak.deb -o tweaksOrder/

# 3) In LiveContainer importieren:
#    Tweaks-Tab -> + -> Import (dylib) -> tweaksOrder/<tweak>.dylib auswählen
#    **WICHTIG**: danach im Tweaks-Tab auf "Sign" drücken (Issue #597)
```

### Beispiel-Workflow für YTLite / H5GG / Instagram-Tweaks

```bash
# Aktuelle Assets finden
python3 tweak_finder.py

# .deb runterladen, dann:
python3 deb2dylib-livecontainer.py com.dvntm.ytlite_5.2.2_iphoneos-arm64.deb
python3 deb2dylib-livecontainer.py com.test.h5gg_8.0.0_iphoneos-arm.deb
# → erzeugt tweaksOrder/*.dylib (+ *.plist)
```

### Einzelne Pfade manuell anpassen

```bash
# Alle Load-Pfade anzeigen
python3 inspect_macho.py tweaksOrder/Tweak.dylib

# Einen Pfad global ersetzen (alle Arch-Slices)
python3 macho_rewrite.py tweaksOrder/Tweak.dylib \
  "/Library/MobileSubstrate/DynamicLibraries/substrate.dylib" \
  "@rpath/substrate.dylib"

# Install-Name (LC_ID_DYLIB) setzen
python3 set_id_dylib.py tweaksOrder/Tweak.dylib "@rpath/Tweak.dylib"
```

## Dateien

| Datei | Zweck |
|---|---|
| `deb2config.py` | zentrale Config; liest `config.env` (gitignored) |
| `deb2dylib-livecontainer.py` | Haupt-Skript: .deb → dylib + plist + @rpath-Rewrites |
| `deb2dylib.py` | nur extrahieren, ohne Rewrites |
| `fat_strip.py` | FAT → thin arm64 slice |
| `inspect_macho.py` | Load-Commands auflisten |
| `macho_rewrite.py` | einzelnen Load-Pfad ersetzen |
| `set_id_dylib.py` | LC_ID_DYLIB setzen/anhängen |
| `tweak_finder.py` | GitHub Releases nach .deb scannen |
| `config.example.env` | Vorlage für `config.env` |
| `docs/NOTES.md` | technische Details, bekannte Repos, Pfad-Mapping-Tabelle |

## Bekannte Tweak-Repos (für `tweak_finder.py`)

| Name | Repo | Typische Arch |
|---|---|---|
| YTLite | dayanch96/YTLite | arm64 |
| H5GG-Revamped | Mods-Center-iOS/H5GG-Revamped | arm64 |
| BHInstagram | BandarHL/BHInstagram | arm64 |
| Rocket | annulya/rocket | arm64 |
| SafariPlus | opa334/SafariPlus | arm64 |

## Lizenz

Privates Projekt, keine Lizenz vergeben.