#!/usr/bin/env python3
"""Rasterise the generated SVGs to PNG/GIF for the README.

Why this exists: the GitHub mobile app will not render these SVGs. Every one
came out as a broken-image link while the shields.io badges beside them were
fine, and switching from relative paths to absolute raw.githubusercontent.com
URLs changed nothing -- so it is not path resolution. Raster images render on
every GitHub surface, so the README points at these instead. The SVGs stay in
the repo as the editable source.

    title.svg       -> title.gif  (replays the whole intro)
    cards, heading,
    divider         -> .gif       (one LOOP period, loops seamlessly)
    hero-framed.svg -> .jpg       (a photo; its only motion was a scanline)

Frames are captured deterministically: the SVG is inlined into the page so
pauseAnimations() + setCurrentTime() can step the SMIL clock exactly, rather
than sampling wall-clock time and hoping.

The ambient GIFs start at SETTLED_T and run exactly one LOOP period. Because
every looping animation in make_art.py uses LOOP or a divisor of it, the last
frame flows back into the first -- verified by comparing the seam against the
median frame-to-frame delta.

Setup:
    pip install playwright imageio-ffmpeg
    # a Chromium and an ffmpeg binary must be reachable; see CHROME/ffmpeg below

Usage:
    python3 tools/make_art.py && python3 tools/rasterize.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent / "profile" / "assets"

SETTLED_T = 8.0          # past the end of every entrance animation
LOOP = 4.0               # must match make_art.LOOP

# Looping GIFs: (svg, CSS width, fps, start time, seconds, colours)
# These are captured over exactly one LOOP period starting from the settled
# frame, so the last frame flows back into the first with no visible jump.
LOOPS = [
    ("character-select.svg", 880, 8, SETTLED_T, LOOP, 64),
    ("divider.svg", 880, 10, SETTLED_T, LOOP, 48),
    ("P1card.svg", 180, 10, SETTLED_T, LOOP, 96),
    ("P2card.svg", 180, 10, SETTLED_T, LOOP, 96),
    ("P3card.svg", 180, 10, SETTLED_T, LOOP, 96),
    ("P4card.svg", 180, 10, SETTLED_T, LOOP, 96),
]

# The banner replays its whole intro rather than looping an ambient beat.
# 8s is two LOOP periods, so the ambient layer still lines up at the seam.
LOOPS_INTRO = [("title.svg", 880, 10, 0.0, 8.0, 112)]

# Stills. The hero is a photograph: JPEG at 1x beats both an upscaled PNG and
# a 128-colour GIF on size and quality, and its only motion was a scanline.
STILLS = [("hero-framed.svg", 880, 1, "jpeg")]


def find_chrome():
    for p in (os.environ.get("CHROME"),
              "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"):
        if p and os.path.exists(p):
            return p
    return None            # let Playwright use its own download


def find_ffmpeg():
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found: pip install imageio-ffmpeg")


def squeeze(src, dst, fmt):
    """Re-encode a captured frame: JPEG for photos, quantised PNG otherwise."""
    from PIL import Image
    im = Image.open(src)
    if fmt == "jpeg":
        im.convert("RGB").save(dst, "JPEG", quality=88, optimize=True,
                               progressive=True)
    else:
        im.convert("RGB").quantize(colors=256, method=Image.MEDIANCUT) \
          .save(dst, "PNG", optimize=True)


def main():
    from playwright.sync_api import sync_playwright

    frames = HERE / "_frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()

    todo = []
    chrome = find_chrome()
    with sync_playwright() as p:
        launch = {"args": ["--no-sandbox"]}
        if chrome:
            launch["executable_path"] = chrome
        browser = p.chromium.launch(**launch)

        def open_svg(name, width, scale=1):
            svg = (ASSETS / name).read_text()
            page = browser.new_page(
                viewport={"width": width, "height": 400},
                device_scale_factor=scale)
            page.set_content(
                '<body style="margin:0;background:#0d1117">'
                f'<div id="w" style="width:{width}px">{svg}</div></body>')
            # inline SVG lets us drive the SMIL clock by hand
            page.evaluate("""(w) => {
                const s = document.querySelector('#w svg');
                s.removeAttribute('width'); s.removeAttribute('height');
                s.style.width = w + 'px'; s.style.height = 'auto';
                s.style.display = 'block';
                s.pauseAnimations();
            }""", width)
            return page

        def shoot(page, t, path):
            page.evaluate("(t) => document.querySelector('#w svg')"
                          ".setCurrentTime(t)", t)
            page.evaluate("() => new Promise(r => requestAnimationFrame("
                          "() => requestAnimationFrame(r)))")
            page.locator("#w svg").screenshot(path=str(path))

        for name, width, scale, fmt in STILLS:
            page = open_svg(name, width, scale=scale)
            stem = pathlib.Path(name).stem
            raw = frames / f"{stem}.png"
            shoot(page, SETTLED_T, raw)
            page.close()
            out = ASSETS / f"{stem}.{'jpg' if fmt == 'jpeg' else 'png'}"
            squeeze(raw, out, fmt)
            print(f"  {out.name:24s} {out.stat().st_size / 1024:7.1f} KB")

        for name, width, fps, t0, secs, colors in LOOPS + LOOPS_INTRO:
            stem = pathlib.Path(name).stem
            shot_dir = frames / stem
            shot_dir.mkdir()
            page = open_svg(name, width)
            n = int(round(secs * fps))
            for i in range(n):
                shoot(page, t0 + i / fps, shot_dir / f"f{i:04d}.png")
            page.close()
            todo.append((stem, shot_dir, fps, n, colors))
        browser.close()

    ff = find_ffmpeg()
    for stem, shot_dir, fps, n, colors in todo:
        gif = ASSETS / f"{stem}.gif"
        pal = shot_dir / "pal.png"
        # one global palette is far smaller than per-frame palettes, and bayer
        # dithering compresses better than error diffusion on these gradients
        subprocess.run([ff, "-loglevel", "error", "-y", "-i", str(shot_dir / "f%04d.png"),
                        "-vf", f"palettegen=max_colors={colors}:stats_mode=diff",
                        str(pal)], check=True)
        subprocess.run([ff, "-loglevel", "error", "-y", "-framerate", str(fps),
                        "-i", str(shot_dir / "f%04d.png"), "-i", str(pal),
                        "-lavfi", "paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                        "-loop", "0", str(gif)], check=True)
        print(f"  {gif.name:24s} {gif.stat().st_size / 1024:7.1f} KB "
              f"({n} frames @ {fps}fps)")
    shutil.rmtree(frames)


if __name__ == "__main__":
    main()
