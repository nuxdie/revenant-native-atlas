# Revenant native map atlas

Full-resolution artwork maps of **all 33 drawable levels** in Revenant's Ahkuilon base module, captured with the original executable and its level editor.

**[Explore the atlas](https://revenant-native-atlas-2026.lithepond4.chatgpt.site/) · [Download maps and mirror files](https://github.com/nuxdie/revenant-native-atlas/releases/latest) · [Credits](CREDITS.md)**

The outdoor island is **65,024 × 29,952 pixels**. Every level has a PNG and a lossless, tiled BigTIFF download. The viewer pans and zooms native tiles; dimensions and actual file sizes sit beside the downloads. Credits opens within the viewer.

## What this includes

- Original-engine capture and live camera tools, complete camera/frame metadata, and source-pixel ownership audits.
- Native-pixel stitching: output colours are selected from original viewports, without colour blending, resampling, inpainting, or exposure correction. Only overview previews are reduced.
- Streaming PNG and tiled BigTIFF exporters. BigTIFF uses 64-bit offsets, 1024-pixel tiles, and lossless Deflate with horizontal prediction. Every TIFF tile is decoded and compared against the source tiles.
- Corrections for black-shadow pixel-format errors and geyser base blending, with explicit binary/resource guards and regression tests. See [rendering and limitations](docs/rendering.md).
- The complete published viewer and its Worker/R2 hosting source, plus an independent local mirror server.
- A separate static-data renderer used to plan coverage, with the earlier decoder and map-format research preserved.

**These maps are snapshots across successive animation frames.** The original engine renders lighting, 3D props, visible actors/items, shadows, and visual effects. Editor mode pauses gameplay AI. Saved state determines what has spawned or is visible. This is not a synchronized simulation of the entire island, nor a promise of identical pixels on every historical GPU.

## Use the maps

Open the [hosted atlas](https://revenant-native-atlas-2026.lithepond4.chatgpt.site/) or download a level's PNG/TIFF from [Releases](https://github.com/nuxdie/revenant-native-atlas/releases/latest). Maps are individual files, without redundant ZIP wrappers. The island decodes to about 5.84 GB of RGB; its tiled BigTIFF allows readers to process sections without loading the whole image.

For an independent copy of the complete viewer, follow [mirroring and hosting](docs/hosting.md). No ChatGPT account or game installation is needed to view already-rendered maps.

## Run the source

Python 3.10+, NumPy, Pillow, a C++17 compiler, and libtiff are sufficient for the offline tools and regression tests:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

On Debian/Ubuntu, the native library/compiler prerequisites are `g++ libtiff6`. Original-game capture additionally needs Linux/X11, XComposite, Wine with 32-bit support, D7VK, Clang 18, i686 MinGW binutils, xdotool, and xwininfo. [The reproduction guide](docs/reproducing.md) explains setup and the capture → audit → export sequence.

You must supply your own compatible extracted game installation. No executable, DLL, raw game resource, save, account credential, or Wine prefix is included.

## Repository guide

| Path | Purpose |
| --- | --- |
| `atlas.py`, `codec.cpp` | Independent static baseline and bounded resource decoder |
| `native/` | Original executable control, capture, stitching, audit, PNG/TIFF export and publication |
| `public-site/` | Full published web application and Worker/R2 API source |
| `tools/` | Release download and independent mirror helpers |
| `tests/` | Renderer, registration, seam, pixel-format and BigTIFF regressions |
| `evidence/` | Published validation summaries, measurements and provenance |
| `sources.json`, `patches/` | Pinned community references and reference-port patches |

## Community and attribution

This continues my earlier [revenant-map-builder](https://github.com/nuxdie/revenant-map-builder) work and builds on research by the Revenant reverse-engineering community: Cinematix and Ben Cooley, RevenantRevisited, D7VK, MathJazz/depy, Slender47/chrisdev1187, pvtjokerr, Vinylon, Ross Scott, and others. See [CREDITS.md](CREDITS.md) and the pinned revisions in [sources.json](sources.json).

The game artwork retains its existing ownership. Referenced projects and bundled third-party components retain their own licences; a reference link does not relicense their code or game assets. This repository does not claim ownership of the original game or upstream work.
