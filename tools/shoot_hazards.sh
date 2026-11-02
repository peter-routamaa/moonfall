#!/bin/bash
# A contact sheet of the signature hazards (the ?scene=haz page), with the game at a phone's height (320 x 570 game px).
#   tools/shoot_hazards.sh <out.png>       Needs tools/test_pages.py run first and tools/out served on $PORT (default 8766).
OUT=$1
CHROME=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
PORT=${PORT:-8766}
DIR="$(cd "$(dirname "$0")" && pwd)"
# The game runs in a 640 x 1140 frame (so 570 game px tall) and draws the 640 x 400 sheet at the frame's top.
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run --user-data-dir="$DIR/.chrome" --window-size=700,1300 \
  --force-device-scale-factor=2 --virtual-time-budget=20000 --screenshot="$OUT.full.png" "http://localhost:$PORT/frame.html?w=640&h=1140&scene=haz" 2>/dev/null
sips -c 800 1280 --cropOffset 160 60 "$OUT.full.png" --out "$OUT" >/dev/null && rm -f "$OUT.full.png"
