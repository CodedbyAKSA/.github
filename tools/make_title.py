#!/usr/bin/env python3
"""Render the animated 'CodedbyAKSA' hero banner for the org profile.

Regenerates profile/assets/title.svg. The banner is a synthwave/tech scene:
a neon perspective grid, falling binary rain, rockets that launch and then
orbit the wordmark, firework bursts, a coding laptop and a trophy -- with
the title typing in one letter at a time on load.

Everything is a self-contained SVG using SMIL animation. The wordmark glyphs
are converted to vector paths because GitHub serves README images through a
proxy that cannot load web fonts, so a `font-family` reference would fall
back to something generic on most machines.

Setup:
    pip install fonttools brotli
    curl -sS -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
        "https://fonts.googleapis.com/css2?family=Fredoka+One" \
      | grep -o 'https://[^)]*woff2' | head -1 | xargs curl -sSL -o FredokaOne.woff2

Usage:
    python3 tools/make_title.py

Tweak TEXT for a different wordmark, or the "flow" gradient stops to restyle.
"""
import os
import random

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.misc.transform import Transform

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "profile", "assets", "title.svg")

TEXT = "CodedbyAKSA"
FONT_CANDIDATES = [
    os.path.join(HERE, "FredokaOne.woff2"),
    "FredokaOne.woff2",
]

# --- canvas -----------------------------------------------------------------
W, H = 1200, 430
HORIZON = 268           # where the neon floor meets the sky
TITLE_W = 880           # target ink width of the wordmark
TITLE_CY = 176          # vertical centre of the wordmark

DEPTH = 14              # 3D extrusion steps
DX, DY = 1.3, 1.4       # per-step extrusion offset

# animation clock
T_LAUNCH = 0.0          # rockets lift off
T_BURST = 1.15          # fireworks bloom
T_TYPE = 1.45           # first letter lands
TYPE_STEP = 0.115       # gap between letters
T_ORBIT = 3.1           # rocket starts circling the title

rng = random.Random(7)


# --- wordmark ---------------------------------------------------------------
def load_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return TTFont(p)
    raise SystemExit(
        "FredokaOne.woff2 not found -- see the download command in this file's "
        "docstring, and drop it next to this script."
    )


font = load_font()
upem = font["head"].unitsPerEm
cmap = font.getBestCmap()
glyphset = font.getGlyphSet()
hmtx = font["hmtx"]

kern = {}
if "kern" in font:
    for st in font["kern"].kernTables:
        kern.update(st.kernTable)

# lay the string out in font units (y still points up)
records, advances, x, prev = [], [], 0.0, None
for ch in TEXT:
    gname = cmap[ord(ch)]
    if prev is not None:
        x += kern.get((prev, gname), 0)
    rec = RecordingPen()
    glyphset[gname].draw(TransformPen(rec, Transform(1, 0, 0, 1, x, 0)))
    records.append(rec)
    advances.append(x)
    x += hmtx[gname][0]
    prev = gname

bounds = BoundsPen(None)
for rec in records:
    rec.replay(bounds)
bx0, by0, bx1, by1 = bounds.bounds

scale = TITLE_W / (bx1 - bx0)
ink_h = (by1 - by0) * scale
# flip y, scale, then centre the ink box on the canvas
place = Transform(
    scale, 0, 0, -scale,
    (W - TITLE_W) / 2 - bx0 * scale,
    TITLE_CY + ink_h / 2 - (-by0 * scale) - (by0 * scale) + (by0 * scale),
)
# solve the vertical offset directly: top of ink should sit at TITLE_CY - ink_h/2
place = Transform(scale, 0, 0, -scale,
                  (W - TITLE_W) / 2 - bx0 * scale,
                  TITLE_CY + ink_h / 2 + by0 * scale)

letters = []
for rec in records:
    pen = SVGPathPen(None, ntos=lambda v: f"{v:.1f}")
    rec.replay(TransformPen(pen, place))
    letters.append(pen.getCommands())

