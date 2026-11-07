> Historical development notes. Some sections describe intermediate exports and retired URLs. Use the root README and current guides for reproduction and hosting.

# Revenant full resolution map atlas

The fidelity path uses the **original game executable** as its renderer.
`native/` drives the built-in editor, reads the actual camera scroll, waits
for a full editor redraw and the background queue to finish, and captures overlapping 640 × 340 viewports. It retains
native lighting, 3D props, visible items, NPCs, creatures, shadows and animation
frames. `native-output/` contains these captures and their stitched exports.
The independent static reconstruction in `output/` remains a coverage baseline;
it is not the fidelity deliverable.

A PNG is a snapshot. Its separate captures are timestamped and do not share one
animation phase. The live viewer displays the original renderer's moving
visuals at the current camera, with controls for every drawable map level.
Editor mode stops gameplay AI; it does not reproduce a whole island simulation
in a browser. Spawned/hidden items and NPCs depend on the loaded game state.

## Original game workflow

This workspace has an isolated installation at `runtime/game`, an isolated Wine
prefix at `runtime/prefix`, and the original executable identified in
`native/provider.json`. The original archived installation is unchanged.
The helper's addresses are specific to this executable; another release must
be reverse engineered before control is enabled.

Requirements in this environment: Python/Pillow/NumPy, X11 and XComposite,
`xdotool`, Clang 18, i686 MinGW binutils, and the installed GE-Proton 11-7 Wine
runner. `native.game.build_control()` builds the small Windows helper. D7VK's
32-bit `ddraw.dll` bridges the original DirectX renderer. Launch the isolated
original game with its normal resources, `EDITOR FASTLOCK=OFF
NOPRELOADSECTORS CHUNKCACHESIZE=24`, and `WINEDLLOVERRIDES=ddraw=n,b;d3dimm=b`.
Enter a new game once so the world is initialized.

```sh
python3 -m native.launch
python3 -m native.export --level 0 --out native-output
python3 -m native.quilt native-output/level-0
python3 -m native.audit native-output/level-0
python3 viewer.py native-output
python3 -m native.live --port 8766
python3 -m native.clip --camera 2 1212 545 0 --out native-output/clips/keep
python3 -m native.check_scene --camera 0 2377 26883 0 --out comparisons/town-check
```

The native outdoor island is 65,024 × 29,952 pixels. The export pipeline covers
all 33 drawable base-module levels; the extra level-90 sector file is empty.
Open <http://127.0.0.1:8766/fidelity.html> for local validation tables, fresh
game/export comparisons and lossless animation clips. The report distinguishes
native exports from the independent static baseline. `python3 -m native.report`
rebuilds it from the recorded final comparisons and per-level audits.

The barrel/crate rainbow band at level 0, camera 2012, 27407, 0 was traced to
the original dispatcher's RGB565 alpha routine receiving an ARGB1555 background
texture. It interpreted the texture's coverage bit as colour. A narrow in-memory
format correction now preserves that bit and applies the native 15-bit channel
rounding to black alpha-shadow bitmaps. Other draw formats use the original
dispatcher. The A/B check changed 586 pixels, all inside the two shadows, with
every pixel outside identical. `native.check_shadow` repeats the check; the
fidelity report retains before/after images and measurements. Captures near
possible shadow instances were replaced; retained captures have explicit
source-bound validation. Source-pixel identity alone does not establish that
the source renderer is artifact-free.

The black shoreline bands at camera 0 / 3196, 28775, 0 were present in older
raw captures reused by the PNG. Fresh native views at the same cameras were
clean. A source-refresh pass replaced 391 candidate frames and refreshed their
owned pixels from those complete native frames. The reported 640 × 340 view
then matched fresh game output exactly. The older session's low-level fault
is not established. Retired source digests are rejected by export/audit, and
captures, comparison clips and the live status now check native frame progress.
See `source-refresh.json` and the shoreline evidence in the fidelity report.

Open <http://127.0.0.1:8766> for the live camera, or
`native-output/index.html` for the stitched maps. The live service binds only
to loopback and suspends camera requests while an export owns the game.
`--plan runtime/native-plan-0.json` reuses a saved capture plan; `--limit N`
creates a resumable partial capture. `--probe X0 Y0 X1 Y1` captures a small
rectangle in units of 512 × 256 pixels for seam investigations.

