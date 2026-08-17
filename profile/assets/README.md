# Assets

Images referenced by [`profile/README.md`](../README.md).

`title.svg` is generated — run [`tools/make_title.py`](../../tools/make_title.py)
to rebuild it after changing the wordmark or its colours. Don't hand-edit it.
It is a self-contained animated SVG (neon grid, binary rain, rockets,
fireworks, laptop, trophy, and the wordmark typing itself in on load); the
animation clock lives in the constants at the top of that script.

The portraits are sized by **height**, not width, so that characters drawn on
differently-proportioned canvases still appear the same size. Any aspect ratio
works; the image is scaled to 210px tall.

| File       | Used for                                | Suggested size          |
| ---------- | --------------------------------------- | ----------------------- |
| `title.svg`| Animated hero banner (generated)        | 1200×430 (rendered full width) |
| `hero.png` | Banner under the wordmark               | ~1200px wide (rendered at 600px) |
| `P1.png`   | Karthik Janardhan — character portrait    | any ratio, ~1000px+ tall (rendered 210px tall) |
| `P2.png`   | Anushka Kotal — character portrait        | any ratio, ~1000px+ tall (rendered 210px tall) |
| `P3.png`   | Stash Lopes — character portrait          | any ratio, ~1000px+ tall (rendered 210px tall) |
| `P4.png`   | Ashwin Koonissery — character portrait    | any ratio, ~1000px+ tall (rendered 210px tall) |

Once these five files are committed, the org profile renders automatically at
<https://github.com/CodedbyAKSA>.