# per-letter x centre, used to park the caret and to aim the pop-in
centres = []
for rec in records:
    b = BoundsPen(None)
    rec.replay(b)
    if b.bounds:
        lx0, _, lx1, _ = b.bounds
        centres.append(((lx0 + lx1) / 2 * scale + (W - TITLE_W) / 2 - bx0 * scale))
    else:
        centres.append(W / 2)

type_end = T_TYPE + TYPE_STEP * len(TEXT)


def letter_markup():
    out = []
    for i, d in enumerate(letters):
        t0 = T_TYPE + i * TYPE_STEP
        cx, cy = centres[i], TITLE_CY
        ext = "".join(
            f'<use href="#g{i}" xlink:href="#g{i}" '
            f'transform="translate({k * DX:.2f} {k * DY:.2f})"/>'
            for k in range(DEPTH, 0, -1)
        )
        out.append(f'''
    <g opacity="0">
      <animate attributeName="opacity" from="0" to="1" dur="0.13s"
               begin="{t0:.3f}s" fill="freeze"/>
      <g transform="translate({cx:.1f} {cy:.1f})">
        <animateTransform attributeName="transform" type="scale"
                          values="1.4;0.94;1" keyTimes="0;0.65;1" dur="0.26s"
                          additive="sum" begin="{t0:.3f}s" fill="freeze"/>
        <g transform="translate({-cx:.1f} {-cy:.1f})">
          <g fill="url(#extrude)">{ext}</g>
          <use href="#g{i}" xlink:href="#g{i}" fill="url(#flow)"/>
          <use href="#g{i}" xlink:href="#g{i}" fill="none"
               stroke="#c4b5fd" stroke-width="1.1" opacity="0.5"/>
        </g>
      </g>
    </g>''')
    return "".join(out)


# --- neon floor -------------------------------------------------------------
def floor_markup():
    parts = []
    # rays converging on the vanishing point
    for i in range(-11, 12):
        x_bottom = W / 2 + i * 148
        parts.append(
            f'<line x1="{W/2}" y1="{HORIZON}" x2="{x_bottom:.0f}" y2="{H}" '
            f'stroke="url(#rayfade)" stroke-width="1.6"/>'
        )
    # horizontal lines sweeping toward the viewer
    n = 13
    dur = 4.6
    for i in range(n):
        begin = -dur * i / n
        parts.append(f'''
    <line x1="0" x2="{W}" y1="{HORIZON}" y2="{HORIZON}"
          stroke="#c084fc" stroke-width="1" opacity="0">
      <animate attributeName="y1" values="{HORIZON};{H}" dur="{dur}s"
               begin="{begin:.2f}s" repeatCount="indefinite"
               calcMode="spline" keySplines="0.42 0 1 1"/>
      <animate attributeName="y2" values="{HORIZON};{H}" dur="{dur}s"
               begin="{begin:.2f}s" repeatCount="indefinite"
               calcMode="spline" keySplines="0.42 0 1 1"/>
      <animate attributeName="opacity" values="0;0.75;0.75;0" keyTimes="0;0.12;0.7;1"
               dur="{dur}s" begin="{begin:.2f}s" repeatCount="indefinite"/>
      <animate attributeName="stroke-width" values="0.6;2.4" dur="{dur}s"
               begin="{begin:.2f}s" repeatCount="indefinite"
               calcMode="spline" keySplines="0.42 0 1 1"/>
    </line>''')
    return "".join(parts)


# --- binary rain ------------------------------------------------------------
def rain_markup():
    cols = []
    for i in range(30):
        x = 14 + i * 40 + rng.randint(-8, 8)
        if 300 < x < 900 and rng.random() < 0.55:
            continue                      # keep the middle clearer for the title
        bits = " ".join(rng.choice("01") for _ in range(rng.randint(9, 15)))
        dur = rng.uniform(5.5, 11.0)
        begin = -rng.uniform(0, dur)
        size = rng.choice([11, 12, 13])
        op = rng.uniform(0.26, 0.55)
        cols.append(f'''
    <text x="{x}" y="-20" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
          font-size="{size}" fill="#22d3ee" opacity="{op:.2f}"
          writing-mode="tb" letter-spacing="3">{bits}
      <animateTransform attributeName="transform" type="translate"
                        values="0 -40;0 {H + 60}" dur="{dur:.1f}s"
                        begin="{begin:.1f}s" repeatCount="indefinite"/>
    </text>''')
    return "".join(cols)


