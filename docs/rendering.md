# Rendering and validation

The fidelity renderer is the original Revenant executable identified by `native/provider.json`, running through Wine/D7VK. The older static renderer is a coverage baseline, not a substitute for original-engine lighting and animated 3D imagery.

## Capture and stitching

The editor provides camera control while pausing gameplay AI. Each 640 × 340 viewport records the requested and observed camera, scroll, native frame progress, area ambience, time, source digest, and sampling configuration. The game performs its own full redraw and background-queue barrier before capture. Changed pixels are measured across actual native frames; masks are not inferred from disagreements between overlapping images.

Quilting chooses unmodified pixels from overlapping source viewports. A 16-bit ownership map identifies the source for each output pixel. The auditor rechecks every owned RGB value, coverage boundaries, viewport registration, source hashes, and actual neighbouring pixel pairs at ownership cuts. Publication requires no missing captures, no nonblack boundaries into uncaptured coverage, and zero unexplained static ownership edges.

Full PNGs are streamed rather than assembled as a multi-billion-pixel in-memory canvas. TIFFs use a single full-resolution RGB image in tiled BigTIFF format, with Deflate compression and horizontal prediction. Their full decoded tile pixels are checked, including sparse black areas and partial edges.

## Corrections

- **Barrel/crate shadow colour bands:** the old dispatcher treated ARGB1555 destination coverage as RGB565 colour. The guarded black-shadow correction preserves coverage and native channel rounding, clipping and mirroring. Other draw paths retain the original dispatcher.
- **Shoreline bands:** stale original-game source frames were retired and replaced with fresh, registered captures. The earlier session's low-level cause is not established. Source digests and frame-advancement checks prevent those frames from silently returning.
- **Geyser diamonds:** June 1999 loose resources omit base-quad blend configuration found in later fire-geyser data. The full mesh correction covers fire/spark templates restored to defaults when PartSys controllers close, as well as the base glow. Compatibility work is restricted to default/additive surfaces in the pinned geyser meshes; authored geometry, particle controllers, textures, placements and lighting remain in the original engine. The release evidence identifies the exact accepted correction and recapture scope.

The executable and resource files on disk remain unchanged. Compatibility changes exist only in the isolated process and are guarded by binary/resource signatures.

## Limits

A stitched PNG/TIFF freezes successive local animation phases; it is not one simultaneous island frame. AI is paused in the editor, and hidden or spawned objects depend on game state. Separate levels retain their own coordinate systems rather than being laid out as invented physical geography. Gamma handling and old graphics APIs differ across hardware; this is a reproducible Wine/D7VK configuration, not universal historical-GPU equivalence.

A pixel-provenance pass does not prove that the source renderer is artifact-free. Visual checks and fresh game comparisons remain necessary. The current release's evidence and known limitations must be read together; do not interpret a local exact match as a universal pixel-perfect claim.
