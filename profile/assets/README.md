# Assets

Everything the org profile renders. **The `.svg` files here are generated** —
run [`tools/make_art.py`](../../tools/make_art.py) to rebuild them all, and
don't hand-edit them.

## Source images (edit these)

| File       | Feeds into        | Notes                                       |
| ---------- | ----------------- | ------------------------------------------- |
| `hero.png` | `hero-framed.svg` | Team photo. Any size; ~1200px wide is plenty. |
| `P1.png`   | `P1card.svg`      | Karthik Janardhan — character portrait       |
| `P2.png`   | `P2card.svg`      | Anushka Kotal — character portrait           |
| `P3.png`   | `P3card.svg`      | Stash Lopes — character portrait             |
| `P4.png`   | `P4card.svg`      | Ashwin Koonissery — character portrait       |

Portraits should have a transparent background. **Any aspect ratio works** —
each one is fitted by height inside its card, so a portrait drawn on a wider
canvas still shows the character at the same size as the others. (`P3.png` is
1142×1377 where the rest are 1024×1536; sizing by width is what used to make
Stash render 20% smaller than everyone else.)

Replace a source image, re-run the generator, and commit both.

## Generated (do not edit)

Rebuilding is two stages:

```sh
python3 tools/make_art.py    # sources -> .svg
python3 tools/rasterize.py   # .svg    -> .gif / .png / .jpg
```

| Stage 1 — SVG          | Stage 2 — what the README uses | What it is                     |
| ---------------------- | ------------------------------ | ------------------------------ |
| `title.svg`            | `title.gif`                    | Hero banner, wordmark types in |
| `hero-framed.svg`      | `hero-framed.jpg`              | Team photo in a HUD frame      |
| `P1card.svg` … `P4card.svg` | `P1card.png` … `P4card.png` | Portraits in framed cards   |
| `character-select.svg` | `character-select.png`         | Section heading                |
| `divider.svg`          | `divider.png`                  | Neon rule above the footer     |

All of it shares one deep-navy palette so the profile reads as a single piece
against GitHub's dark background. The palette and the animation clock are
constants at the top of `make_art.py`.

## The README must reference the raster files, not the SVGs

**The GitHub mobile app will not render these SVGs.** Every one showed up as a
broken-image link while the shields.io badges beside them rendered fine, and
switching from relative paths to absolute `raw.githubusercontent.com` URLs
changed nothing — so it is not path resolution. The app also surfaced a
"Something went wrong" error on the page. `rasterize.py` exists to sidestep the
whole question: GIF, PNG and JPEG render on every GitHub surface.

So the SVGs are the editable source and never appear in the README. If you add
new art, rasterise it and link the raster.

Two supporting details worth keeping:

- **Absolute URLs.** Harmless, and removes any doubt about how a client
  resolves a path relative to `profile/`.
- **The SVGs degrade to their finished frame.** Staged entrances animate from
  `0s` with the delay encoded in `keyTimes` instead of sitting at
  `opacity="0"` waiting for a `begin` time, so a renderer that ignores SMIL
  still shows completed artwork. `make_art.py` has a `reveal()` helper for
  this — use it for anything that fades in. It is also what lets
  `rasterize.py` capture a correct still by seeking the SMIL clock.

Once these are committed the profile renders automatically at
<https://github.com/CodedbyAKSA>.
