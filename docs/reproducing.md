# Reproduce the native maps

## Choose a compatible source installation

Work on a separate extracted installation under `runtime/game/`, not your only copy. You should have `Revenant.exe`, `Resources/class.def`, `Resources/Imagery/`, and `Modules/Ahkuilon/Map/` containing loose resources. Some releases package resources in archives that must first be extracted.

The original executable's accepted SHA-256 is pinned in `native/provider.json`. This release uses the July 7, 1999 version 0.30 executable. Runtime addresses and resource guards deliberately reject other binaries/assets; do not disable them to make an unrelated release run. No game executable, raw resource archive or proprietary DLL is supplied in GitHub releases.

## Linux prerequisites

Use an X11 session with XComposite and a Vulkan driver that supports D7VK. Python 3.10+, Pillow, NumPy, g++, libtiff, Clang 18, i686 MinGW binutils, xdotool and xwininfo are required. Install a Wine runner with 32-bit support. The published maps used GE-Proton 11-7 and D7VK commit `d6faa06439eb097783dee27fb2b5d1cf3bb1b335`; other versions need their own visual validation.

On Debian/Ubuntu the tool packages include:

```sh
sudo apt-get install g++ libtiff6 libx11-6 libxcomposite1 xdotool x11-utils clang-18 binutils-mingw-w64-i686
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Configure `REVENANT_WINE` to your runner's `wine` executable. Set `DISPLAY` to the X11 display used for game capture. Run commands from this repository's root.

```sh
export REVENANT_WINE=/absolute/path/to/runner/files/bin/wine
export WINEPREFIX="$PWD/runtime/prefix"
mkdir -p runtime
"$REVENANT_WINE" wineboot -u
"$REVENANT_WINE" reg add 'HKCU\Software\Wine\Explorer' /v Desktop /t REG_SZ /d RevenantAtlas /f
"$REVENANT_WINE" reg add 'HKCU\Software\Wine\Explorer\Desktops' /v RevenantAtlas /t REG_SZ /d 640x480 /f
```

Place the matching 32-bit D7VK `ddraw.dll` beside the copied executable. Configure the copied game's `revenant.ini` for hardware 3D (`Software3D=No`), real-time lighting and GammaLevel 3. The controller selects the original real-time grid in memory. Do not confuse the alternative software DLS path with the tested configuration.

The original game has legacy path-length problems. For deeply nested installs, map the private game directory to a short drive in this private Wine prefix:

```sh
ln -s "$PWD/runtime/game" "$WINEPREFIX/dosdevices/g:"
export REVENANT_EXE='G:\Revenant.exe'
```

Do not replace an existing drive mapping without inspecting it.

## Build the static coverage baseline

```sh
python3 atlas.py --game runtime/game --levels all --no-full-png
```

This is the independent static decoder. It determines coverage and provides plans; its unlit images are not the final native fidelity exports.

## Launch and capture

```sh
python3 -m native.launch
python3 -m native.build_all
```

The launcher builds the guarded helper, starts the isolated original editor, and initializes a new game. Initial menu automation assumes the tested 640 × 480 presentation. Capture viewports are 640 × 340. A dedicated Wine prefix/desktop is essential because the controller locates the original game window by title. The controller's input/presentation configuration prevents mouse-edge panning from stealing a scripted camera.

For a single level or resumable limited investigation:

```sh
python3 -m native.export --level 30 --out native-output
python3 -m native.quilt native-output/level-30 --no-full
python3 -m native.audit native-output/level-30 --no-full
python3 -m native.finalize native-output/level-30
python3 -m native.bigtiff --levels 30
```

Consult each command's `--help` for supported flags. Native exports retain source frames, ownership indexes and measured motion, and can be resumed. Never publish a partial or `review_required` map.

## Investigate joins and effect issues

Use `native.repair_reviews --levels 30,31` to recapture held joins with longer observation; `native.recut` tries alternate source ownership while retaining original colours. A source defect requires correcting and freshly capturing the original renderer; stitching alone does not fix black-backed effect surfaces.

`native.repair_effects` can recapture an entire level with the guarded current effect profile:

```sh
python3 -m native.repair_effects --levels 30,31 --all-captures
```

Its scoped mode uses a runtime JSON list of capture names. Level 39 has an additional registered Z=192 viewport; preserve that source and ownership when repairing it. See `native.bridge`, the saved metadata and the release's rendering evidence.

## Preview and compare

```sh
python3 viewer.py native-output
python3 -m native.live --port 8766
python3 -m native.check_scene --camera 30 10536 10736 0 --out comparisons/cavern
python3 -m native.clip --camera 30 10536 10736 0 --seconds 10 --out comparisons/cavern-cycle
```

`native.live` is loopback-only and suspends camera requests while capture/comparison tools own the camera. A moving effect needs a full-cycle observation; a few quiet frames cannot establish its blend behaviour throughout controller initialization, emission and cleanup.

Use [rendering.md](rendering.md) for acceptance criteria and limitations. For reference-port experiments, `sources.json` pins the community repositories and `patches/` keeps the local Revisited patches; those experiments do not establish original-executable fidelity.
