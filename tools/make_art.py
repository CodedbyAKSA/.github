#!/usr/bin/env python3
"""Generate every animated SVG used by the org profile.

Emits into profile/assets/:
    title.svg            the hero banner -- HUD scene, wordmark types itself in
    hero-framed.svg      the team photo inside a matching HUD frame
    character-select.svg the section heading
    divider.svg          the neon rule above the footer

All four share one deep-navy palette so the profile reads as a single piece
against GitHub's dark background instead of three clashing backdrops.

Every file is self-contained: wordmark glyphs are converted to vector paths
and the team photo is inlined as a data URI, because GitHub serves README
images through a proxy that cannot load web fonts or fetch sibling files.
Motion is SMIL, which runs in proxied <img> SVGs.

Setup:
    pip install fonttools brotli pillow
    curl -sS -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
        "https://fonts.googleapis.com/css2?family=Fredoka+One" \
      | grep -o 'https://[^)]*woff2' | head -1 | xargs curl -sSL -o FredokaOne.woff2

Usage:
    python3 tools/make_art.py
"""
import base64
import io
import os
import random

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.misc.transform import Transform
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ASSETS = os.path.join(REPO, "profile", "assets")

TEXT = "CodedbyAKSA"

# --- shared palette (sampled from the reference clip) ------------------------
NAVY_CORE = "#1b2160"     # centre of the backdrop
NAVY_DEEP = "#070a22"     # edges
PANEL = "#0a0e2e"         # terminal / frame fill
GRID = "#3444a8"
STAR = "#93a7ff"
CYAN = "#67e8f9"
VIOLET = "#a78bfa"
MAGENTA = "#e879f9"
GOLD = "#fbbf24"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

rng = random.Random(11)

# Ambient (endlessly looping) motion all runs on this period, or a divisor
# of it. rasterize.py cuts the looping GIFs to exactly LOOP seconds, so a
# shared period is what makes them loop without a visible jump.
LOOP = 4.0


# --- font plumbing ----------------------------------------------------------
def load_font():
    for p in (os.path.join(HERE, "FredokaOne.woff2"), "FredokaOne.woff2"):
        if os.path.exists(p):
            return TTFont(p)
    raise SystemExit(
        "FredokaOne.woff2 not found -- see the download command in this file's "
        "docstring, and drop it next to this script."
    )


FONT = load_font()
CMAP = FONT.getBestCmap()
GLYPHS = FONT.getGlyphSet()
HMTX = FONT["hmtx"]
KERN = {}
if "kern" in FONT:
    for st in FONT["kern"].kernTables:
        KERN.update(st.kernTable)


def wordmark(text, target_w, cx, cy):
    """Lay `text` out, scaled to `target_w` and centred on (cx, cy).

    Returns (per-letter path strings, per-letter x centres, ink height).
    """
    records, x, prev = [], 0.0, None
    for ch in text:
        g = CMAP[ord(ch)]
        if prev is not None:
            x += KERN.get((prev, g), 0)
        rec = RecordingPen()
        GLYPHS[g].draw(TransformPen(rec, Transform(1, 0, 0, 1, x, 0)))
        records.append(rec)
        x += HMTX[g][0]
        prev = g

    bp = BoundsPen(None)
    for rec in records:
        rec.replay(bp)
    bx0, by0, bx1, by1 = bp.bounds

    s = target_w / (bx1 - bx0)
    ink_h = (by1 - by0) * s
    tx = cx - target_w / 2 - bx0 * s
    ty = cy + ink_h / 2 + by0 * s          # y flips, so by0 shifts the baseline
    place = Transform(s, 0, 0, -s, tx, ty)

    paths, centres = [], []
    for rec in records:
        pen = SVGPathPen(None, ntos=lambda v: f"{v:.1f}")
        rec.replay(TransformPen(pen, place))
        paths.append(pen.getCommands())
        b = BoundsPen(None)
        rec.replay(b)
        if b.bounds is None:            # whitespace has no outline
            centres.append(cx)
        else:
            lx0, _, lx1, _ = b.bounds
            centres.append((lx0 + lx1) / 2 * s + tx)
    return paths, centres, ink_h


