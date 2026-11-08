#!/usr/bin/env python3
"""Verify a flat or structured atlas backup and restore the mirror data layout."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath


def relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value:
        raise ValueError(f"Unsafe backup path: {value!r}")
    return Path(*path.parts)


def digest(path):
    with path.open("rb") as handle:
        value = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
        return value.hexdigest()


def restore(source, data, link=False, check_only=False):
    source, data = source.resolve(), data.resolve()
    manifest = json.loads((source / "backup-manifest.json").read_text())
    work, destinations = [], set()
    for row in manifest["files"]:
        file = source / relative(row["path"])
        if file.stat().st_size != row["bytes"] or digest(file) != row["sha256"]:
            raise ValueError(f"Backup verification failed: {row['path']}")
        destination = row.get("canonical_path")
        if destination is None:
            if row["path"] not in ("catalog.json", "retail-preview-catalog.json"):
                continue
            destination = row["path"]
        target = data / relative(destination)
        target.parent.resolve().relative_to(data)
        if target in destinations:
            raise ValueError(f"Duplicate destination: {destination}")
        destinations.add(target)
        if target.exists() or target.is_symlink():
            if not target.is_file() or digest(target) != row["sha256"]:
                raise ValueError(f"Refusing to replace different existing data: {target}")
        else:
            work.append((file, target))
    print(f"Verified {len(manifest['files'])} backup files; {len(work)} files to restore.")
    if check_only:
        return
    # Install catalogs last so an interrupted restore cannot advertise missing data.
    work.sort(key=lambda pair: pair[1].name in ("catalog.json", "retail-preview-catalog.json"))
    for file, target in work:
        target.parent.mkdir(parents=True, exist_ok=True)
        if link:
            target.symlink_to(file)
        else:
            temporary = target.with_name(target.name + ".restoring")
            with file.open("rb") as incoming, temporary.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            shutil.copystat(file, temporary)
            temporary.rename(target)
    print(f"Atlas data ready: {data}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Folder containing backup-manifest.json")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--link", action="store_true", help="Link to the backup instead of copying; keep it in place")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    restore(args.source, args.data, args.link, args.check_only)
