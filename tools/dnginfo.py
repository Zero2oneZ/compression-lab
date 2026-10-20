#!/usr/bin/env python3
"""Minimal DNG/TIFF IFD walker: reports Compression, dimensions, bits per IFD.
Stdlib only. Usage: dnginfo.py <file.dng> [...]"""
import struct
import sys

COMP = {1: "uncompressed", 7: "lossless-JPEG", 8: "deflate", 34892: "lossy-JPEG (DNG)"}


def walk(path):
    with open(path, "rb") as f:
        data = f.read()
    bo = "<" if data[:2] == b"II" else ">"
    (magic,) = struct.unpack(bo + "H", data[2:4])
    if magic != 42:
        print(f"{path}: not TIFF")
        return
    (off,) = struct.unpack(bo + "I", data[4:8])
    seen, queue, n = set(), [off], 0
    while queue:
        ifd = queue.pop(0)
        if ifd in seen or ifd == 0 or ifd + 2 > len(data):
            continue
        seen.add(ifd)
        (count,) = struct.unpack(bo + "H", data[ifd:ifd + 2])
        tags = {}
        for i in range(count):
            e = ifd + 2 + i * 12
            tag, typ, cnt = struct.unpack(bo + "HHI", data[e:e + 8])
            raw = data[e + 8:e + 12]
            if typ == 3 and cnt == 1:
                (val,) = struct.unpack(bo + "H", raw[:2])
            elif typ == 4 and cnt == 1:
                (val,) = struct.unpack(bo + "I", raw)
            elif typ == 4 and cnt > 1:
                (ptr,) = struct.unpack(bo + "I", raw)
                val = list(struct.unpack(bo + f"{cnt}I", data[ptr:ptr + 4 * cnt]))
            else:
                val = None
            tags[tag] = val
        comp = tags.get(259)
        w, h = tags.get(256), tags.get(257)
        strips = tags.get(279)
        total = sum(strips) if isinstance(strips, list) else strips
        if comp is not None:
            print(f"{path} IFD@{ifd}: {w}x{h} comp={comp}({COMP.get(comp, '?')}) "
                  f"imageBytes={total}")
        sub = tags.get(330)
        if isinstance(sub, int):
            queue.append(sub)
        elif isinstance(sub, list):
            queue.extend(sub)
        (nxt,) = struct.unpack(bo + "I", data[ifd + 2 + count * 12:ifd + 6 + count * 12])
        queue.append(nxt)
        n += 1
        if n > 32:
            break


for p in sys.argv[1:]:
    walk(p)