def png_data_uri(path, target_h, colors=200):
    """Alpha-preserving data URI, downscaled and palette-quantised.

    Rendered at 2x the layout height so the card stays crisp, which still
    lands around 35 KB per portrait once quantised.
    """
    im = Image.open(path).convert("RGBA")
    w = round(im.width * target_h / im.height)
    im = im.resize((w, target_h), Image.LANCZOS)
    q = im.quantize(colors=colors, method=Image.FASTOCTREE)
    buf = io.BytesIO()
    q.save(buf, "PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}", (w, target_h)


def data_uri(path, quality=90, max_w=None):
    im = Image.open(path).convert("RGB")
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}", im.size


# --- shared scenery ---------------------------------------------------------
def backdrop(w, h, rx=16):
    return f'''
    <rect width="{w}" height="{h}" rx="{rx}" fill="url(#sky)"/>
    <g stroke="{GRID}" stroke-width="1" opacity="0.20">
      {''.join(f'<line x1="{x}" y1="0" x2="{x}" y2="{h}"/>' for x in range(0, w, 48))}
      {''.join(f'<line x1="0" y1="{y}" x2="{w}" y2="{y}"/>' for y in range(0, h, 48))}
    </g>'''


def starfield(w, h, n=80):
    out = []
    for _ in range(n):
        x, y = rng.uniform(6, w - 6), rng.uniform(6, h - 6)
        r = rng.choice([0.9, 1.2, 1.5, 2.0])
        d = rng.choice([LOOP / 2, LOOP])
        out.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{STAR}" opacity="0.5">'
            f'<animate attributeName="opacity" values="0.12;0.85;0.12" dur="{d:g}s" '
            f'begin="{-rng.uniform(0, d):.1f}s" repeatCount="indefinite"/></circle>'
        )
    return "".join(out)


def corner_ticks(w, h, m=14, L=26, col=CYAN):
    """HUD brackets in the four corners."""
    return f'''
    <g stroke="{col}" stroke-width="2" fill="none" opacity="0.75" stroke-linecap="round">
      <path d="M{m} {m + L} L{m} {m} L{m + L} {m}"/>
      <path d="M{w - m - L} {m} L{w - m} {m} L{w - m} {m + L}"/>
      <path d="M{m} {h - m - L} L{m} {h - m} L{m + L} {h - m}"/>
      <path d="M{w - m - L} {h - m} L{w - m} {h - m} L{w - m} {h - m - L}"/>
    </g>'''


def scanline(w, h, dur=LOOP, op=0.10):
    # parked off-canvas so a renderer that ignores SMIL shows nothing rather
    # than a stray band across the top
    return f'''
    <rect x="0" y="-60" width="{w}" height="46" fill="url(#scan)" opacity="{op}">
      <animateTransform attributeName="transform" type="translate"
                        values="0 0;0 {h + 80}" dur="{dur}s" repeatCount="indefinite"/>
    </rect>'''


# Reveal timeline. Every staged entrance runs as one animation starting at 0s
# whose delay is encoded in keyTimes, and the element's own attributes hold the
# FINAL state. So if SMIL never runs -- a renderer without animation support,
# reduced-motion, a thumbnailer -- the artwork still shows its finished frame
# instead of a mostly-empty canvas.
REVEAL_TOTAL = 7.0


def reveal(t0, d=0.4, attr="opacity", lo="0", hi="1", total=REVEAL_TOTAL):
    k1, k2 = t0 / total, (t0 + d) / total
    return (f'<animate attributeName="{attr}" values="{lo};{lo};{hi};{hi}" '
            f'keyTimes="0;{k1:.4f};{k2:.4f};1" dur="{total}s" begin="0s" fill="freeze"/>')


SHARED_DEFS = f'''
    <radialGradient id="sky" cx="0.5" cy="0.45" r="0.78">
      <stop offset="0" stop-color="{NAVY_CORE}"/>
      <stop offset="0.55" stop-color="#0f1440"/>
      <stop offset="1" stop-color="{NAVY_DEEP}"/>
    </radialGradient>
    <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>
      <stop offset="0.5" stop-color="{CYAN}" stop-opacity="0.9"/>
      <stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{CYAN}"/>
      <stop offset="0.5" stop-color="{VIOLET}"/>
      <stop offset="1" stop-color="{MAGENTA}"/>
    </linearGradient>
    <filter id="soft" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="4" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="halo" x="-45%" y="-45%" width="190%" height="190%">
      <feGaussianBlur stdDeviation="12" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="b"/></feMerge>
    </filter>'''


