# Mirror and host the atlas

The release is independent of the ChatGPT Sites URL. Source and individual map images live on GitHub; the release also includes the original tile packs, indexes and overview images used by the web viewer.

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
python3 -m native.bigtiff
python3 -m native.publish_pack
python3 -m native.publish_upload https://YOUR-HOST
python3 -m native.verify_public https://YOUR-HOST
```

The publisher reads its key through hidden stdin, verifies complete remote bytes, and updates the catalog only after the referenced objects are available. It does not silently rebuild the native maps. ZIPs and private validation JSONs are excluded from the public file endpoint.