# --- rockets ----------------------------------------------------------------
ROCKET = '''
  <g id="rocket">
    <!-- drawn nose-right so rotate="auto" aligns it with the flight path -->
    <path d="M26 0 L4 -8 Q-10 -9 -12 0 Q-10 9 4 8 Z" fill="url(#hull)"/>
    <path d="M4 -8 L-6 -19 L-13 -6 Z" fill="#7c3aed"/>
    <path d="M4 8 L-6 19 L-13 6 Z" fill="#7c3aed"/>
    <circle cx="9" cy="0" r="4.1" fill="#0b1026"/>
    <circle cx="9" cy="0" r="2.6" fill="#67e8f9"/>
    <path d="M-12 -5 Q-30 0 -12 5 Z" fill="#f0abfc" opacity="0.95">
      <animate attributeName="opacity" values="0.95;0.45;0.95" dur="0.16s"
               repeatCount="indefinite"/>
    </path>
    <path d="M-12 -3 Q-40 0 -12 3 Z" fill="#a5f3fc" opacity="0.7">
      <animate attributeName="opacity" values="0.7;0.2;0.7" dur="0.11s"
               repeatCount="indefinite"/>
    </path>
  </g>'''

ORBIT = (f"M {W/2 - 452},{TITLE_CY + 8} "
         f"a 452,120 0 1,0 904,0 a 452,120 0 1,0 -904,0")


def launch_markup():
    """Two rockets streaking up out of frame, with exhaust plumes."""
    out = []
    for x, delay, hue in ((452, 0.0, "#c084fc"), (748, 0.16, "#38bdf8")):
        out.append(f'''
    <g opacity="0">
      <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.08;0.75;1"
               dur="1.5s" begin="{T_LAUNCH + delay:.2f}s" fill="freeze"/>
      <path d="M{x},{H + 30} L{x},{H + 30}" stroke="{hue}" stroke-width="26"
            stroke-linecap="round" opacity="0.55" filter="url(#soft)">
        <animate attributeName="d" values="M{x},{H + 30} L{x},{H + 30};M{x},{H + 30} L{x},-40"
                 dur="1.5s" begin="{T_LAUNCH + delay:.2f}s" fill="freeze"/>
      </path>
      <g transform="translate({x} {H + 30}) rotate(-90)">
        <animateTransform attributeName="transform" type="translate"
                          values="{x} {H + 30};{x} -60" dur="1.5s"
                          begin="{T_LAUNCH + delay:.2f}s" fill="freeze"
                          calcMode="spline" keySplines="0.3 0 0.7 1"/>
        <g transform="rotate(-90)">
          <use href="#rocket" xlink:href="#rocket" transform="scale(1.7)"/>
        </g>
      </g>
    </g>''')
    return "".join(out)


def burst_markup():
    """Firework bursts behind the wordmark."""
    out = []
    for cx, cy, col, delay in ((338, 128, "#e879f9", 0.0),
                               (872, 138, "#38bdf8", 0.22),
                               (600, 96, "#a78bfa", 0.44)):
        spokes = []
        for k in range(18):
            a = k * 20
            spokes.append(
                f'<line x1="0" y1="0" x2="0" y2="-54" stroke="{col}" '
                f'stroke-width="2.4" stroke-linecap="round" transform="rotate({a})"/>'
            )
            spokes.append(
                f'<circle cx="0" cy="-58" r="2.6" fill="#fff" opacity="0.9" '
                f'transform="rotate({a})"/>'
            )
        out.append(f'''
    <g transform="translate({cx} {cy})" opacity="0" filter="url(#soft)">
      <g>{''.join(spokes)}</g>
      <animate attributeName="opacity" values="0;1;0.85;0" keyTimes="0;0.12;0.5;1"
               dur="1.5s" begin="{T_BURST + delay:.2f}s;{T_BURST + delay + 9:.2f}s"
               repeatCount="1" repeatDur="indefinite"/>
      <animateTransform attributeName="transform" type="scale" values="0.15;1.15;1.4"
                        dur="1.5s" begin="{T_BURST + delay:.2f}s;{T_BURST + delay + 9:.2f}s"
                        additive="sum" calcMode="spline"
                        keySplines="0.1 0.8 0.3 1;0.4 0 0.8 1"/>
    </g>''')
    return "".join(out)


