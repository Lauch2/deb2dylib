# Projektnotizen — deb2dylib / LiveContainer

Gesammelte Erkenntnisse aus der Arbeit mit iOS-Tweaks für LiveContainer.

## Ausgangslage

- Ziel: iOS-Tweaks (Cydia/Substrate-.deb) auf **iPad** via **LiveContainer** laufen
  lassen (ohne Jailbreak, LiveContainer stellt Substrate/CydiaSubstrate bereit).
- LiveContainer importiert **nur `.dylib` / `.framework`**, keine `.deb`
  (Issue #167). Nach dem Import **muss im Tweaks-Tab auf "Sign" gedrückt
  werden** (Issue #597).
- Ein .deb ist ein ar-Archiv mit `data.tar.*`; darin liegt der Code unter
  `Library/MobileSubstrate/DynamicLibraries/<tweak>.dylib` (+ Filter-`.plist`).

## Was die Rewrites machen (Kernstück)

LiveContainer lädt Substrate **global** (einmal pro Prozess) via
`TweakLoader.m`. Die Tweak-dylibs referenzieren Substrate aber oft über
absolute Pfade, die auf dem Gerät so nicht existieren. Die Lösung: alle
Substrate/Hook-bezogenen `LC_LOAD_DYLIB`-Einträge auf `@rpath/...` umbiegen.

| Original-Pfad (in der dylib) | → LiveContainer-Pfad (`@rpath/...`) |
|---|---|
| `/Library/MobileSubstrate/DynamicLibraries/<name>.dylib` | `@rpath/<name>.dylib` |
| `/Library/Frameworks/<Name>.framework/<Name>` | `@rpath/<Name>.framework/<Name>` |
| `/usr/lib/libsubstrate*.dylib` | `@rpath/usr/lib/libsubstrate*.dylib` |
| `/var/jb/...` | `@rpath/...` (Substrate-Pfad) |

System-Frameworks (`/System/Library/Frameworks/...`,
`/usr/lib/libc++.dylib` etc.) werden **nicht** angefasst — die liegen
absolut auf jedem iOS-Gerät.

## FAT-Binary-Handling

Viele Tweak-dylibs sind FAT (arm64 + arm64e, manchmal armv7). Die Rewrites
müssen **pro Slice** laufen, weil jeder Slice eigene Load-Commands hat.
`deb2dylib-livecontainer.py` und `macho_rewrite.py` parsen den FAT-Header
(`0xcafebabe`), iterieren über alle Slices und patchen jeden einzeln
(Pure-Python, kein `lipo`/`install_name_tool` nötig).

## Bekannte Tweaks, die so konvertiert wurden

| Tweak | Bundle-ID / Repo | .deb-Datei | Status |
|---|---|---|---|
| YTLite (YouTube) | com.dvntm.ytlite | 7.3 MB | ✅ läuft |
| H5GG (Mod-Engine) | com.test.h5gg | 468 KB | ✅ läuft |
| BHInstagram | com.bandarhl.bhinsta | 70 KB | ✅ läuft |
| Cephei (Framework) | — | 199 KB | Framework → eigener Ordner |
| Rocket (Instagram) | annulya/rocket | 1.4 MB | .deb vorhanden |

## Praktische Kommandos

```bash
# Alle Load-Pfade einer dylib anzeigen (inkl. FAT-Slices)
python3 inspect_macho.py tweaksOrder/Tweak.dylib

# FAT -> thin arm64 (falls ein Tool nur thin mag)
python3 fat_strip.py tweaksOrder/Tweak.dylib

# Install-Name (LC_ID_DYLIB) setzen, damit dyld sie unter @rpath findet
python3 set_id_dylib.py tweaksOrder/Tweak.dylib "@rpath/Tweak.dylib"

# Aktuelle Tweak-Releases scannen (GitHub API, 60/h ohne Token)
python3 tweak_finder.py
# Mit Token (config.env): 5000/h
# GITHUB_TOKEN=ghp_xxx python3 tweak_finder.py
```

## Häufige Fallen

| Symptom | Ursache / Fix |
|---|---|
| Tweak wird in LiveContainer geladen, aber Hook greift nicht | `Sign`-Button im Tweaks-Tab **nicht** gedrückt (Signatur wird beim Import erneuert, Issue #597). |
| `dyld: Library not loaded: /Library/MobileSubstrate/...` | Pfade nicht auf `@rpath` umge rewritten — `deb2dylib-livecontainer.py` laufen lassen. |
| `LC_LOAD_DYLIB` Pfad länger als Original | `macho_rewrite.py` prüft Länge; Ziel muss ≤ Original sein (Slot im Header ist fix). |
| FAT-Binary, aber nur ein Slice gepatcht | `inspect_macho.py` zeigt alle Slices; Rewrites laufen pro Slice (Skripte machen das). |
| `tweak_finder.py` zeigt keine Assets | Rate-Limit (60/h ohne Token) — `GITHUB_TOKEN` in `config.env` setzen. |

## Framework-Handling (Cephei etc.)

Einige Tweaks ziehen Frameworks mit (z. B. `Cephei.framework`). Die liegen im
.deb unter `Library/Frameworks/Cephei.framework/`. `deb2dylib-livecontainer.py`
extrahiert den Framework-Ordner samt Binary und `Info.plist` nach
`tweaksOrder/Cephei.framework/`. In LiveContainer muss das Framework **neben**
der Tweak-dylib liegen (gleicher Import-Ordner), dann findet dyld es über
`@rpath/Cephei.framework/Cephei`.

## Nützliche Links

- LiveContainer TweakLoader.m (Referenz für Import-Logik):
  https://github.com/LiveContainer/LiveContainer/blob/main/LiveContainer/TweakLoader.m
- Issue #167 (`.deb` Import nicht unterstützt):
  https://github.com/LiveContainer/LiveContainer/issues/167
- Issue #597 (Signatur beim Import):
  https://github.com/LiveContainer/LiveContainer/issues/597