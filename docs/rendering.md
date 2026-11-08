# Rendering and validation

## Dataset and renderer selection

The production capture profile is the English GOG 1.22L `Revenant.exe`, SHA-256 `28bec27387bf53a553da320dd4883d00ff5bcc5a5f3d2658cca8e8ed586372b5` (MD5 `e9a42fe6baef4e7bbf2ac610d7a3e313`). It reports Revenant 1.22, build May 8, 2000. `native/retail_dataset.py` hashes the installed packs, reads their actual map records and inventories the authored lighting cycles.

The earlier July executable and loose data are a different baseline. Their forest/town ambient values, ruins placement and fire-geyser imagery differ from retail. `native/provider.json` and the older compatibility code describe that historical installation; they must not be applied to the retail binary.

The production renderer is the original retail executable through Wine/D7VK, with RealTimeLight enabled and GammaLevel 3. Revisited's Classic and modern modes remain comparison candidates. The recorded scene harness applies the requested mode and clock explicitly; screenshots are not labelled "modern" merely because a settings file exists. No Revisited enhancement assets replace the retail resources in those comparisons.

The comparison scenes cover Misthaven by day and night, the resurrection pit and the cavern geyser area. Whole-viewport differences include unsynchronized animation phases, so their error measurements are diagnostic, not a static-surface certification. The comparison does not establish equivalence for other Revisited configurations or platforms.

## Day and night

The `NIGHTAMBLIGHT`/`NIGHTAMBCOLOR` entries in each module's AREA.DEF determine whether a location has a cycle. The forest/Misthaven and ruins are rendered at noon and 01:00. Fixed-lighting areas have one image; a night preference in the viewer does not invent a darker cave or a second identical download.

Native day/night changes are rendered by the game, including the area ambient colour and light contribution. The night files are not tinted daytime exports. The viewer chooses an immutable image revision for each state and retains its world position and scale.

## Capture and stitching

The integrated editor provides camera control while pausing gameplay AI. Each 640 × 340 source records its actual camera, scroll, native frame progress, time, ambient values, executable identity, source digest and motion-sampling configuration. The controller requests the original full redraw. The strengthened barrier also observes the retail background-update and rectangle queues and requires quiet native frames before capture.

Presentation changes hide mouse overlays and prevent editor edge panning. The editor's 2D and 3D imagery filters are changed to the normal gameplay treatment of `OF_EDITOR`/`OF_INVISIBLE`. These changes do not alter light emission, textures, geometry, particles or raster arithmetic. Every process patch has byte guards; the on-disk executable and packs remain unchanged.

Retail also draws the ambient-sound `speaker` placeholder (`Misc/Speaker.I3D`, type ID `0xad92bc10`) without either visibility flag. It appears as a small pale diamond or cylinder, including inside the stranded fish and along the shore. Fresh editor captures reproduce it, so it is not a PNG seam. The available comparison does not establish its visibility during normal retail gameplay.

The `speaker_mesh_hidden_v1` capture profile suppresses only that placeholder's native draw call, using the exact effect class and null-terminated type name. Sound objects, their placements and audio behaviour are retained. Other scenery follows the original draw path; no image pixels are painted, recoloured or synthesized. The guarded process hook preserves the displaced instruction and registers, and an executable machine-code regression checks its selection and continuation paths.

The retail inventory identifies speakers on 22 levels, covering 26 lighting images. Affected owned source frames are captured again, followed by complete provenance, ownership-edge, PNG and BigTIFF checks. The plan records every speaker position; publication rejects unfiltered sources owning pixels near those positions. July images are unchanged: its level 0 contains no speaker placements, and its two inventoried speakers are covered by the church roof. These presentation changes do not recover the 16 missing placements in the separately labeled recovery maps.

Quilting selects unchanged source pixels across overlaps. A 16-bit ownership map identifies each output pixel's source. The auditor rechecks every owned RGB value, source hashes, registration, coverage boundaries and neighbouring pixel pairs at ownership cuts. Acceptance requires no missing sources, no nonblack boundaries into uncaptured coverage and no unexplained static ownership edges. Longer native motion sampling and registered extra views are used where a join needs review; disagreement alone is not a motion mask.

