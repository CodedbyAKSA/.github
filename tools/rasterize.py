#!/usr/bin/env python3
"""Rasterise the generated SVGs to PNG/GIF for the README.

Why this exists: the GitHub mobile app will not render these SVGs. Every one
came out as a broken-image link while the shields.io badges beside them were
fine, and switching from relative paths to absolute raw.githubusercontent.com
URLs changed nothing -- so it is not path resolution. Raster images render on
every GitHub surface, so the README points at these instead. The SVGs stay in
the repo as the editable source.

    title.svg  -> title.gif   (animated, the intro replays on loop)
    everything else -> .png   (settled frame, 2x for sharpness)

Frames are captured deterministically: the SVG is inlined into the page so
pauseAnimations() + setCurrentTime() can step the SMIL clock exactly, rather
than sampling wall-clock time and hoping.

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

# Settled-state stills: (svg, CSS width, device scale, format)
# The hero is a photograph, so JPEG at 1x beats an upscaled PNG on both size
# and quality -- the source photo is only 704px wide. Everything else is flat
# colour and line work, which palette-quantised PNG handles well.
STILLS = [
    ("hero-framed.svg", 880, 1, "jpeg"),
    ("character-select.svg", 880, 2, "png"),
    ("divider.svg", 880, 2, "png"),
    ("P1card.svg", 230, 2, "png"),
    ("P2card.svg", 230, 2, "png"),
    ("P3card.svg", 230, 2, "png"),
    ("P4card.svg", 230, 2, "png"),
]
SETTLED_T = 8.0          # past the end of every entrance animation

GIF_SRC = "title.svg"
GIF_W = 880
GIF_FPS = 12
GIF_SECONDS = 7.0        # one full intro: launch, fireworks, typing, orbit


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

        page = open_svg(GIF_SRC, GIF_W)
        n = int(GIF_SECONDS * GIF_FPS)
        for i in range(n):
            shoot(page, i / GIF_FPS, frames / f"f{i:04d}.png")
        page.close()
        browser.close()

    ff = find_ffmpeg()
    gif = ASSETS / (pathlib.Path(GIF_SRC).stem + ".gif")
    pal = frames / "pal.png"
    # a single global palette keeps the file far smaller than per-frame palettes,
    # and bayer dithering compresses better than error-diffusion on gradients
    subprocess.run([ff, "-loglevel", "error", "-y", "-i", str(frames / "f%04d.png"),
                    "-vf", "palettegen=max_colors=128:stats_mode=diff",
                    str(pal)], check=True)
    subprocess.run([ff, "-loglevel", "error", "-y", "-framerate", str(GIF_FPS),
                    "-i", str(frames / "f%04d.png"), "-i", str(pal),
                    "-lavfi", "paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                    "-loop", "0", str(gif)], check=True)
    shutil.rmtree(frames)
    print(f"  {gif.name:24s} {gif.stat().st_size / 1024:7.1f} KB "
          f"({n} frames @ {GIF_FPS}fps)")


if __name__ == "__main__":
    main()
