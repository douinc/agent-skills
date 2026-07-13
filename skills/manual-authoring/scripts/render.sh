#!/usr/bin/env bash
# Render a self-contained manual HTML to an A4 PDF via headless Chrome.
# Usage: render.sh <input.html> <output.pdf>
# Relative img/ paths in the HTML resolve against the HTML's own directory,
# so keep the HTML and its img/ folder together.
set -euo pipefail
IN="${1:?usage: render.sh <input.html> <output.pdf>}"
OUT="${2:?usage: render.sh <input.html> <output.pdf>}"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="/Applications/Chromium.app/Contents/MacOS/Chromium"

# --no-pdf-header-footer keeps Chrome from stamping its own URL/date margins.
# The @page { size:A4; margin:0 } in the template controls the real geometry.
"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT" "file://$IN" 2>/dev/null
echo "wrote $OUT"