# ============================================================ hero banner ====
def build_title():
    W, H = 1200, 430
    TITLE_W, TITLE_CY = 850, 178
    DEPTH, DX, DY = 14, 1.25, 1.35

    T_LAUNCH, T_BURST = 0.0, 1.1
    T_TYPE, STEP = 1.4, 0.115
    T_ORBIT = 3.05
    paths, centres, ink_h = wordmark(TEXT, TITLE_W, W / 2, TITLE_CY)
    type_end = T_TYPE + STEP * len(TEXT)

    glyph_defs = "".join(f'<path id="g{i}" d="{d}"/>' for i, d in enumerate(paths))

    # -- wordmark, one letter at a time over a 3D extrusion
    letters = []
    for i in range(len(paths)):
        t0 = T_TYPE + i * STEP
        cx = centres[i]
        ext = "".join(
            f'<use href="#g{i}" xlink:href="#g{i}" '
            f'transform="translate({k * DX:.2f} {k * DY:.2f})"/>'
            for k in range(DEPTH, 0, -1)
        )
        kp = (t0 / REVEAL_TOTAL, (t0 + 0.17) / REVEAL_TOTAL, (t0 + 0.26) / REVEAL_TOTAL)
        letters.append(f'''
    <g opacity="1">
      {reveal(t0, 0.13)}
      <g transform="translate({cx:.1f} {TITLE_CY})">
        <animateTransform attributeName="transform" type="scale" values="1.4;1.4;0.94;1;1"
                          keyTimes="0;{kp[0]:.4f};{kp[1]:.4f};{kp[2]:.4f};1"
                          dur="{REVEAL_TOTAL}s" additive="sum" begin="0s" fill="freeze"/>
        <g transform="translate({-cx:.1f} {-TITLE_CY})">
          <g fill="url(#extrude)">{ext}</g>
          <use href="#g{i}" xlink:href="#g{i}" fill="url(#flow)"/>
        </g>
      </g>
    </g>''')

    halo = "".join(
        f'<use href="#g{i}" xlink:href="#g{i}" opacity="1">'
        f'{reveal(T_TYPE + i * STEP, 0.18)}</use>'
        for i in range(len(paths))
    )

    caret = [f"{c:.0f}" for c in centres] + [f"{centres[-1] + 48:.0f}"]

    # -- terminal panel, typing itself out
    code = ["const future = await build();",
            "if (ideas) ship(ideas);",
            "$ npm run launch"]
    lines = []
    for i, ln in enumerate(code):
        col = [CYAN, VIOLET, "#86efac"][i]
        begin = type_end + 0.2 + i * 0.75
        lines.append(f'''
      <clipPath id="tc{i}"><rect x="0" y="{i * 19}" height="18" width="205">
        {reveal(begin, 0.7, "width", "0", "205")}</rect></clipPath>
      <text x="0" y="{i * 19 + 13}" font-family="{MONO}" font-size="12.5" fill="{col}"
            clip-path="url(#tc{i})">{ln}</text>''')

    # -- rockets
    orbit = (f"M {W/2 - 330},252 a 330,58 0 1,0 660,0 a 330,58 0 1,0 -660,0")
    launches = []
    for x, delay, hue in ((470, 0.0, VIOLET), (742, 0.18, CYAN)):
        launches.append(f'''
    <g opacity="0">
      <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.08;0.72;1"
               dur="1.45s" begin="{T_LAUNCH + delay:.2f}s" fill="freeze"/>
      <path d="M{x},{H + 20} L{x},{H + 20}" stroke="{hue}" stroke-width="22"
            stroke-linecap="round" opacity="0.5" filter="url(#soft)">
        <animate attributeName="d" values="M{x},{H + 20} L{x},{H + 20};M{x},{H + 20} L{x},-40"
                 dur="1.45s" begin="{T_LAUNCH + delay:.2f}s" fill="freeze"/>
      </path>
      <g transform="translate({x} {H + 20})">
        <animateTransform attributeName="transform" type="translate"
                          values="{x} {H + 20};{x} -60" dur="1.45s"
                          begin="{T_LAUNCH + delay:.2f}s" fill="freeze"
                          calcMode="spline" keySplines="0.3 0 0.7 1"/>
        <g transform="rotate(-90)"><use href="#rocket" xlink:href="#rocket"
             transform="scale(1.5)"/></g>
      </g>
    </g>''')

    bursts = []
    for cx, cy, col, delay in ((330, 116, MAGENTA, 0.0), (880, 126, CYAN, 0.24)):
        spokes = "".join(
            f'<line x1="0" y1="0" x2="0" y2="-50" stroke="{col}" stroke-width="2.2" '
            f'stroke-linecap="round" transform="rotate({k * 22})"/>' for k in range(16))
        # one burst per 9s cycle: the visible part is the first ~1.4s, the rest
        # of the cycle is held at zero opacity so it re-fires rather than looping
        bursts.append(f'''
    <g transform="translate({cx} {cy})" opacity="0" filter="url(#soft)">
      <g>{spokes}</g>
      <animate attributeName="opacity" values="0;1;0.8;0;0" keyTimes="0;0.017;0.056;0.156;1"
               dur="9s" begin="{T_BURST + delay:.2f}s" repeatCount="indefinite"/>
      <animateTransform attributeName="transform" type="scale"
                        values="0.15;1.1;1.35;1.45;1.45" keyTimes="0;0.017;0.056;0.156;1"
                        dur="9s" begin="{T_BURST + delay:.2f}s" additive="sum"
                        repeatCount="indefinite"/>
    </g>''')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{TEXT}">
  <title>{TEXT}</title>
  <defs>
    {SHARED_DEFS}
    {glyph_defs}
    {ROCKET}
    <linearGradient id="flow" gradientUnits="userSpaceOnUse"
                    x1="0" y1="0" x2="660" y2="{H}" spreadMethod="repeat">
      <stop offset="0.00" stop-color="#7dd3fc"/>
      <stop offset="0.25" stop-color="#a5b4fc"/>
      <stop offset="0.50" stop-color="#e9d5ff"/>
      <stop offset="0.75" stop-color="#f0abfc"/>
      <stop offset="1.00" stop-color="#7dd3fc"/>
      <animateTransform attributeName="gradientTransform" type="translate"
                        from="0 0" to="660 0" dur="7s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="extrude" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#6d28d9"/>
      <stop offset="1" stop-color="#160f3d"/>
    </linearGradient>
    <linearGradient id="hull" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e0e7ff"/>
      <stop offset="0.5" stop-color="#818cf8"/>
      <stop offset="1" stop-color="#4338ca"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fde68a"/><stop offset="0.5" stop-color="{GOLD}"/>
      <stop offset="1" stop-color="#d97706"/>
    </linearGradient>
    <clipPath id="frame"><rect width="{W}" height="{H}" rx="16"/></clipPath>
  </defs>

  <g clip-path="url(#frame)">
    {backdrop(W, H)}
    <g>{starfield(W, H, 90)}</g>

    <!-- HUD chrome -->
    {corner_ticks(W, H)}
    <text x="46" y="40" font-family="{MONO}" font-size="13" fill="{CYAN}" opacity="0.85"
          letter-spacing="1.5">// CODE DEPLOYMENT // ONLINE</text>
    <text x="{W - 46}" y="40" text-anchor="end" font-family="{MONO}" font-size="13"
          fill="{MAGENTA}" opacity="0.85" letter-spacing="1.5">BUILD 01 READY</text>

    {''.join(bursts)}
    {''.join(launches)}

    <!-- wordmark halo, revealed in step with the typing -->
    <g filter="url(#halo)" fill="#6d28d9" opacity="0.55">
      <animate attributeName="opacity" values="0.34;0.68;0.34" dur="3.6s"
               begin="{type_end + 0.8:.2f}s" repeatCount="indefinite"/>
      {halo}
    </g>

    <!-- orbit + rocket -->
    <g opacity="1">
      {reveal(T_ORBIT, 0.7)}
      <path d="{orbit}" fill="none" stroke="url(#edge)" stroke-width="2" opacity="0.5"/>
      <path d="{orbit}" fill="none" stroke="url(#edge)" stroke-width="6" opacity="0.55"
            stroke-linecap="round" filter="url(#soft)" stroke-dasharray="220 1600">
        <animate attributeName="stroke-dashoffset" from="1820" to="0" dur="10s"
                 begin="{T_ORBIT:.2f}s" repeatCount="indefinite"/>
      </path>
      <g>
        <animateMotion dur="10s" begin="{T_ORBIT:.2f}s" repeatCount="indefinite"
                       rotate="auto" path="{orbit}"/>
        <use href="#rocket" xlink:href="#rocket" transform="scale(0.95)"/>
      </g>
    </g>

    <g>{''.join(letters)}</g>

    <!-- caret -->
    <g opacity="0">
      <animate attributeName="opacity" values="0;1" dur="0.01s" begin="{T_TYPE - 0.12:.2f}s" fill="freeze"/>
      <animate attributeName="opacity" values="1;0" dur="0.3s" begin="{type_end + 1.0:.2f}s" fill="freeze"/>
      <rect y="{TITLE_CY - 50}" width="9" height="100" rx="4" fill="{CYAN}" x="{centres[0]:.0f}">
        <animate attributeName="x" values="{';'.join(caret)}"
                 dur="{STEP * (len(TEXT) + 1):.2f}s" begin="{T_TYPE - 0.12:.2f}s"
                 calcMode="discrete" fill="freeze"/>
        <animate attributeName="opacity" values="1;1;0.1;1" keyTimes="0;0.45;0.5;1"
                 dur="0.9s" repeatCount="indefinite"/>
      </rect>
    </g>

    <text x="{W/2}" y="258" text-anchor="middle" font-family="{MONO}" font-size="12.5"
          fill="{CYAN}" letter-spacing="4.5" opacity="0.9">
      BUILD &#8226; CREATE &#8226; SHIP &#8226; WIN
      {reveal(T_ORBIT + 0.3, 0.8, "opacity", "0", "0.9")}
    </text>

    <!-- terminal -->
    <g transform="translate(34 306)" opacity="1">
      {reveal(type_end, 0.5)}
      <rect x="-12" y="-16" width="238" height="76" rx="8" fill="{PANEL}"
            stroke="{VIOLET}" stroke-width="1.5" opacity="0.95"/>
      <g>{''.join(lines)}</g>
    </g>

    {laptop(96, 108, 0.62, type_end + 0.15)}
    {laptop(1044, 344, 0.5, type_end + 0.35)}
    {trophy(1092, 104, 0.6, type_end + 0.25)}

    <!-- progress strip -->
    <g opacity="1">
      {reveal(type_end, 0.5)}
      <text x="34" y="396" font-family="{MONO}" font-size="11.5" fill="{CYAN}"
            opacity="0.8" letter-spacing="2.4">INITIALIZING CREATIVE ENGINE</text>
      <rect x="34" y="406" width="{W - 68}" height="3" rx="1.5" fill="{GRID}" opacity="0.5"/>
      <rect x="34" y="406" width="{W - 68}" height="3" rx="1.5" fill="url(#edge)">
        {reveal(type_end, 3.4, "width", "0", str(W - 68))}
      </rect>
    </g>

    {scanline(W, H)}
  </g>