Each capture has a lossless source PNG, camera/scroll/frame/time/ambient metadata and a
SHA-256 digest. `temporal/` records measured changes across three frames with
an explicit eight-pixel motion margin. `seams.json` retains overlap errors,
including animation differences. `validation.json` checks source digests,
camera registration, nonblack edges bordering uncaptured coverage, exact
per-pixel identity to the source viewports, PNG CRCs, and
sampled full-image pixels. Raw overlap differences above 0.1% are retained for
inspection. After quilting, the acceptance check examines the actual adjacent
output pixels at ownership boundaries, checks whether either native source
reproduces both neighbours, and separates measured animation differences from
unexplained differences. Publication requires zero unexplained static boundary differences and zero
nonblack boundaries into unplanned coverage for each native map. This does not claim that all animations are synchronized or that every
gameplay state is represented. Current fresh-view measurements, masks and remaining differences are available
in the fidelity report. The shoreline correction is verified against every
pixel of its fresh 640 × 340 viewport; this is a local result, not a claim
that the entire stitched island is one synchronized, pixel-identical frame.

Capture configuration is the original real-time light grid (`RealTimeLight=Yes`)
and GammaLevel 3. The installation's alternative software DLS path clips much
of the bright outdoor terrain; comparison captures are retained separately.
Stitching chooses cuts through matching overlap pixels. It preserves complete
source pixels and saves a 16-bit ownership index for every output tile, linking
each pixel to its original viewport. The auditor verifies every owned pixel,
not just a sample. Raw overlap differences and nonmatching cuts remain in the
reports. No post-capture exposure, color normalization, blending, AI inpainting
or pixel resampling is used in the export. Only overview previews are downscaled.
D7VK ignores application gamma ramps, so this is a specific reproducible
Wine/D7VK configuration, not a promise of identity to every historical GPU.

The helper changes a few presentation settings **in memory**:
it disables background pausing and frame skipping and suppresses the mouse
cursor/shadow and editor-only markers. Three 2D visibility branches and a
small 3D visibility guard apply the gameplay filters while retaining editor
camera control and paused AI. The guard handles helper imagery too; its
visibility checks preserve the original loop and registers. The separate
`shadow_blend.c` / `shadow_bridge.s` correction fixes black-shadow blending into
ARGB1555 background textures; this is a rendering correction, not an unmodified
retail-rasterization claim. It preserves coverage, dimming, source clipping and
horizontal/vertical mirrors. The executable on disk is unchanged. Other lighting
and rasterization still run in the original engine. The source records every
address and checks the executable hash and console-thread signature. Capture can temporarily bypass the frame timer while the editor simulation is
paused; normal timing is restored before the live view or an animation clip.
Ending the game discards these changes. Area transitions, light-grid rendering,
actor rendering and all imagery decoding still execute in the original game.

## Public atlas and downloads

The public tiled viewer is at
<https://revenant-native-atlas-2026.lithepond4.chatgpt.site>.
`/downloads.html` lists every published PNG, its ZIP, dimensions and checksums.
The viewer requests native PNG tiles at 1:1; only the fit overview resamples.
The ZIP contains the identical full resolution PNG. No original executable or
raw game resource is published.

`public-site/` contains the Sites/Vinext viewer and R2 streaming endpoints.
`native.publish_pack` prepares immutable per-level revisions from accepted
native audits, including a pack of unchanged PNG tiles and their byte offsets.
`native.publish_upload URL --watch` accepts its upload secret through hidden
stdin, uploads files in resumable parts and reads them back to check SHA-256.
It publishes the catalog after all referenced files pass. The production
secret stays in native Sites environment variables; it is absent from source,
client assets and deployment archives.

`python3 -m native.verify_public URL` independently downloads every published
PNG and ZIP anonymously, verifies their complete hashes, checks byte ranges
and PNG dimensions, and compares a public tile with its native tile digest.
Reports remain in `runtime/publication/`.

`python3 -m native.build_all` captures and audits all levels. Independent camera
instances can use `REVENANT_RUNTIME`, `REVENANT_DESKTOP`, and disjoint `--levels`
sets. Their isolated Wine prefixes and game directories must be initialized
first. The legacy executable needs a short Windows drive path for deeply
nested installations; `REVENANT_EXE` supplies that launch path. The all-level
capture uses normal game timing. Held joins can be rechecked with
`native.repair_reviews --levels ...`: it waits for the instance's camera lock,
recaptures the relevant viewports, and measures 32 or 64 native frames over a
longer interval. It never infers motion masks from overlap disagreements.
`native.recut` can select a different ownership cut through existing sources;
it retains a patch only when its measured static disagreement count falls.
Every owned colour is rechecked against its original source before finalizing.
A camera-dependent sector boundary on level 39 required a native viewport at
Z=192. `native.bridge` retains this entire source frame and its measured scroll,
verifies exact registration against the overlapping coarse-grid capture, and
uses only unchanged source pixels inside a matching boundary. The audit checks
this extra source, frame advancement, registration and pixel ownership too.

## Independent static artwork baseline

Render Revenant's static world artwork directly from the extracted map objects,
I2D resources, sprite registration points and per-pixel depth buffers. Output
keeps one source pixel per map pixel. A local tiled viewer makes the large
images practical to explore.

