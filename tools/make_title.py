#!/usr/bin/env python3
"""Render 'CodedbyAKSA' in Fredoka One as an animated gradient SVG.

Regenerates profile/assets/title.svg -- the wordmark at the top of the org
profile. Glyphs are converted to vector paths so the result renders
identically everywhere without needing the font installed or fetched, which
matters because GitHub serves README images through a proxy that cannot
load web fonts.

Setup:
    pip install fonttools brotli
    curl -sS -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
        "https://fonts.googleapis.com/css2?family=Fredoka+One" \
      | grep -o 'https://[^)]*woff2' | head -1 | xargs curl -sSL -o FredokaOne.woff2

Usage:
    python3 make_title.py

Tweak TEXT to change the wordmark, or the <stop> colours in the "flow"
gradient below to restyle it.
"""
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.misc.transform import Transform

TEXT = "CodedbyAKSA"
FONT = "FredokaOne.woff2"
SIZE = 132          # px per em
PAD_X, PAD_Y = 46, 34

font = TTFont(FONT)
upem = font["head"].unitsPerEm
cmap = font.getBestCmap()
glyphset = font.getGlyphSet()
hmtx = font["hmtx"]

scale = SIZE / upem

# --- kerning (legacy 'kern' table if present) ---
kern = {}
if "kern" in font:
    for st in font["kern"].kernTables:
        kern.update(st.kernTable)

# --- lay out glyphs, collecting transformed outlines ---
records, x = [], 0.0
prev = None
for ch in TEXT:
    gname = cmap[ord(ch)]
    if prev is not None:
        x += kern.get((prev, gname), 0) * scale
    # font Y is up, SVG Y is down -> flip
    t = Transform(scale, 0, 0, -scale, x, 0)
    rec = RecordingPen()
    glyphset[gname].draw(TransformPen(rec, t))
    records.append(rec)
    x += hmtx[gname][0] * scale
    prev = gname

# --- measure the drawn ink so the viewBox hugs the text ---
bounds = BoundsPen(None)
for rec in records:
    rec.replay(bounds)
x0, y0, x1, y1 = bounds.bounds

shift = Transform(1, 0, 0, 1, PAD_X - x0, PAD_Y - y0)
d_parts = []
for rec in records:
    pen = SVGPathPen(None, ntos=lambda v: f"{v:.1f}")
    rec.replay(TransformPen(pen, shift))
    d_parts.append(pen.getCommands())
d = "".join(d_parts)

W = round(x1 - x0 + PAD_X * 2)
H = round(y1 - y0 + PAD_Y * 2)
PERIOD = round(W * 0.62)          # gradient repeat length
SHINE_W = round(W * 0.20)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{TEXT}">
  <title>{TEXT}</title>
  <defs>
    <!-- blue -> indigo -> purple -> fuchsia, looping seamlessly -->
    <linearGradient id="flow" gradientUnits="userSpaceOnUse"
                    x1="0" y1="0" x2="{PERIOD}" y2="{H}" spreadMethod="repeat">
      <stop offset="0.00" stop-color="#38BDF8"/>
      <stop offset="0.22" stop-color="#5B8DEF"/>
      <stop offset="0.44" stop-color="#8B5CF6"/>
      <stop offset="0.66" stop-color="#C026D3"/>
      <stop offset="0.84" stop-color="#7C3AED"/>
      <stop offset="1.00" stop-color="#38BDF8"/>
      <animateTransform attributeName="gradientTransform" type="translate"
                        from="0 0" to="{PERIOD} 0" dur="7s" repeatCount="indefinite"/>
    </linearGradient>

    <!-- travelling specular highlight -->
    <linearGradient id="shine" gradientUnits="objectBoundingBox" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0.00" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="0.50" stop-color="#ffffff" stop-opacity="0.5"/>
      <stop offset="1.00" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>

    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="9" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="b"/></feMerge>
    </filter>

    <path id="letters" d="{d}"/>
    <mask id="ink">
      <use href="#letters" xlink:href="#letters" fill="#ffffff"/>
    </mask>
  </defs>

  <!-- pulsing halo -->
  <use href="#letters" xlink:href="#letters" fill="#8B5CF6" filter="url(#glow)" opacity="0.45">
    <animate attributeName="opacity" values="0.25;0.6;0.25" dur="3.4s" repeatCount="indefinite"/>
  </use>

  <!-- body -->
  <use href="#letters" xlink:href="#letters" fill="url(#flow)"/>

  <!-- highlight sweep, clipped to the letterforms -->
  <g mask="url(#ink)">
    <rect x="{-SHINE_W}" y="0" width="{SHINE_W}" height="{H}" fill="url(#shine)">
      <animate attributeName="x" from="{-SHINE_W}" to="{W}"
               dur="4.5s" begin="0s" repeatCount="indefinite"/>
    </rect>
  </g>
</svg>
'''

out = "/home/user/.github/profile/assets/title.svg"
with open(out, "w") as fh:
    fh.write(svg)
print(f"wrote {out}  ({W}x{H}, {len(svg)} bytes)")
