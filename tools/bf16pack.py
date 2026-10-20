#!/usr/bin/env python3
"""bf16pack — lossless packer for BF16/FP16 tensor files.

Byte-plane split (low=mantissa, high=sign+exponent), each plane compressed as
its own zstd stream (the high plane is where all the structure lives).
Container: [BFPK][u64 orig_len][32B sha256][u64 lo_len][lo zstd][hi zstd].
Streams in 64 MiB chunks; two passes over the input, so memory stays flat.

pack:   bf16pack.py pack   <input> <output.bfpk> [zstd-level]
unpack: bf16pack.py unpack <input.bfpk> <output>
Unpack verifies SHA-256 of the reconstruction before declaring success.
Requires the zstd CLI. Stdlib otherwise.
"""
import hashlib
import struct
import subprocess
import sys

MAGIC = b"BFPK"
CHUNK = 64 * 1024 * 1024


def _plane_pass(src_path, plane, proc_in):
    with open(src_path, "rb") as f:
        carry = b""
        while True:
            chunk = carry + f.read(CHUNK)
            if not chunk:
                break
            if len(chunk) % 2 and len(chunk) == CHUNK + len(carry):
                carry = chunk[-1:]
                chunk = chunk[:-1]
            else:
                carry = b""
            proc_in.write(chunk[plane::2])
    proc_in.close()


def pack(src, dst, level="22"):
    h = hashlib.sha256()
    n = 0
    with open(src, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
            n += len(b)
    planes = []
    for plane in (0, 1):
        args = ["zstd", "-T0", "-c", f"-{level}"]
        if int(level) > 19:
            args.insert(1, "--ultra")
        out = dst + f".plane{plane}.tmp"
        with open(out, "wb") as sink:
            p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=sink)
            _plane_pass(src, plane, p.stdin)
            if p.wait() != 0:
                sys.exit(f"zstd failed on plane {plane}")
        planes.append(out)
    import os
    lo_len = os.path.getsize(planes[0])
    with open(dst, "wb") as out:
        out.write(MAGIC + struct.pack("<Q", n) + h.digest() + struct.pack("<Q", lo_len))
        for tmp in planes:
            with open(tmp, "rb") as f:
                while True:
                    b = f.read(CHUNK)
                    if not b:
                        break
                    out.write(b)
            os.remove(tmp)
    csize = os.path.getsize(dst)
    print(f"packed {n} -> {csize} bytes  ratio={n/csize:.4f}  saved={100*(1-csize/n):.2f}%")


def unpack(src, dst):
    with open(src, "rb") as f:
        head = f.read(4 + 8 + 32 + 8)
        if head[:4] != MAGIC:
            sys.exit("bad magic")
        (n,) = struct.unpack("<Q", head[4:12])
        digest = head[12:44]
        (lo_len,) = struct.unpack("<Q", head[44:52])
        lo_start = f.tell()

    def stream(offset, length):
        p = subprocess.Popen(["zstd", "-dc"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        def feed():
            with open(src, "rb") as f:
                f.seek(offset)
                left = length
                while left > 0:
                    b = f.read(min(CHUNK, left))
                    if not b:
                        break
                    p.stdin.write(b)
                    left -= len(b)
            p.stdin.close()
        import threading
        t = threading.Thread(target=feed)
        t.start()
        return p, t

    import os
    hi_len = os.path.getsize(src) - lo_start - lo_len
    plo, tlo = stream(lo_start, lo_len)
    phi, thi = stream(lo_start + lo_len, hi_len)
    h = hashlib.sha256()
    written = 0
    with open(dst, "wb") as out:
        while written < n:
            want = min(CHUNK, n - written)
            lo = plo.stdout.read((want + 1) // 2)
            hi = phi.stdout.read(want // 2)
            buf = bytearray(len(lo) + len(hi))
            buf[0::2] = lo
            buf[1::2] = hi
            if not buf:
                sys.exit("short stream")
            out.write(buf)
            h.update(buf)
            written += len(buf)
    for t, p in ((tlo, plo), (thi, phi)):
        t.join()
        p.wait()
    if h.digest() != digest:
        sys.exit("SHA-256 MISMATCH — unpack corrupt")
    print(f"unpacked {written} bytes, sha256 verified OK")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "pack":
        pack(sys.argv[2], sys.argv[3], *(sys.argv[4:] or ["22"]))
    elif cmd == "unpack":
        unpack(sys.argv[2], sys.argv[3])
    else:
        sys.exit("usage: pack <in> <out.bfpk> [level] | unpack <in.bfpk> <out>")
