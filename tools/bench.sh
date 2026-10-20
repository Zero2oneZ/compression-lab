#!/usr/bin/env bash
# Sandboxed compression sweep. Usage: bench.sh <input-file> <label> <results.tsv> [bf16]
# Every codec runs in its own systemd user scope with a hard memory cap.
# Round trip is verified by sha256 before a result is recorded.
set -u
IN=$1; LABEL=$2; OUT=$3; BF16=${4:-no}
LAB=$(cd "$(dirname "$0")" && pwd)
TMP=$LAB/tmp.$$; mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

ORIG=$(stat -c%s "$IN")
OSHA=$(sha256sum < "$IN" | cut -d' ' -f1)
echo "input=$IN bytes=$ORIG sha256=$OSHA"

SD="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 timeout 3600"

run() {
  local name=$1 ccmd=$2 dcmd=$3
  local cfile=$TMP/c.bin t0 t1 t2 csize sha ok ct dt
  t0=$(date +%s.%N)
  $SD bash -c "$ccmd" < "$IN" > "$cfile" 2>"$TMP/err" || { echo "$name COMPRESS-FAIL $(head -c200 "$TMP/err")"; rm -f "$cfile"; return; }
  t1=$(date +%s.%N)
  sha=$($SD bash -c "$dcmd" < "$cfile" 2>"$TMP/err" | sha256sum | cut -d' ' -f1)
  t2=$(date +%s.%N)
  csize=$(stat -c%s "$cfile"); rm -f "$cfile"
  ok=BAD; [ "$sha" = "$OSHA" ] && ok=OK
  ct=$(echo "$t1 $t0" | awk '{printf "%.1f", $1-$2}')
  dt=$(echo "$t2 $t1" | awk '{printf "%.1f", $1-$2}')
  local ratio pct
  ratio=$(echo "$ORIG $csize" | awk '{printf "%.4f", $1/$2}')
  pct=$(echo "$ORIG $csize" | awk '{printf "%.2f", 100*(1-$2/$1)}')
  echo -e "$LABEL\t$name\t$ORIG\t$csize\t$ratio\t$pct\t$ct\t$dt\t$ok" >> "$OUT"
  echo "$name: $csize bytes  ratio=$ratio  saved=$pct%  c=${ct}s d=${dt}s  $ok"
}

run "gzip-9"        "gzip -9c"                                   "gzip -dc"
run "bzip2-9"       "bzip2 -9c"                                  "bzip2 -dc"
run "zstd-19"       "zstd -19 -T0 -c"                            "zstd -dc"
run "zstd-22-long"  "zstd --ultra -22 --long=31 -T0 -c"          "zstd -dc --long=31"
run "xz-9e"         "xz -9e -T1 -c"                              "xz -dc"

if [ "$BF16" = bf16 ]; then
  run "bps+zstd-19"      "python3 -I $LAB/bfsplit.py | zstd -19 -T0 -c"                   "zstd -dc | python3 -I $LAB/bfsplit.py --merge"
  run "bps+zstd-22-long" "python3 -I $LAB/bfsplit.py | zstd --ultra -22 --long=31 -T0 -c" "zstd -dc --long=31 | python3 -I $LAB/bfsplit.py --merge"
  run "bps+xz-9e"        "python3 -I $LAB/bfsplit.py | xz -9e -T1 -c"                     "xz -dc | python3 -I $LAB/bfsplit.py --merge"
fi
echo "DONE $LABEL"