Four nonsensical off-world placements in the shipped packs are reported in the dataset inventory and excluded from camera planning. Empty campaign levels 33 and 90 have no drawable map. Test geometry that is genuinely visible in the base module is not repainted as invented terrain.

The original renderer can cull scenery when a coarse camera falls outside world XY. Recovery uses another original editor camera at higher Z with in-world XY and the same observed native pixel scroll. An immutable reference records at least 1,000 identical, nonblack static pixels; additions over a reference's black culling gaps are allowed. Where coverage extends beyond one viewport, each registered overlap is checked back through an acyclic chain to an ordinary in-world view. The final ownership-edge audit still requires zero unexplained static joins. No source image is shifted, resampled or painted to make it fit.

Registration normally compares the entire static overlap. Where the viewport's outer apron has view-dependent culling, `native_core_cross_strip_v1` uses a fixed geometric strip: rows 42–297 for horizontal neighbours, or columns 64–575 for vertical neighbours. It rejects changes to existing static foreground inside that strip. This only establishes camera alignment; apron pixels remain included in provenance, overlap-difference reports and the complete stitched-edge audit. A measured disagreement is never converted into a motion mask. Level 31's recovered views registered against 18,053–28,587 identical foreground pixels and then passed the complete edge audit with zero unexplained static joins.

Authored `BGEFFECT` areas such as the labyrinth's `labback` have a background outside the finite map geometry. Their export uses the complete padded rectangular map bounds, including every interior native viewport. The audit reports the outer background crop separately, rejects interior capture holes, and retains the same pixel and ownership-edge checks.

Switching from campaign to deathmatch passes through unused level 90 so the old area's exit clears its scripts before mounting another archive. Otherwise retail can try to open a campaign script such as `keep.s` from a deathmatch module and stop. Each new deathmatch source records the module actually mounted in the native manager; changing a requested module name in metadata is insufficient.

Full PNGs are streamed. TIFFs contain one full-resolution RGB image in tiled BigTIFF format, with lossless Deflate and horizontal prediction. Every tile is decoded and checked against the source tiles, including sparse black areas and partial edges. The publisher switches the public catalog only after the complete retail set is verified.

## Earlier compatibility work

The July pipeline's barrel/crate colour-band correction, shoreline recaptures and missing geyser blend-controller correction are retained for that installation. They are guarded by its executable/resource hashes. The retail fire-geyser resource already contains the authored blend controller: SHA-256 `64102fd39d039f0ca24af8b1b39eff4529ea988a69471fe49728b8932984c77b`. The July mesh patch is not installed in the retail process.

## Limits

A stitched PNG/TIFF contains successive local animation phases, not one simultaneous island frame. Base-module editor state differs from quest progress and spawned objects in a save. Separate levels retain their own coordinate systems.

D7VK ignores the application's display gamma-ramp request; the game's ambient gamma adjustment still applies. Old graphics hardware and other wrappers can produce different pixels. Matching this original-game configuration does not prove identity to every setting in Ross's video, whose compressed/scaled frames are not a lossless framebuffer reference.

Pixel provenance proves where a pixel came from, not that a renderer has no artifacts. Visual effect reviews and fresh original-game comparisons are required alongside the ownership audit. No report should be read as a universal pixel-perfect claim.

## Labeled retail recoveries

Legacy version-1 sectors remain in retail levels 41–43. Sixteen placements use eleven unique object IDs absent from the installed retail class catalog (ten placements on level 41, four on level 42 and two on level 43). The original executable stops with “Bad object” when loading that part of the map, and a restart reproduces it. Those IDs were not found in the available July class catalog either. The inventory reports these unresolved types, including whether the native loader can skip a bounded object record. The live atlas includes these three as explicitly labeled recovery maps: only those 16 unresolvable slots are omitted, and surviving record bytes and positions are preserved. No substitute artwork or guessed aliases are used. Raster acceptance does not recover the absent source definitions; strict exact-publication completion remains false.

