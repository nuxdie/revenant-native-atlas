# Reproduce the retail maps

## Source data and tools

Use the English GOG 1.22L installation. The controller accepts only this SHA-256 for `Revenant.exe`:

```text
28bec27387bf53a553da320dd4883d00ff5bcc5a5f3d2658cca8e8ed586372b5
```

It reports version 1.22, built May 8, 2000. Supply your own game files. For an offline GOG installer, `innoextract` can extract them without running setup. Keep the extracted installation separate from each capture instance. The inventory reads `imagery.rvi`, `resources.rvr` and the `Modules/*.rvm` ZIP archives directly.

Use Linux/X11, XComposite, a Vulkan driver, Python 3.10+, Pillow, NumPy, g++, libtiff, Clang 18, i686 MinGW binutils, xdotool and xwininfo. Capture was tested with GE-Proton 11-7 and 32-bit D7VK at commit `d6faa06439eb097783dee27fb2b5d1cf3bb1b335`.

```sh
sudo apt-get install g++ libtiff6 libx11-6 libxcomposite1 xdotool x11-utils clang-18 binutils-mingw-w64-i686
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
export DISPLAY=:0
export REVENANT_WINE=/absolute/path/to/runner/files/bin/wine
```

An X11 desktop must remain available throughout capture. The original renderer and its hardware support affect the result; another Wine/D7VK/GPU configuration needs its own visual checks.

## Inventory and prepare an isolated copy

From the repository root:

```sh
python3 -m native.retail_dataset --help
python3 -m native.retail_dataset --data /absolute/path/to/extracted-game --out runtime/retail-index
python3 -m native.retail_instance \
  --data /absolute/path/to/extracted-game \
  --runtime runtime/retail \
  --desktop RevenantRetail \
  --wine "$REVENANT_WINE" \
  --ddraw /absolute/path/to/32-bit/DDraw.dll \
  --launch
```

The inventory records pack hashes, module/area names, geometry and the areas with authored night lighting. It plans 31 drawable campaign levels and six deathmatch levels, with two states each for levels 0 and 5: 39 images in total. Invalid off-world object placements are reported rather than allowed to enlarge the map by billions of pixels.

The instance helper gives the capture copy its own INI, Curmap, Save, Wine prefix and desktop. It links read-only stock assets to the source directory. It chooses hardware rendering, GammaLevel 3, the original real-time light grid and silent audio through a dedicated muted PulseAudio sink when available. `--ini` selects an INI explicitly; `--prefix-template` can clone an existing compatible prefix. Wait for the helper to finish before opening the controller. Do not run two games against one writable capture directory or Wine prefix.

The Wine runner must support 32-bit Windows applications. The private `G:` drive mapping avoids the original engine's path-length problems. Existing unexpected mappings cause an error rather than being overwritten.

## Capture and resume

The controller defaults to the instance above. For another instance, set all three variables before invoking any capture or controller command:

```sh
export REVENANT_RETAIL_RUNTIME="$PWD/runtime/retail"
export REVENANT_RETAIL_DATA="$PWD/runtime/retail/game"
export REVENANT_RETAIL_DESKTOP=RevenantRetail
export REVENANT_AUDIO_SINK=revenant_atlas_silent
python3 -m native.retail @info
python3 -m native.retail_batch --levels 0,1,2,3,4,5,6,30,31,32,36,37,39,41,42,43,44,45,46,47,48,49,51,52,53,54,55,56,57,58,66,73,83,100,101,102,205
```

The resumable batch wrapper restarts only its own Wine prefix after a capture failure and retains good sources. It holds levels whose unbounded legacy records reference absent object IDs (currently 41–43), instead of retrying an unrecoverable native loader error indefinitely. Those holds prevent a complete catalog from publishing.

The exporter mounts each module in the original editor, hides editor helpers while retaining gameplay visibility, fixes the scene clock, registers each camera, requests the engine's own redraw and waits for native frames and background update queues. Viewports are 640 × 340 pixels, with overlapping 512 × 256 cores. It records the frame, executable identity, clock, camera, source hash and measured temporal changes beside each capture.