</svg>
'''
    return "title.svg", svg


ROCKET = f'''
  <g id="rocket">
    <path d="M24 0 L4 -7 Q-9 -8 -11 0 Q-9 8 4 7 Z" fill="url(#hull)"/>
    <path d="M4 -7 L-5 -17 L-12 -5 Z" fill="#7c3aed"/>
    <path d="M4 7 L-5 17 L-12 5 Z" fill="#7c3aed"/>
    <circle cx="8" cy="0" r="3.7" fill="#0b1026"/>
    <circle cx="8" cy="0" r="2.3" fill="{CYAN}"/>
    <path d="M-11 -4 Q-28 0 -11 4 Z" fill="{MAGENTA}" opacity="0.95">
      <animate attributeName="opacity" values="0.95;0.4;0.95" dur="0.15s" repeatCount="indefinite"/>
    </path>
    <path d="M-11 -2.5 Q-37 0 -11 2.5 Z" fill="#a5f3fc" opacity="0.7">
      <animate attributeName="opacity" values="0.7;0.2;0.7" dur="0.1s" repeatCount="indefinite"/>
    </path>
  </g>'''


def laptop(x, y, s, begin):
    bars = "".join(
        f'<rect x="{-26 + (5 if i % 2 else 0)}" y="{-22 + i * 7}" height="2.8" rx="1.4" '
        f'width="{w0}" fill="{c}" opacity="0.9">'
        f'<animate attributeName="width" values="{w0};{w1};{w0}" dur="{2.0 + i * 0.4}s" '
        f'repeatCount="indefinite"/></rect>'
        for i, (w0, w1, c) in enumerate(
            [(30, 18, CYAN), (20, 34, VIOLET), (36, 22, "#a5f3fc"), (16, 28, MAGENTA)])
    )
    return f'''
  <g transform="translate({x} {y})" opacity="1">
    {reveal(begin, 0.6)}
    <g>
      <animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0"
                        dur="4.4s" repeatCount="indefinite" calcMode="spline"
                        keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>
      <g transform="scale({s})">
        <rect x="-32" y="-28" width="64" height="44" rx="4" fill="{PANEL}"
              stroke="{CYAN}" stroke-width="2.2"/>
        {bars}
        <path d="M-42 16 L42 16 L38 23 L-38 23 Z" fill="{PANEL}" stroke="{CYAN}"
              stroke-width="2" stroke-linejoin="round"/>
      </g>
    </g>
  </g>'''


def trophy(x, y, s, begin):
    sparks = "".join(
        f'<path d="M{dx} {dy - r} L{dx + r*0.34} {dy - r*0.34} L{dx + r} {dy} '
        f'L{dx + r*0.34} {dy + r*0.34} L{dx} {dy + r} L{dx - r*0.34} {dy + r*0.34} '
        f'L{dx - r} {dy} L{dx - r*0.34} {dy - r*0.34} Z" fill="#fde68a">'
        f'<animate attributeName="opacity" values="0.15;1;0.15" dur="{d}s" '
        f'repeatCount="indefinite"/></path>'
        for dx, dy, r, d in ((-44, -30, 4.2, 1.7), (42, -22, 3.4, 2.2), (40, 24, 3.8, 1.9))
    )
    return f'''
  <g transform="translate({x} {y})" opacity="1">
    {reveal(begin, 0.6)}
    <g>
      <animateTransform attributeName="transform" type="translate" values="0 0;0 -6;0 0"
                        dur="3.8s" repeatCount="indefinite" calcMode="spline"
                        keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>
      <g transform="scale({s})">
        <path d="M-28 -34 L28 -34 L25 -8 Q20 11 0 14 Q-20 11 -25 -8 Z" fill="url(#gold)"
              stroke="#b45309" stroke-width="2"/>
        <path d="M-28 -28 Q-46 -28 -44 -12 Q-42 2 -26 2" fill="none" stroke="url(#gold)"
              stroke-width="5" stroke-linecap="round"/>
        <path d="M28 -28 Q46 -28 44 -12 Q42 2 26 2" fill="none" stroke="url(#gold)"
              stroke-width="5" stroke-linecap="round"/>
        <rect x="-5.5" y="13" width="11" height="13" fill="url(#gold)"/>
        <path d="M-20 26 L20 26 L24 37 L-24 37 Z" fill="url(#gold)" stroke="#b45309"
              stroke-width="2" stroke-linejoin="round"/>
        <path d="M0 -26 L4.9 -16.5 L15.5 -15 L7.8 -7.5 L9.6 3 L0 -2 L-9.6 3 L-7.8 -7.5
                 L-15.5 -15 L-4.9 -16.5 Z" fill="#fffbeb" opacity="0.92"/>
        {sparks}
      </g>
    </g>
  </g>'''


# ============================================================ framed hero ====
def build_hero():
    uri, (iw, ih) = data_uri(os.path.join(ASSETS, "hero.png"), quality=84)
    PAD, TOP = 24, 52
    W, H = iw + PAD * 2, ih + PAD + TOP
    px, py = PAD, TOP

    dots = "".join(
        f'<circle cx="{28 + i * 15}" cy="26" r="4.5" fill="{c}" opacity="0.85"/>'
        for i, c in enumerate([MAGENTA, GOLD, "#4ade80"]))

    br = 22   # corner bracket length over the photo
    brackets = "".join(f'<path d="{d}"/>' for d in (
        f"M{px} {py + br} L{px} {py} L{px + br} {py}",
        f"M{px + iw - br} {py} L{px + iw} {py} L{px + iw} {py + br}",
        f"M{px} {py + ih - br} L{px} {py + ih} L{px + br} {py + ih}",
        f"M{px + iw - br} {py + ih} L{px + iw} {py + ih} L{px + iw} {py + ih - br}",
    ))

    return "hero-framed.svg", f'''<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}"
     width="{W}" height="{H}" role="img" aria-label="The CodedbyAKSA team">
  <title>The CodedbyAKSA team</title>
  <defs>
    {SHARED_DEFS}
    <clipPath id="shot"><rect x="{px}" y="{py}" width="{iw}" height="{ih}" rx="7"/></clipPath>
    <radialGradient id="vig" cx="0.5" cy="0.5" r="0.72">
      <stop offset="0.55" stop-color="{NAVY_DEEP}" stop-opacity="0"/>
      <stop offset="1" stop-color="{NAVY_DEEP}" stop-opacity="0.62"/>
    </radialGradient>
    <!-- cool the photo toward the page palette so it stops reading as a white block -->
    <filter id="grade">
      <feComponentTransfer>
        <feFuncR type="linear" slope="0.82" intercept="0.01"/>
        <feFuncG type="linear" slope="0.85" intercept="0.02"/>
        <feFuncB type="linear" slope="0.96" intercept="0.06"/>
      </feComponentTransfer>
      <feColorMatrix type="saturate" values="0.92"/>
    </filter>
  </defs>

  <rect width="{W}" height="{H}" rx="14" fill="{PANEL}"/>
  {backdrop(W, H, 14)}
  <rect width="{W}" height="{H}" rx="14" fill="none" stroke="url(#edge)" stroke-width="2"
        opacity="0.75">
    <animate attributeName="opacity" values="0.45;0.95;0.45" dur="{LOOP}s" repeatCount="indefinite"/>
  </rect>

  {dots}
  <text x="{W - 24}" y="31" text-anchor="end" font-family="{MONO}" font-size="12"
        fill="{CYAN}" opacity="0.8" letter-spacing="2">// TEAM ROSTER &#183; 04 MEMBERS</text>

  <g clip-path="url(#shot)">
    <image href="{uri}" xlink:href="{uri}" x="{px}" y="{py}" width="{iw}" height="{ih}"
           filter="url(#grade)" preserveAspectRatio="xMidYMid slice"/>
    <rect x="{px}" y="{py}" width="{iw}" height="{ih}" fill="url(#vig)"/>
    <rect x="{px}" y="{py}" width="{iw}" height="30" fill="url(#scan)" opacity="0.14">
      <animateTransform attributeName="transform" type="translate"
                        values="0 -40;0 {ih + 40}" dur="{LOOP}s" repeatCount="indefinite"/>
    </rect>
  </g>

  <g stroke="{CYAN}" stroke-width="2.5" fill="none" stroke-linecap="round" opacity="0.9">
    {brackets}
  </g>