## Deterministic outdoor ambient state

Retail `SetAmbientLight` adds the GammaLevel ambient offset; `FadeAmbient` omits it. At GammaLevel 3, a nearby area transition can therefore drop intensity by 10 and retain that value afterwards. The same shore rendered at 40 after a direct visit and at 30 after passing through Misthaven, despite both areas authoring AMBLIGHT 30. This is an original-engine state bug, not a different water texture. Revisited documents and corrects that fade path in its own renderer.

Outdoor capture chooses the authored ambient through the original editor's `amb` and `ambcolor` commands after camera changes. The native setter retains the selected GammaLevel 3 offset: daytime 30 becomes native 40, night 35 becomes native 45. No raster arithmetic or output RGB values are patched. Actual ambient, colour, fade completion and clock are checked, including the end of each capture. Earlier frames with the history-dependent brightness are retained privately for comparison and recaptured rather than recoloured.

A shore → town → shore repeatability check under this policy reproduced all 217,600 static viewport pixels exactly. This defines a reproducible lighting configuration; it does not reproduce every erroneous fading state in a played save or establish Ross's unknown graphics settings.

## Hourly lighting clock

The existing day image is captured at 12:00 and night at 01:00. Retail `rules.def` sets `TWILIGHT 60, 8`; the real-time grid uses the continuous integer ramp from the original `Daylight` function at `0x0047ea00`. Dawn spans 05:30–06:29 and dusk 17:30–18:29. At whole hours, 07:00–17:00 share full daylight, 00:00–05:00 and 19:00–23:00 share night, and 06:00/18:00 share the intermediate light state. Thus the hourly viewer needs three native image states per cycling location, rather than 24 colour-filtered images. It does not claim minute precision, synchronized animation, or time-dependent quest simulation.

`native.retail_clock` captures the new twilight image at 06:00. Integer interpolation of the authored light values gives raw intensity 31 and colour (161,174,252), becoming native intensity 41 at GammaLevel 3. A fresh dawn/dusk comparison reproduced all 203,455 observed static pixels exactly. The viewer preserves the map position and zoom across lighting changes, hides the clock for fixed-lighting locations, and holds downloads when a requested native state is not available. The retail catalog is separate from the July edition; both are live.

The older July world's daytime ambient is 80 with colour (250,245,240), while retail authors 30 with colour (250,250,250). Recorded native intensities at the same gamma setting are 90 and 40. This explains why retail daylight is darker; noon already selects its maximum daylight value. The comparison in `evidence/retail-lighting-comparison/` uses the same camera in both versions.

## Wine desktop remapping

A later audit found three source frames containing unrelated compositor contents immediately after a Wine desktop was mapped. Their exports and all 15 corresponding remote objects were withdrawn. The older public catalog did not reference those revisions. A pass over 16,373 sources found three matches to the observed browser signature; authored full-screen animated backgrounds were reviewed separately. This targeted signature check is not a universal application-origin detector.

Capture now requests the original game's redraw and waits for native frames **after** mapping and naming the XComposite pixmap, before reading it. A regression check covers that ordering. The affected sources are recaptured and must pass the full provenance and static-edge checks again before publication. Pixel ownership alone did not prove the pixels belonged to the intended application, and an almost-full temporal mask concealed the erroneous joins; that earlier acceptance was invalid.


A further acquisition guard renames the current XComposite backing pixmap for
every read. A Wine desktop resize can leave an old named pixmap readable while
it stops receiving frames. A generated red/blue X11 fixture reproduces that
failure; per-read naming returns the new backing. The original-game A/B/A camera
repeat returned all 68,833 sampled static foreground pixels identically while
the intermediate camera produced a different image. Invalid private diagnostic
captures were archived and recaptured; this check does not replace the native
source, coverage, seam, and exported-file validation gates.
