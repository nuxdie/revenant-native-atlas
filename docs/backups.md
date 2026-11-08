# Download and restore a backup

Verified public mirrors:

- [MediaFire](https://www.mediafire.com/folder/8cb21hsx5s9aj/Revenant_Native_Atlas_-_2026-11-08)
- [MEGA](https://mega.nz/folder/LpwxGRTZ#Qr7J9HzEMwvJB9qFDK5D0Q)
- [Google Drive](https://drive.google.com/open?id=1EZFyEhEZdlRQxXqkIMDFyNPYaC2Tm3GR)

Each mirror contains 378 files, approximately 5.05 GB, without game executables
or original resource archives.

The backup contains both editions: 33 July maps and 37 retail locations, with
74 lighting images in total. Every image has its full-resolution PNG, lossless
tiled BigTIFF, overview, native tile pack and tile index. Files are individual
downloads; there are no ZIP wrappers.

Retail levels 41, 42 and 43 retain their **Recovered** labels and omit 10, 4 and
2 source placements. The missing object definitions have not been recovered.
Animation phases and quest states are snapshots, as described in the main
rendering documentation.

Each copy includes `backup-manifest.json`, both viewer catalogs, SHA-256
checksums and the source credits. Google Drive uses edition/location folders;
MediaFire and MEGA use edition/location prefixes in each filename. The manifest
maps either layout back to the viewer's immutable revision paths.

Download the complete contents of one backup folder, then run from this source
repository:

```sh
python3 tools/restore_backup.py --source /path/to/downloaded-backup --data data
python3 tools/serve_atlas.py --data data --port 8767
```

Open <http://127.0.0.1:8767/>. The restore verifies every manifest file before
installing it and refuses to overwrite different existing data. It installs
catalogs last. Use `--check-only` to verify without restoring, or `--link` to
avoid a second copy when the downloaded backup will remain in place.

Keep the source checkout too: image hosting and viewer hosting are independent.
The accounts belong to the atlas owner; free-host retention policies and account
access still govern each copy.

## Verification

All MediaFire file sizes and server SHA-256 hashes match the originals. All
MEGA public file sizes and MAC commitments match the locally hashed originals;
this does not mean every remote encrypted byte has been downloaded again.
Anonymous PNG and BigTIFF sample downloads from both mirrors also match their
original SHA-256 hashes. Google Drive's exact file count, byte count and every
source/remote MD5 checksum also match. A restored local viewer passed all 296
image, overview and tile availability requests across both editions.

The current bundle includes the native sound-marker presentation correction
for 26 retail lighting images. Existing public folder links are retained;
the earlier local export snapshots remain unchanged. See
[rendering details](rendering.md) and [current mirror receipts](../evidence/external-backups.json).