Requires Python 3, Pillow, NumPy and a C++17 compiler (`g++`).

```
python3 -m pip install -r requirements.txt
python3 atlas.py --game /path/to/Revenant --levels all
python3 viewer.py
python3 -m unittest discover -s tests -v
```

Open `output/index.html` in a browser. It works directly from disk. Drag to pan,
scroll to zoom, press `1` for actual pixels or `F` to fit the map. The dropdown
selects the outdoor island or another world level. Each level also has a
`full-resolution.png`, a small `overview.jpg`, lossless native tiles, its
placement records and a manifest with bounds and coverage statistics.

`--levels 0` renders the outdoor world. `--levels 0,2,4` chooses specific levels;
`--levels all` includes every level with drawable scenery, including unused and
demo layouts present in the installation. `--inventory` inspects and decodes
assets without rendering tiles. `--no-full-png` exports tiles and previews only.
The game files are read without changes. Save-game variations in `Save/` and
`Curmap/` are not used as replacements for the base module.

## Rendering

`class.def` maps an object's unique ID to its imagery file. Sector records give
its position, flags and state. The original engine's projection is
`screen_x = world_x - world_y` and
`screen_y = (world_x + world_y)/2 - world_z*867/1000`, with C++ integer rounding.
State registration points anchor the original sprites. Per-pixel z buffers
resolve overlapping walls, roofs, paths and vegetation, including horizontal
flips. Color palettes use the source RGB555 representation.

The decoder follows the original assembly's LZ operation: it copies bytes from
the encoded source stream using ESI, rather than copying the decompressed
output. Chunk offsets are self-relative, including single-chunk bitmaps. It
also decodes the separate depth streams and their high-byte changes. The
focused tests cover source back-references, depth skips, malformed
streams, legacy map records, duplicate IDs, world coordinates, clipping,
projection, occlusion, tile seams and streamed PNG export.

Tile rendering bounds memory use. Full PNGs are written in strips with a
streaming PNG encoder, so the complete billion-pixel canvas is never allocated.
Manifests, `assets.json`, `decode-failures.json` and `empty-assets.json` expose
coverage and decoding outcomes. `sources.json` records the reference revisions;
`CREDITS.md` names the contributors.

## Scope and remaining differences from the running game

- Static 2D scenery is rendered in its original map coordinates. Characters,
  editor helpers, 3D effects and 3D-only props are omitted and counted.
- Illumination sprites and runtime lighting are omitted. The map shows the
  unlit source artwork consistently, rather than a particular time of day.
- Separate world levels retain their own coordinate systems. Interiors and
  dungeons are separate images; their positions are not invented to form a
  single physical island.
- A few shipped depth chunks overrun a 64-by-64 buffer in the original decoder.
  Writes are bounded to that buffer and affected assets are recorded in the
  metadata. Their source color pixels remain intact.
- The running executable moves out-of-sector coordinates into their owning
  sectors in steps of 1024, retaining the inclusive upper boundary. The parser
  reproduces this behavior and counts corrected positions. This was checked
  against thousands of tile coordinates saved by the original game. The atlas
  retains shipped duplicate/test layouts and does not invent missing land.

Use the PNGs to inspect and export original artwork; use manifests to assess
coverage. This is a reconstruction of static scenery, with the differences
above, rather than a claim of a pixel-identical live-game screenshot.


The atlas serves direct PNG and lossless tiled BigTIFF downloads. ZIP archives and the separate
About, Checks and Downloads pages have been retired. Credits opens as a styled,
keyboard-accessible dialog within the map viewer.

The June 1999 loose `CavFGeyser.i3d` has no blend controller for its black-backed
`#glow` quad, unlike the later retail asset documented by RevenantRevisited.
Particles already use native litadd, while the base previously drew opaque.
The pinned compatibility profile in `native/provider.json` applies native
litadd16 to that base and the equivalent steam `#blast` only. It leaves authored
meshes, keyframes, particle controllers, textures, placements and lights intact.
The original executable and resource files on disk are unchanged. This is an
explicit correction to defective source rendering, not a claim of equality to
the uncorrected frame. Scope and explicit-blend preservation are regression
tested in `tests/test_effect_blend.py`; native cycle recordings are retained in
`comparisons/geyser-blend-fixed-*`.


`python3 -m native.bigtiff` streams 1024-pixel tiles through libtiff in BigTIFF
(`w8`) format, with lossless Deflate and horizontal prediction. It reopens and
decodes every tile, checks every RGB pixel against the native source tiles,
and records a hash in each private `tiff-validation.json`. It never allocates
the full map. The island is 65,024 by 29,952 pixels (5.84 GB of decoded RGB),
so the TIFF uses 64-bit directory offsets even when compressed below 4 GB.
The public viewer places dimensions and actual byte sizes beside both file
links; it uses the full viewport with controls overlaid on the map.
