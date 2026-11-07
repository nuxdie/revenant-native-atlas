# Revenant retail map atlas

Tools for full-resolution artwork maps captured from the **English retail game (GOG 1.22L)** using its original executable and level editor.

**Retail rebuild status:** native capture and review are in progress. The public viewer keeps the preceding July-data catalog until the replacement is complete. In particular, legacy sectors in retail levels 41–43 reference missing object types and crash the original game; that area is held for investigation.

**[Explore and download](https://revenant-native-atlas-2026.lithepond4.chatgpt.site/) · [Credits](CREDITS.md) · [Reproduce the captures](docs/reproducing.md)**

The retail dataset contains **31 drawable campaign levels and six deathmatch levels**. The forest and ruins have separately rendered **day and night** versions: **37 locations, 39 images**. Each image has a PNG and a lossless tiled BigTIFF download. The viewer keeps the same position and zoom when changing time, and shows dimensions and file sizes beside the download links.

## Why the retail data matters

The earlier atlas used a July 1999 installation. That data puts the ruins on level 0 and gives Misthaven daytime ambient intensity 80; the retail module puts the ruins on level 5 and uses intensity 30. Changing brightness or replacing the renderer cannot correct that world-data difference.

The current capture tools pin the retail executable and inventory the installed archives, including the areas that actually have a day/night cycle. Day is captured at **12:00**, night at **01:00**. Fixed-lighting interiors retain their authored lighting.

## Rendering and verification

- The original retail engine renders the terrain, lighting, 3D props, visible actors/items, shadows and visual effects. The capture configuration uses Wine/D7VK, the retail light grid and GammaLevel 3.
- Output pixels come directly from registered original-game viewports. Stitching selects existing source pixels; it does not average colours, recolour a daytime image, inpaint gaps or upscale artwork.
- Camera/scroll registration, frame progress, source hashes, pixel ownership and actual neighbouring pixel pairs at stitching boundaries are checked. Moving regions are measured from native frames, rather than inferred from image disagreements.
- PNGs are streamed. BigTIFF uses 64-bit offsets, 1024-pixel tiles and lossless Deflate; every decoded TIFF tile is compared against its source RGB pixels.
- The publisher uploads immutable revisions and replaces the catalog only when **all 39** images and TIFFs pass. An incomplete rebuild cannot replace the existing viewer with a partial catalog.

RevenantRevisited is included as a comparison backend, with its upstream revision and small capture patches recorded. Both Classic and modern modes were tested against retail views. Its extra features are useful, but it has not been accepted as a pixel-identical substitute for this retail configuration. See [rendering evidence and limits](docs/rendering.md).

These files freeze successive local animation phases. Editor mode pauses gameplay AI; quest state and spawned objects can differ from a played save. The atlas is a reproducible rendering of the base modules, not one synchronized simulation or a guarantee of identical output on every historical GPU.

## Run the source

Python 3.10+, NumPy, Pillow, a C++17 compiler and libtiff run the offline tools and tests:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
node --test public-site/tests/atlas-model.test.mjs
```

On Debian/Ubuntu, install `g++ libtiff6`. Original-game capture additionally needs Linux/X11 and XComposite, Wine with 32-bit support, 32-bit D7VK, Clang 18, i686 MinGW binutils, xdotool and xwininfo. The [reproduction guide](docs/reproducing.md) covers isolated instances, the required binary, capture, review and publication.

Supply your own compatible game installation. The source repository contains no original executable, DLL, resource archive, save, account credential or Wine prefix. Rendered game artwork retains its existing ownership.

## Hosting and releases

The [live atlas](https://revenant-native-atlas-2026.lithepond4.chatgpt.site/) provides direct individual PNG/TIFF downloads, without redundant ZIP wrappers. [Hosting instructions](docs/hosting.md) cover the Sites Worker/R2 source and an independent local mirror.

A GitHub dataset release is prepared as a **draft** while community announcements are on hold. Until it is published, anonymous downloads should use the live atlas; `tools/fetch_release.py` requires a published release. Source code and reproduction instructions are public independently of that release.

## Repository guide

| Path | Purpose |
| --- | --- |
| `native/retail*.py`, `native/retail_control.c` | Retail inventory, isolated capture instances and original-editor control |
| `native/quilt.py`, `native/audit.py`, `native/edges.py` | Source-pixel stitching and ownership/boundary validation |
| `native/bigtiff.py`, `native/publish_retail.py` | Lossless giant-image downloads and complete-catalog publication |
| `public-site/` | Viewer, lighting-state controls and Worker/R2 API |
| `tools/` | Release download and independent mirror helpers |
| `tests/`, `evidence/` | Regression tests, provenance and rendering comparisons |
| `atlas.py`, `codec.cpp`, older `native/` tools | Earlier static renderer and July-installation research, retained separately |
| `sources.json`, `patches/` | Pinned community references and comparison-port patches |

This continues my earlier [revenant-map-builder](https://github.com/nuxdie/revenant-map-builder) work and the community's research. See [CREDITS.md](CREDITS.md), [NOTICE](NOTICE.md) and the pinned upstream sources. Coding assistance was used; the artwork is rendered by the game, not generated.