# --- props ------------------------------------------------------------------
def laptop_markup():
    """Laptop with code scrolling on the screen."""
    lines = []
    palette = ["#67e8f9", "#c4b5fd", "#f0abfc", "#a5f3fc", "#ddd6fe"]
    for i in range(6):
        w0 = rng.randint(14, 38)
        w1 = rng.randint(14, 38)
        lines.append(f'''
      <rect x="{-31 + (6 if i in (1, 2, 4) else 0)}" y="{-27 + i * 8}" height="3.4" rx="1.7"
            width="{w0}" fill="{palette[i % len(palette)]}" opacity="0.85">
        <animate attributeName="width" values="{w0};{w1};{w0}" dur="{2.2 + i * 0.3:.1f}s"
                 repeatCount="indefinite"/>
      </rect>''')
    return f'''
  <g transform="translate(118 322)" opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.6s"
             begin="{type_end + 0.1:.2f}s" fill="freeze"/>
    <g>
      <animateTransform attributeName="transform" type="translate"
                        values="0 0;0 -7;0 0" dur="4.2s" repeatCount="indefinite"
                        calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>
      <g transform="scale(1.35)">
        <rect x="-38" y="-34" width="76" height="52" rx="5"
              fill="#0b1026" stroke="#7c3aed" stroke-width="2.4"/>
        <rect x="-33" y="-30" width="66" height="44" rx="3" fill="#11082e"/>
        {''.join(lines)}
        <path d="M-49 20 L49 20 L44 27 L-44 27 Z" fill="#1e1b4b"
              stroke="#7c3aed" stroke-width="2.2" stroke-linejoin="round"/>
        <ellipse cx="0" cy="34" rx="56" ry="6" fill="#a855f7" opacity="0.16"/>
      </g>
    </g>
  </g>'''


def trophy_markup():
    sparks = []
    for dx, dy, r, d in ((-46, -34, 4.4, 1.7), (44, -26, 3.6, 2.1),
                         (-38, 22, 3.2, 2.5), (46, 20, 4.0, 1.9)):
        sparks.append(f'''
      <path d="M{dx} {dy - r} L{dx + r * 0.34} {dy - r * 0.34} L{dx + r} {dy}
               L{dx + r * 0.34} {dy + r * 0.34} L{dx} {dy + r}
               L{dx - r * 0.34} {dy + r * 0.34} L{dx - r} {dy}
               L{dx - r * 0.34} {dy - r * 0.34} Z" fill="#fde68a">
        <animate attributeName="opacity" values="0.15;1;0.15" dur="{d}s"
                 repeatCount="indefinite"/>
      </path>''')
    return f'''
  <g transform="translate(1082 322)" opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.6s"
             begin="{type_end + 0.25:.2f}s" fill="freeze"/>
    <g>
      <animateTransform attributeName="transform" type="translate"
                        values="0 0;0 -8;0 0" dur="3.6s" repeatCount="indefinite"
                        calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>
      <g transform="scale(1.25)">
        <path d="M-30 -36 L30 -36 L27 -8 Q22 12 0 15 Q-22 12 -27 -8 Z"
              fill="url(#gold)" stroke="#b45309" stroke-width="2"/>
        <path d="M-30 -30 Q-49 -30 -47 -13 Q-45 2 -28 2" fill="none"
              stroke="url(#gold)" stroke-width="5.5" stroke-linecap="round"/>
        <path d="M30 -30 Q49 -30 47 -13 Q45 2 28 2" fill="none"
              stroke="url(#gold)" stroke-width="5.5" stroke-linecap="round"/>
        <rect x="-6" y="14" width="12" height="14" fill="url(#gold)"/>
        <path d="M-22 28 L22 28 L26 40 L-26 40 Z" fill="url(#gold)"
              stroke="#b45309" stroke-width="2" stroke-linejoin="round"/>
        <path d="M0 -28 L5.2 -17.6 L16.6 -16 L8.3 -8 L10.3 3.2 L0 -2.1
                 L-10.3 3.2 L-8.3 -8 L-16.6 -16 L-5.2 -17.6 Z" fill="#fffbeb" opacity="0.92"/>
        <ellipse cx="0" cy="46" rx="46" ry="6" fill="#fbbf24" opacity="0.18"/>
        {''.join(sparks)}
      </g>
    </g>
  </g>'''


