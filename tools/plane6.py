#!/usr/bin/env python3
"""Split a file into N byte-stride planes, zstd each, verify merge. Stdlib + zstd CLI.

usage: plane6.py <input> <stride> <outdir> [zstd-level]
Streams in stride-aligned chunks; writes plane files + .zst, then re-merges from
the planes and compares SHA-256 against the input. Prints per-plane and total.
"""
import hashlib
import os
import subprocess
import sys

inp, stride, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
level = sys.argv[4] if len(sys.argv) > 4 else "19"
os.makedirs(outdir, exist_ok=True)
CHUNK = 6 * 1024 * 1024 * stride // stride * stride or stride

h = hashlib.sha256()
planes = [open(os.path.join(outdir, f"p{j}"), "wb") for j in range(stride)]
n = 0
with open(inp, "rb") as f:
    carry = b""
    while True:
        chunk = carry + f.read(CHUNK)
        if not chunk:
            break
        rem = len(chunk) % stride
        if rem and len(chunk) >= CHUNK:
            carry, chunk = chunk[-rem:], chunk[:-rem]
        else:
            carry = b""
        h.update(chunk)
        n += len(chunk)
        for j in range(stride):
            planes[j].write(chunk[j::stride])
for p in planes:
    p.close()
orig_sha = h.hexdigest()

total_c = 0
for j in range(stride):
    pf = os.path.join(outdir, f"p{j}")
    zf = pf + ".zst"
    args = ["zstd", "-T0", "-f", f"-{level}", "-q", pf, "-o", zf]
    if int(level) > 19:
        args.insert(1, "--ultra")
    subprocess.run(args, check=True)
    ps, zs = os.path.getsize(pf), os.path.getsize(zf)
    total_c += zs
    print(f"p{j}: {ps} -> {zs}  ({100 * (1 - zs / ps):.1f}% saved)", flush=True)

hm = hashlib.sha256()
readers = [open(os.path.join(outdir, f"p{j}"), "rb") for j in range(stride)]
left = n
while left > 0:
    rows = min(CHUNK // stride, (left + stride - 1) // stride)
    parts = [r.read(rows) for r in readers]
    buf = bytearray(sum(len(x) for x in parts))
    for j, part in enumerate(parts):
        buf[j::stride] = part
    hm.update(buf)
    left -= len(buf)
for r in readers:
    r.close()
ok = hm.hexdigest() == orig_sha
print(f"TOTAL {n} -> {total_c}  ratio={n/total_c:.4f}  saved={100*(1-total_c/n):.2f}%  "
      f"merge={'OK' if ok else 'MISMATCH'}", flush=True)