</svg>
'''


# ================================================= section heading + rule ====
def build_header():
    W, H = 900, 116
    label = "CHARACTER SELECT"
    paths, centres, _ = wordmark(label, 470, W / 2, H / 2 + 2)
    glyphs = "".join(f'<path d="{d}"/>' for d in paths)

    return "character-select.svg", f'''<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}"
     width="{W}" height="{H}" role="img" aria-label="{label}">
  <title>{label}</title>
  <defs>
    {SHARED_DEFS}
    <linearGradient id="hg" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="420" y2="0"
                    spreadMethod="repeat">
      <stop offset="0" stop-color="{CYAN}"/><stop offset="0.5" stop-color="{VIOLET}"/>
      <stop offset="1" stop-color="{CYAN}"/>
      <animateTransform attributeName="gradientTransform" type="translate" from="0 0"
                        to="420 0" dur="{LOOP}s" repeatCount="indefinite"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" rx="14" fill="url(#sky)"/>
  <rect width="{W}" height="{H}" rx="14" fill="none" stroke="url(#edge)" stroke-width="1.5"
        opacity="0.5"/>
  <g>{starfield(W, H, 26)}</g>

  <g fill="#4c1d95" filter="url(#halo)" opacity="0.5">{glyphs}
    <animate attributeName="opacity" values="0.3;0.62;0.3" dur="3.6s" repeatCount="indefinite"/>
  </g>
  <g fill="url(#hg)">{glyphs}</g>

  <g stroke="{CYAN}" stroke-width="3" fill="none" stroke-linecap="round" opacity="0.85">
    <path d="M{W/2 - 268} {H/2 - 18} L{W/2 - 282} {H/2} L{W/2 - 268} {H/2 + 18}">
      <animateTransform attributeName="transform" type="translate" values="0 0;-10 0;0 0"
                        dur="{LOOP / 2}s" repeatCount="indefinite"/>
    </path>
    <path d="M{W/2 + 268} {H/2 - 18} L{W/2 + 282} {H/2} L{W/2 + 268} {H/2 + 18}">
      <animateTransform attributeName="transform" type="translate" values="0 0;10 0;0 0"
                        dur="{LOOP / 2}s" repeatCount="indefinite"/>
    </path>
  </g>
  {scanline(W, H, LOOP, 0.12)}
</svg>
'''


def build_divider():
    W, H = 900, 26
    return "divider.svg", f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"
     width="{W}" height="{H}" role="img" aria-label="">
  <defs>
    {SHARED_DEFS}
    <linearGradient id="dl" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>
      <stop offset="0.5" stop-color="{VIOLET}" stop-opacity="0.9"/>
      <stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect x="0" y="{H/2 - 1}" width="{W}" height="2" fill="url(#dl)"/>
  <circle cy="{H/2}" r="4" fill="{CYAN}" filter="url(#soft)" cx="0">
    <animate attributeName="cx" values="60;{W - 60};60" dur="{LOOP}s" repeatCount="indefinite"
             calcMode="spline" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>
  </circle>
</svg>
'''


# ========================================================= character cards ===
CARD_W, CARD_H, CARD_PAD = 230, 270, 15
MEMBERS = ["Karthik Janardhan", "Anushka Kotal", "Stash Lopes", "Ashwin Koonissery"]


def build_cards():
    """One framed card per portrait.

    The portrait is fitted by height, so a source drawn on a wider canvas
    (P3 is 1142x1377 against 1024x1536 for the rest) still shows the
    character at the same size as the others.
    """
    out = []
    inner_h = CARD_H - CARD_PAD * 2
    for i, name in enumerate(MEMBERS, start=1):
        uri, (w2, _) = png_data_uri(
            os.path.join(ASSETS, f"P{i}.png"), inner_h * 2)
        w = w2 / 2
        x = (CARD_W - w) / 2
        out.append((f"P{i}card.svg", f'''<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {CARD_W} {CARD_H}"
     width="{CARD_W}" height="{CARD_H}" role="img" aria-label="{name}">
  <title>{name}</title>
  <defs>
    {SHARED_DEFS}
    <clipPath id="card"><rect width="{CARD_W}" height="{CARD_H}" rx="14"/></clipPath>
    <radialGradient id="pad" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{VIOLET}" stop-opacity="0.55"/>
      <stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <g clip-path="url(#card)">
    {backdrop(CARD_W, CARD_H, 14)}
    <g>{starfield(CARD_W, CARD_H, 16)}</g>
    <ellipse cx="{CARD_W/2}" cy="{CARD_H - CARD_PAD - 6}" rx="{w * 0.46:.0f}" ry="11"
             fill="url(#pad)"/>
    <g>
      <animateTransform attributeName="transform" type="translate" values="0 0;0 -6;0 0"
                        dur="{LOOP}s" repeatCount="indefinite" calcMode="spline"
                        keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>
      <image href="{uri}" xlink:href="{uri}" x="{x:.1f}" y="{CARD_PAD}"
             width="{w:.1f}" height="{inner_h}"/>
    </g>
    {scanline(CARD_W, CARD_H, LOOP, 0.10)}
    {corner_ticks(CARD_W, CARD_H, 9, 16)}
  </g>
  <rect width="{CARD_W}" height="{CARD_H}" rx="14" fill="none" stroke="url(#edge)"
        stroke-width="1.8" opacity="0.7">
    <animate attributeName="opacity" values="0.4;0.9;0.4" dur="{LOOP}s"
             repeatCount="indefinite"/>
  </rect>
</svg>
'''))
    return out


if __name__ == "__main__":
    for name, svg in build_cards():
        with open(os.path.join(ASSETS, name), "w") as fh:
            fh.write(svg)
        print(f"  {name:24s} {len(svg) / 1024:7.1f} KB")
    for builder in (build_title, build_hero, build_header, build_divider):
        name, svg = builder()
        path = os.path.join(ASSETS, name)
        with open(path, "w") as fh:
            fh.write(svg)
        print(f"  {name:24s} {len(svg) / 1024:7.1f} KB")
