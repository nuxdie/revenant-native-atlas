# Mirror and host the atlas

The source is independent of the ChatGPT Sites URL. The retail dataset release is currently a draft while community announcements are on hold. Until it is published, use the live atlas for image downloads: the GitHub download helper cannot fetch an anonymous draft. A published dataset includes PNGs, BigTIFFs, tile packs, indexes and overview images without redundant ZIP wrappers.

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

The catalog contains 37 distinct locations and 39 images. Levels 0 and 5 contain separate day/night entries under `variants`; their immutable revisions and file sizes differ. The viewer preserves position and zoom when switching. Other levels have one fixed-lighting entry. The API continues to identify the actual image by `revision` and `level`; `variant=day`, `night` or `fixed` optionally labels the download filename.

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

The retail publisher reads its key through hidden stdin and verifies complete remote bytes. It stages accepted immutable objects incrementally, but adds the catalog upload only when all 39 PNG/TIFF pairs are ready. Keep the catalog as the last upload. `runtime/retail-publication/upload-manifest.json` records paths, keys, sizes and hashes; do not distribute its local paths as public provenance. Verify the deployed catalog, both lighting states, file sizes, byte ranges and download hashes before announcing it. It does not silently rebuild the native maps. ZIPs and private validation JSONs are excluded from the public file endpoint.

## Prepare a GitHub dataset release

After the complete retail set passes:

```sh
python3 tools/stage_retail_release.py --out release-assets
```

This refuses an incomplete dataset. It links each accepted image, overview and native tile pack under names that include both level and lighting state, then writes `release-manifest.json` with portable object paths, byte counts and SHA-256 digests. The mirror helper consumes that manifest; no game files, local paths, credentials or private validation reports are included.

Upload those files to a **draft** GitHub release with `gh release upload TAG release-assets/*`. Keep the release a draft while announcements or dataset publication are on hold. Publishing the draft is a separate deliberate action, not a step performed by the staging helper.
