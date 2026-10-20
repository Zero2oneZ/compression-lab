# Compression Lab

One machine, one weekend, every number a SHA-256-verified round trip. Predictions were
registered before measurement; negative results are reported next to the wins.

## Headline: a packaging audit of Cyberpunk 2077

Retail Steam install, 85 GB with Phantom Liberty, 57 REDengine `RDAR` archives
(Oodle-Kraken-chunked). Measured on 256 MiB slices per category plus one full 3.04 GB
archive. Byte-exact (compress, decompress, hash must equal the original):

| Archive category | Best byte-exact saving | Predicted beforehand |
| --- | --- | --- |
| gamedata | 18.8% (xz -9e) | 5-10% |
| nightcity (world) | 18.7% (zstd --ultra -22 --long) | 5-8% |
| audio soundbanks (Wwise) | 3.9% | 0-3% |
| video (Bink) | 1.9% | 0-2% |
| GI probe data | 0.0% | "wildcard" |
| terrain (full 3.04 GB file) | 1.7% (zstd -19) | - |

**Finding 1.** The content archives carry ~19% redundancy that per-chunk Kraken cannot
see. The diagnostic is the signature: gzip (32 KiB window) recovers under 2% while
long-window codecs recover 18+ — the redundancy lies *between* compressed chunks, not
inside them. Size-weighted across the install this is ~10%, about 8.5 GB per download.

**Finding 2.** The GI probe data is packed to its entropy floor — 0.0% recoverable by
any codec at any setting. Credit where due: that data was packaged by someone who
measured.

**Honest scope.** One game, one patch level, one platform. This is outer recompression
of shipped archives; it proves recoverable redundancy exists, not that it ships without
affecting streaming/seek behavior. A chunk-aware repack (decompress, dedupe, repack
solid) is estimated at 1.8-2x on content archives — an estimate, clearly labeled, and
exactly what a pilot inside the real pipeline would measure. Long-range matching and
solid repacking are known techniques; the contribution here is the verified,
categorized, reproducible audit, not a new algorithm.

## The rest of the lab (same discipline, same weekend)

| Target | Best verified result |
| --- | --- |
| BF16 LLM weights, full 3.99 GB shard | 33.10% saved, byte-exact, 6m12s — measured order-0 entropy ceiling is 33.7%, so this is the floor, reached |
| FP8 weights | 23.3% — and MXFP4 (4-bit) weights: 3.0%. Quantization consumes exactly the redundancy lossless codecs feed on |
| Quake (2021 mg1) pak0, 497 MB | 77.6% (xz, dictionary >= file size; the dict rule alone is worth +0.65 over `-9e` defaults) |
| Doom WAD, 143 MB | 65.2% (xz -9e) |
| Zip repack (pk3, 86 MB) | solid tar+xz beats direct recompression 28.1% vs 12.7% (content-equivalent; the zip held 35 duplicate entry paths) |
| Camera RAW (Pixel DNGs, 427 MB) | 1.8% max — the mosaic is already lossless-JPEG inside the DNG container |
| HDRI EXR, float32 | byte-plane split + per-plane zstd beats the file's own PIZ codec by 16.2%, pixels bit-exact |

Negative results kept: sorting files inside a solid archive changed nothing once the
window spanned the archive (0.003%); xz delta filters hurt interleaved BF16; zstd past
level 19 loses on noise-like planes while costing 6x the time.

## The rules the numbers kept obeying

1. Entropy is invariant under representation; only surprise costs bytes.
2. In floating-point data, structure concentrates in the sign/exponent byte planes.
   Splitting planes before coding exposes it (`tools/bfsplit.py`, `tools/plane6.py`).
3. Compression window >= archive size, or cross-chunk redundancy is left behind.
4. A shared dictionary changes everything: to a receiver who already holds the data,
   a kilobyte manifest of hashes IS the gigabytes (`tools/hashmanifest.py`).

## Reproducing

`tools/bench.sh <file> <label> <out.tsv>` runs the codec ladder with verified round
trips (zstd 1.5.7, xz 5.8.3, bzip2, gzip). `results.tsv` is this weekend's raw output.
`tools/bf16pack.py` is the BF16/FP16 shipping format (streaming plane split + per-plane
zstd, SHA-256-sealed container). Runs were memory-capped via
`systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0`.

No third-party bytes are redistributed here: tools and measurements only.
