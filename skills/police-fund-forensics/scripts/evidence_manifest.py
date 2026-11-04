#!/usr/bin/env python3
"""Create/verify a local content manifest. No evidence files are modified."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import sys


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def hash_file(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("not a regular file: " + str(path))
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    if not stat.S_ISREG(current.st_mode) or not (identity(before) == identity(after) == identity(current)):
        raise ValueError("file changed during read: " + str(path))
    return {"bytes": before.st_size, "sha256": digest.hexdigest()}


def file_list(root):
    result = []

    def on_error(error):
        raise error

    for folder, dirs, names in os.walk(root, followlinks=False, onerror=on_error):
        for name in dirs + names:
            path = Path(folder) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError("symlink or special file: " + str(path))
        for name in names:
            path = Path(folder) / name
            path.resolve().relative_to(root)
            result.append(path.relative_to(root).as_posix())
    return sorted(result)


def snapshot(root):
    names = file_list(root)
    files = [{"path": name, **hash_file(root / name)} for name in names]
    if names != file_list(root):
        raise ValueError("directory contents changed during scan")
    return {"schema_version": 1, "algorithm": "sha256", "files": files}


def outside_root(path, root):
    resolved = path.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError("manifest must be outside the material root")


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def validate_manifest(value):
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("unsupported manifest schema")
    if value.get("algorithm") != "sha256" or not isinstance(value.get("files"), list):
        raise ValueError("invalid manifest structure")
    result = {}
    for item in value["files"]:
        if not isinstance(item, dict):
            raise ValueError("invalid manifest entry")
        name = item.get("path")
        if not isinstance(name, str) or not name or "\\" in name or "\0" in name:
            raise ValueError("invalid relative path")
        p = PurePosixPath(name)
        if p.is_absolute() or PureWindowsPath(name).drive or ".." in p.parts or p.as_posix() != name or name == ".":
            raise ValueError("unsafe relative path")
        if name in result:
            raise ValueError("duplicate manifest path")
        if type(item.get("bytes")) is not int or item["bytes"] < 0:
            raise ValueError("invalid file size")
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("invalid sha256")
        result[name] = {"bytes": item["bytes"], "sha256": item["sha256"]}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "verify"):
        p = sub.add_parser(command)
        p.add_argument("--root", type=Path, required=True)
        p.add_argument("--output" if command == "create" else "--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.root.is_symlink():
            raise ValueError("material root must not be a symlink")
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("material root must be a directory")
        target = args.output if args.command == "create" else args.manifest
        outside_root(target, root)
        if args.command == "create":
            value = snapshot(root)
            write_new(target, value)
            print(json.dumps({"created": True, "file_count": len(value["files"])}))
            return 0
        expected = validate_manifest(json.loads(target.read_text(encoding="utf-8")))
        actual = validate_manifest(snapshot(root))
        result = {
            "missing": sorted(expected.keys() - actual.keys()),
            "unexpected": sorted(actual.keys() - expected.keys()),
            "changed": sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k]),
        }
        result["matches"] = not any(result.values())
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["matches"] else 1
    except (OSError, ValueError, TypeError) as exc:
        print("manifest error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