For a limited investigation:

```sh
python3 -m native.retail_export --levels 30,31
python3 -m native.retail_export --levels 0 --variant night
```

Re-running resumes recorded captures after validating their identity and hashes. Keep `retail-output/` and its source frames; final PNGs alone cannot reproduce the ownership audit. A process reports `REVIEW` and continues to another map when unexplained joins remain. That map is held, not accepted.

The outdoor plans record the authored light intensity and colour. After each camera change, the original ambient setters ensure that nearby-area fading has not lost the GammaLevel 3 offset. Resume rejects earlier outdoor captures whose recorded ambient differs from that target and recaptures their pixels.

Day is 12:00 and night is 01:00. Interiors without a day/night area definition have one `fixed` state. These are original-engine renders at the selected clock, not colour transforms of one image.

## Review and export

Use an idle isolated renderer for review; its `export.lock` serializes camera use. Retail review must use the retail controller, matching module and matching clock:

```sh
python3 -m native.retail_review retail-output/fixed/level-30 retail-output/fixed/level-31
```

To supervise review, native edge-camera recovery and final PNG/BigTIFF generation for a completed selection:

```sh
python3 -m native.retail_finish --levels 0,5,30,31
```

Use `--wait-for-batch` only when the same isolated instance's batch is still running. Assign disjoint output levels to separate workers. The finisher reports each accepted, held or missing state in its runtime's `finish-status.json`; completion of the process does not imply every assigned map passed. Retain `registration-references/` and the source metadata with the output, since recovered cameras are audited against those immutable native anchors.

This recaptures the affected registered sources with longer native animation observation and tries alternate source ownership. It never manufactures a motion mask from overlap differences or changes RGB values. A persistent problem stays `review_required` and needs investigation; do not relax acceptance to publish it.

Individual offline checks and output generation are also available:

```sh
python3 -m native.quilt retail-output/fixed/level-30 --no-full
python3 -m native.audit retail-output/fixed/level-30 --no-full
python3 -m native.finalize retail-output/fixed/level-30
python3 - <<'PY'
from pathlib import Path
from native.bigtiff import build
build(Path("retail-output/fixed/level-30"))
PY
```

The exporter and review command build the tiled BigTIFF after an accepted PNG. TIFF uses 64-bit offsets, Deflate compression and decoded-tile equality checks. Both formats retain native resolution. Overview previews alone are resized.

Review known shoreline, shadow, light and geyser scenes against fresh original-game viewports, using an idle retail instance:

```sh
python3 -m native.check_scene --atlas retail-output/fixed --camera 30 10536 10736 0 --out comparisons/retail-geyser
python3 -m native.clip --atlas retail-output/fixed --camera 30 10536 10736 0 --seconds 20 --out comparisons/retail-geyser-cycle
```

The comparison retains a measured static-foreground mask. The clip is lossless APNG and verifies every stored RGB frame against a recorded source frame. A stitch can preserve a rendering defect perfectly: source-pixel identity does not by itself establish visual fidelity. See [rendering.md](rendering.md) for configuration, comparison evidence and limits.

## Parallel instances and older research

Parallel work requires a different runtime, desktop, private game directory and Wine prefix per instance. Assign disjoint level lists. Never change the camera of an instance whose export lock is held. If the original game stalls, restart only that instance and resume its registered captures; never fill missing frames with another renderer.

The older `native.launch`, `native.export`, `native.repair_effects`, `native.live` and `native/provider.json` belong to the July 1999 installation. Their runtime addresses, lighting clock and effect patches are deliberately separate. Do not apply them to retail. `atlas.py` remains an independent static decoder; its output is not the production native render.

Revisited comparison patches and upstream revisions are in `patches/` and `sources.json`. The scene comparison harness accepts an explicit scene clock, but its extra rendering features do not establish parity with the original retail executable.
