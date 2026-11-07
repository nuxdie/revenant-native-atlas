# Attribution and third-party material

The original Revenant engine, artwork, maps and resources are the work of Cinematix and their respective rights holders. No blanket licence to that game material is asserted by this repository.

`codec.cpp` is a bounded translation of the original ChunkDecompress / ChunkDecompressZ operations in Ben Cooley's published `chunkcache.cpp`; see CREDITS.md and sources.json. Reference repositories are linked and pinned, rather than republished wholesale. The patches under `patches/` are intended for the pinned reference sources and do not replace their licence terms.

The web application's bundled font files carry their original SIL Open Font Licences in `public-site/public/fonts/`. The vendored Sites Vite integration retains its upstream licence under `public-site/scripts/vite/`. Other framework and component dependencies retain their own notices and licences.

The stone UI texture is a rendered crop from the game's loading-screen artwork. PNG/TIFF map releases and rendered comparison images retain the original artwork's ownership; they are not licensed as newly created game assets.

The implementation was developed with AI-assisted coding, with source attribution, executable/resource guards, regression tests, native frame comparisons, and full download verification. The exported map pixels come from the original game renderer and source tiles, not image generation or inpainting.