def brackets_markup():
    """A floating </> glyph, drawn as strokes so no font is needed."""
    return f'''
  <g transform="translate(600 372)" opacity="0" filter="url(#soft)">
    <animate attributeName="opacity" from="0" to="0.75" dur="0.8s"
             begin="{type_end + 0.4:.2f}s" fill="freeze"/>
    <g stroke="#67e8f9" stroke-width="4" fill="none"
       stroke-linecap="round" stroke-linejoin="round">
      <animateTransform attributeName="transform" type="translate"
                        values="0 0;0 -6;0 0" dur="5s" repeatCount="indefinite"
                        calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>
      <path d="M-26 -11 L-38 0 L-26 11"/>
      <path d="M-7 13 L7 -13" stroke="#f0abfc"/>
      <path d="M26 -11 L38 0 L26 11"/>
    </g>
  </g>'''


# --- assemble ---------------------------------------------------------------
glyph_defs = "".join(
    f'<path id="g{i}" d="{d}"/>' for i, d in enumerate(letters)
)

caret_x = [f"{c:.0f}" for c in centres] + [f"{centres[-1] + 46:.0f}"]

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{TEXT}">
  <title>{TEXT}</title>
  <defs>
    {glyph_defs}
    {ROCKET}

    <linearGradient id="flow" gradientUnits="userSpaceOnUse"
                    x1="0" y1="0" x2="{round(W * 0.55)}" y2="{H}" spreadMethod="repeat">
      <stop offset="0.00" stop-color="#38BDF8"/>
      <stop offset="0.22" stop-color="#60A5FA"/>
      <stop offset="0.44" stop-color="#A78BFA"/>
      <stop offset="0.66" stop-color="#E879F9"/>
      <stop offset="0.84" stop-color="#8B5CF6"/>
      <stop offset="1.00" stop-color="#38BDF8"/>
      <animateTransform attributeName="gradientTransform" type="translate"
                        from="0 0" to="{round(W * 0.55)} 0" dur="7s"
                        repeatCount="indefinite"/>
    </linearGradient>

    <linearGradient id="extrude" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#4c1d95"/>
      <stop offset="1" stop-color="#12082e"/>
    </linearGradient>

    <linearGradient id="hull" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e0e7ff"/>
      <stop offset="0.5" stop-color="#818cf8"/>
      <stop offset="1" stop-color="#4338ca"/>
    </linearGradient>

    <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fde68a"/>
      <stop offset="0.5" stop-color="#fbbf24"/>
      <stop offset="1" stop-color="#d97706"/>
    </linearGradient>

    <linearGradient id="rayfade" gradientUnits="userSpaceOnUse"
                    x1="0" y1="{HORIZON}" x2="0" y2="{H}">
      <stop offset="0" stop-color="#a855f7" stop-opacity="0"/>
      <stop offset="1" stop-color="#e879f9" stop-opacity="0.55"/>
    </linearGradient>

    <radialGradient id="horizonglow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#c084fc" stop-opacity="0.45"/>
      <stop offset="0.45" stop-color="#a855f7" stop-opacity="0.18"/>
      <stop offset="1" stop-color="#a855f7" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="sky" cx="0.5" cy="0.62" r="0.75">
      <stop offset="0" stop-color="#2a1065"/>
      <stop offset="0.55" stop-color="#140a33"/>
      <stop offset="1" stop-color="#05030f"/>
    </radialGradient>

    <linearGradient id="trail" gradientUnits="userSpaceOnUse"
                    x1="0" y1="0" x2="{W}" y2="0">
      <stop offset="0" stop-color="#38bdf8"/>
      <stop offset="0.5" stop-color="#a855f7"/>
      <stop offset="1" stop-color="#e879f9"/>
    </linearGradient>

    <filter id="soft" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="4.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>

    <filter id="halo" x="-45%" y="-45%" width="190%" height="190%">
      <feGaussianBlur stdDeviation="13" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="b"/></feMerge>
    </filter>

    <clipPath id="frame"><rect x="0" y="0" width="{W}" height="{H}" rx="18"/></clipPath>
  </defs>

  <g clip-path="url(#frame)">
    <rect width="{W}" height="{H}" fill="url(#sky)"/>

    <!-- neon floor -->
    <g>{floor_markup()}</g>

    <!-- falling binary -->
    <g>{rain_markup()}</g>

    <!-- horizon glow -->
    <ellipse cx="{W/2}" cy="{HORIZON}" rx="{W*0.44}" ry="52" fill="url(#horizonglow)"/>

    <!-- fireworks -->
    {burst_markup()}

    <!-- launch -->
    {launch_markup()}

    <!-- wordmark halo: revealed letter by letter in step with the typing, so
         un-typed glyphs never show through as ghosts -->
    <g filter="url(#halo)" fill="#7c3aed" opacity="0.5">
      <animate attributeName="opacity" values="0.3;0.62;0.3" dur="3.4s"
               begin="{type_end + 0.8:.2f}s" repeatCount="indefinite"/>
      {"".join(
          f'<use href="#g{i}" xlink:href="#g{i}" opacity="0">'
          f'<animate attributeName="opacity" from="0" to="1" dur="0.18s" '
          f'begin="{T_TYPE + i * TYPE_STEP:.3f}s" fill="freeze"/></use>'
          for i in range(len(letters)))}
    </g>

    <!-- orbiting rocket + smoke trail -->
    <g opacity="0">
      <animate attributeName="opacity" from="0" to="1" dur="0.7s"
               begin="{T_ORBIT:.2f}s" fill="freeze"/>
      <path d="{ORBIT}" fill="none" stroke="url(#trail)" stroke-width="7"
            stroke-linecap="round" opacity="0.5" filter="url(#soft)"
            stroke-dasharray="300 2000">
        <animate attributeName="stroke-dashoffset" from="2300" to="0"
                 dur="11s" begin="{T_ORBIT:.2f}s" repeatCount="indefinite"/>
      </path>
      <g>
        <animateMotion dur="11s" begin="{T_ORBIT:.2f}s" repeatCount="indefinite"
                       rotate="auto" path="{ORBIT}"/>
        <use href="#rocket" xlink:href="#rocket" transform="scale(1.05)"/>
      </g>
    </g>

    <!-- the wordmark -->
    <g>{letter_markup()}</g>

    <!-- typing caret -->
    <g opacity="0">
      <animate attributeName="opacity" values="0;1" dur="0.01s"
               begin="{T_TYPE - 0.12:.2f}s" fill="freeze"/>
      <animate attributeName="opacity" values="1;0" dur="0.3s"
               begin="{type_end + 1.1:.2f}s" fill="freeze"/>
      <rect y="{TITLE_CY - 52}" width="9" height="104" rx="4" fill="#67e8f9" x="{centres[0]:.0f}">
        <animate attributeName="x" values="{';'.join(caret_x)}"
                 dur="{TYPE_STEP * (len(TEXT) + 1):.2f}s" begin="{T_TYPE - 0.12:.2f}s"
                 calcMode="discrete" fill="freeze"/>
        <animate attributeName="opacity" values="1;1;0.1;1" keyTimes="0;0.45;0.5;1"
                 dur="0.9s" repeatCount="indefinite"/>
      </rect>
    </g>

    <!-- props -->
    {laptop_markup()}
    {trophy_markup()}
    {brackets_markup()}
  </g>
</svg>
'''

with open(OUT, "w") as fh:
    fh.write(svg)
print(f"wrote {OUT}  ({W}x{H}, {len(svg) / 1024:.1f} KB)")
