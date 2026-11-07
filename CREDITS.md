# Revenant map rendering credits

This atlas builds on the work of the Revenant reverse engineering community.
Pinned repository revisions are in `sources.json`.

- **[Cinematix and Ben Cooley](https://github.com/benjcooley/Revenant)** — the original game engine and its published
  source, especially `object.cpp`, `Sector.cpp`, `imageres.h`, `animimage.cpp`,
  `bitmapdata.h`, `decompdata.h`, and `chunkcache.cpp`. The bounded decompressor
  in `codec.cpp` follows its original assembly operations.
- **[Ben Cooley / RevenantRevisited contributors](https://github.com/benjcooley/RevenantRevisited)** — the modern port, lighting
  research, engine documentation and useful independent reference tooling.
  The native fidelity export runs the original executable.
- **[WinterSnowfall and D7VK contributors](https://github.com/WinterSnowfall/d7vk)** — the DirectDraw/Direct3D bridge used
  to run the original renderer with Wine.
- **[nuxdie / WiegerWolf / kpcg](https://github.com/nuxdie/revenant-map-builder)** — `revenant-map-builder`, the map-sector,
  class-definition and resource parsing work, format investigations, and the
  forum/Discord collaboration that brought these efforts together.
- **[MathJazz / depy](https://github.com/depy/RevenantRE)** — `RevenantRE`, independent graphics and compression
  decoding and the shared working Go implementation.
- **[Slender47 / chrisdev1187](https://github.com/chrisdev1187/Revenant-Asset-Studio)** — `Revenant-Asset-Studio`, subsequent asset
  decoding, format research, tooling, and useful independent comparisons.
- **[pvtjokerr](https://www.accursedfarms.com/index.php?members/pvtjokerr.33944/)** — early Kaitai/Python work, palette observations, reference
  renders, and investigations of fixed-size chunks and partial edges.
- **[Vinylon, Ross Scott, and the Accursed Farms community](https://www.accursedfarms.com/index.php?threads/revenant-maps.3265/)** — the original
  map extraction discussion and the motivation for a complete artwork map.

The renderer uses a local installation's artwork. The source checkout contains neither that installation nor generated maps.
The public atlas hosts rendered images separately; original executables and raw
game resources are not uploaded. Capture and validation run locally before the
explicit publication pipeline.
