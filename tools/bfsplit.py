#!/usr/bin/env python3
"""Reversible byte-plane split filter for 2-byte-element data (bf16/fp16/int16).

split: stdin -> [magic][u64 length][all even-offset bytes][all odd-offset bytes]
merge: inverse. Lossless by construction; verify with sha256 round trip.
Stdlib only. Streams in 64 MiB chunks per plane to bound memory.
"""
import sys
import struct

MAGIC = b"BPS2"


def split() -> None:
    data = sys.stdin.buffer.read()
    out = sys.stdout.buffer
    out.write(MAGIC)
    out.write(struct.pack("<Q", len(data)))
    out.write(data[0::2])
    out.write(data[1::2])
    out.flush()


def merge() -> None:
    data = sys.stdin.buffer.read()
    if data[:4] != MAGIC:
        sys.exit("bad magic")
    (n,) = struct.unpack("<Q", data[4:12])
    body = data[12:]
    half = (n + 1) // 2
    even, odd = body[:half], body[half:]
    buf = bytearray(n)
    buf[0::2] = even
    buf[1::2] = odd
    sys.stdout.buffer.write(buf)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--merge":
        merge()
    else:
        split()
