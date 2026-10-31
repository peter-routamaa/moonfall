#!/bin/bash
# Screenshot a scene at an exact phone size, at 2x, with headless Chrome.
#   tools/shoot.sh <width> <height> <out.png> "<query>"      e.g.  tools/shoot.sh 375 667 cafe.png "scene=cafe&face=shop"
# Needs tools/test_pages.py run first and tools/out served on $PORT (default 8766):  python3 -m http.server 8766 -d tools/out
# Chrome won't make windows narrower than about 500 px, so the page sits in an iframe (frame.html) and the shot is cropped.
W=$1; H=$2; OUT=$3; Q=$4
CHROME=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
PORT=${PORT:-8766}
DIR="$(cd "$(dirname "$0")" && pwd)"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run --user-data-dir="$DIR/.chrome" --window-size=700,900 \
  --force-device-scale-factor=2 --virtual-time-budget=15000 --screenshot="$OUT.full.png" "http://localhost:$PORT/frame.html?w=$W&h=$H&$Q" 2>/dev/null
# Keep the middle W x H (at 2x); sips is macOS's image tool.
sips -c $((H * 2)) $((W * 2)) "$OUT.full.png" --out "$OUT" >/dev/null && rm -f "$OUT.full.png"
