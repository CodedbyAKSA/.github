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

| File                   | What it is                                            |
| ---------------------- | ----------------------------------------------------- |
| `title.svg`            | Hero banner — HUD scene, wordmark types itself in     |
| `hero-framed.svg`      | `hero.png` inside a matching HUD frame                |
| `P1card.svg` … `P4card.svg` | Portraits in matching framed cards               |
| `character-select.svg` | Section heading                                       |
| `divider.svg`          | Neon rule above the footer                            |

All six share one deep-navy palette so the profile reads as a single piece
against GitHub's dark background. Each is self-contained: the wordmark is
baked to vector paths and bitmaps are inlined as data URIs, because GitHub
serves README images through a proxy that can't load web fonts or fetch
sibling files. Motion is SMIL, which does run in proxied `<img>` SVGs.

The palette and animation clock are constants at the top of the generator.

## Two rules for referencing these from the README

**Link them by absolute `raw.githubusercontent.com` URL, not a relative path.**
The profile README lives in `profile/`, but the GitHub mobile app presents it
as `CodedbyAKSA/README.md` and resolves relative paths against the repo root,
so `assets/title.svg` 404s there and every image renders as a broken link.
Absolute URLs resolve the same everywhere. (This is also why the shields.io
badges kept working when nothing else did — they were already absolute.)

**Keep the finished frame in the elements' own attributes.** Staged entrances
animate from `0s` with the delay encoded in `keyTimes`, rather than sitting at
`opacity="0"` waiting for a `begin` time. A renderer that ignores SMIL then
shows the completed artwork instead of a near-empty canvas. `tools/make_art.py`
has a `reveal()` helper that does this — use it for anything that fades in.

Once these are committed the profile renders automatically at
<https://github.com/CodedbyAKSA>.
