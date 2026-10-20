#!/usr/bin/env python3
"""Identity manifest: prove exactly which bytes a folder contains, in a few KB.

usage: hashmanifest.py make <dir> [glob]   -> manifest JSON on stdout
       hashmanifest.py check <dir> <manifest.json>

The manifest names every matching file with its length and SHA-256. Against a
receiver who already holds the data, the manifest IS the data (H(X|X)=0):
send the kilobytes, they verify the gigabytes. Stdlib only.
"""
import fnmatch
import hashlib
import json
import os
import sys


def walk(root, pattern):
    out = []
    for r, _dirs, files in os.walk(root):
        for n in sorted(files):
            p = os.path.join(r, n)
            if pattern and not fnmatch.fnmatch(n, pattern):
                continue
            out.append(p)
    return sorted(out)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 24)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    mode, root = sys.argv[1], sys.argv[2]
    if mode == "make":
        pattern = sys.argv[3] if len(sys.argv) > 3 else None
        entries = []
        for p in walk(root, pattern):
            entries.append({"path": os.path.relpath(p, root),
                            "bytes": os.path.getsize(p), "sha256": digest(p)})
        json.dump({"root_note": os.path.basename(os.path.abspath(root)),
                   "files": len(entries),
                   "total_bytes": sum(e["bytes"] for e in entries),
                   "entries": entries}, sys.stdout, indent=1)
        sys.stdout.write("\n")
    elif mode == "check":
        with open(sys.argv[3]) as f:
            man = json.load(f)
        bad = 0
        for e in man["entries"]:
            p = os.path.join(root, e["path"])
            ok = (os.path.isfile(p) and os.path.getsize(p) == e["bytes"]
                  and digest(p) == e["sha256"])
            if not ok:
                print(f"MISMATCH {e['path']}")
                bad += 1
        print(f"{len(man['entries']) - bad}/{len(man['entries'])} files identical")
        sys.exit(1 if bad else 0)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
