# Mirror and host the atlas

The source is independent of the ChatGPT Sites URL. The GitHub dataset release remains an unpublished staging draft. Until it is published, use the live atlas for image downloads: the GitHub download helper cannot fetch an anonymous draft. A published dataset includes PNGs, BigTIFFs, tile packs, indexes and overview images without redundant ZIP wrappers.

## Local mirror, without game files or cloud accounts

From the repository root:

```sh
python3 tools/fetch_release.py --viewer
python3 tools/serve_atlas.py --data data --port 8767
```

Open <http://127.0.0.1:8767/>. `fetch_release.py` verifies byte counts and SHA-256 before installing each file. Re-running it skips verified existing files. Files are downloaded individually; there is no giant ZIP to unpack.

To mirror only the island:

```sh
python3 tools/fetch_release.py --viewer --levels 0
python3 tools/serve_atlas.py --data data
```

To fetch just the TIFFs without the viewer:

```sh
python3 tools/fetch_release.py --formats tif
```

For a lightweight viewer-only mirror, omit the full-image downloads:

```sh
python3 tools/fetch_release.py --viewer --formats ''
```

That keeps the pan/zoom viewer but full-image download buttons require the corresponding files. The default command includes both formats. Pick a frozen version with `--release TAG` rather than `latest`.

## Public independent hosting

The mirror server binds to loopback by default. Put it behind your usual HTTPS reverse proxy on a VPS, or use `--host 0.0.0.0` only when you intend to expose that listener. It is a read-only server: it has no upload endpoint and needs no upload key. Keep `data/catalog.json` and `data/releases/...` in the layout created by the download helper.

The HTTP interface is deliberately small:

- `GET /api/catalog`: published level metadata and PNG/TIFF sizes.
- `GET /api/tile?revision=...&level=...&x=...&y=...`: a native PNG tile, streamed from its packed byte range.
- `GET /api/file?revision=...&level=...&name=...`: overview or full-resolution PNG/TIFF, with byte-range support.

The unchanged viewer is in `public-site/public/`. It can be served by another backend implementing those routes.

The live viewer offers 33 July maps and 37 retail locations / 41 lighting images. Retail levels 0 and 5 contain separate day, twilight and night entries under `variants`; other locations have fixed lighting. Levels 41–43 carry permanent recovery labels and omission counts of 10, 4 and 2. Switching editions preserves position and zoom on shared locations. The API identifies each actual image by `revision` and `level`; `variant` labels lighting in download filenames.

## Original Worker/R2 application

`public-site/` contains the complete Vinext/Cloudflare Worker source used for the hosted site, including pinned npm dependencies and the Sites integration. The public snapshot omits the original account's project identifier and all local credentials/state.

```sh
cd public-site
npm ci
npm run build
npm start
```

This builds and runs the Worker locally. Its R2 binding must be populated before map requests work. The independent mirror above is the easiest route when you do not need the Worker.

For ChatGPT Sites, register your own Site and add its `project_id` to `.openai/hosting.json`, preserving `r2: "BUCKET"`. Follow the Sites source-helper/build/publication workflow. For your own Cloudflare deployment, configure the Worker entry point, assets and R2 binding in your own account; do not reuse this project's account identity.

The hosted uploader expects the `ATLAS_UPLOAD_KEY` runtime secret. Generate your own secret and set it through the hosting provider. Never put it in JavaScript, Git, release assets, command-line arguments or the public catalog.

After reproducing and accepting native maps:

```sh
python3 -m native.publish_retail
python3 -m native.publish_retail --publish https://YOUR-HOST
```

If a connection fails, resume the staged immutable files without regenerating the upload manifest:

```sh
python3 -m native.publish_retail --resume-staged --passes 5 --publish https://YOUR-HOST
```

Remote verification reads the complete object through bounded batches of four 1 MiB ranges, checks each range's exact position and hashes the returned bytes in order. A failed file is held while other files continue, then retried in another pass. `runtime/retail-publication/upload-status.json` records the batch's checked-file count and failures. A finished process reports held files explicitly; the catalog is never sent while any referenced file remains unverified or the retail dataset is incomplete.

The retail publisher reads its key through hidden stdin and verifies complete remote bytes. It stages accepted immutable objects incrementally, but adds the catalog upload only when all 39 PNG/TIFF pairs are ready. Keep the catalog as the last upload. `runtime/retail-publication/upload-manifest.json` records paths, keys, sizes and hashes; do not distribute its local paths as public provenance. Verify the deployed catalog, both lighting states, file sizes, byte ranges and download hashes before announcing it. It does not silently rebuild the native maps. ZIPs and private validation JSONs are excluded from the public file endpoint.

The hourly retail edition uses a separate catalog. Preparing or uploading even a complete baseline retail set never overwrites the July edition’s `catalog.json`. Publish the composed retail catalog through `native.clock_preview`:

```sh
python3 -m native.clock_preview --watch --publish https://YOUR-HOST
```

Open `/?dataset=retail&level=5&time=06:00`. The publisher includes only accepted native images, verifies their remote bytes before updating `retail-preview-catalog.json`, and can pick up completed twilight captures during its bounded six-hour watch. A missing hour state is visibly pending and has no download link. The clock supports whole hours; indoor locations retain their fixed lighting. The viewer exposes both editions through the July 1999 / Retail 1.22L switch. July remains the default and uses `catalog.json`; `?dataset=july` selects it explicitly. The scrollable location column under the logo lists only maps available in the selected edition. Switching preserves location and view where shared; otherwise it restores the last valid location in that edition, or its first location. Credits opens from the bottom left. PNG and TIFF filenames identify the edition. The 24-hour dial appears only for locations with hourly capture metadata. For a local mirror, place the optional retail catalog at `retail-preview-catalog.json` alongside the original `catalog.json`, and include both catalogs’ immutable revisions under `releases/`.

## Prepare a GitHub dataset release

After the complete retail set passes:

```sh
python3 tools/stage_retail_release.py --out release-assets
```

This refuses an incomplete dataset. It links each accepted image, overview and native tile pack under names that include both level and lighting state, then writes `release-manifest.json` with portable object paths, byte counts and SHA-256 digests. The mirror helper consumes that manifest; no game files, local paths, credentials or private validation reports are included.

Upload those files to a **draft** GitHub release with `gh release upload TAG release-assets/*`. Keep the release a draft while announcements or dataset publication are on hold. Publishing the draft is a separate deliberate action, not a step performed by the staging helper.


## Publish explicitly labeled recovery renders

The complete available retail collection has 37 locations / 41 lighting images.
Levels 41, 42 and 43 are recoveries with 10, 4 and 2 omitted placements. They do
not qualify as exact restorations. After explicitly choosing to include these
recoveries, publish the audited output root with:

```sh
python3 -m native.clock_preview --publish https://YOUR-HOST \
  --recovery-root /path/to/audited/recovery/output
```

This opt-in verifies PNG/TIFF digests and raster acceptance, requires the audited
omission manifest, includes a `recovery` object on each affected map, and uses
`-recovered-` immutable revision keys. The viewer labels each affected selection
and its missing-object count. HTTP downloads retain `recovered` in their filename
even if the edition query is omitted. The merged catalog reports
`available_complete: true` but `publication_complete: false` while source
placements remain unrecovered. Ordinary preparation still withholds these maps.
The July catalog remains independent. Unnecessary edition-summary captions have
been removed from the viewer.
