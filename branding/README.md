# Rulemancer branding

Logo and icon assets for **Rulemancer**, a RAG agent over the MTG Comprehensive
Rules. Designed as a deliberate sibling to **Cardomancer** — same construction and
line style (thin refined linework, rounded corners, corner dots, a vertical arcane
sigil, an offset depth layer, ~8° counterclockwise tilt), recolored to Rulemancer's
own garnet + parchment palette.

The mark is a **closed arcane tome** with a branching sigil on the cover (the amber
root resolving down through decision nodes — a nod to how rules resolve).

## Palette

| Token | Hex | Use |
|---|---|---|
| Garnet (primary) | `#7C2530` | Linework, wordmark, solid favicon fill |
| Parchment | `#F2EFEF` | Light background (cool near-neutral, tuned off the garnet hue) |
| Rose (page fill) | `#EAD8DB` | Tome cover fill (a low-saturation tint of the garnet) |
| Rose (depth) | `#D9BEC2` | Back cover / depth layer |
| Teal (accent) | `#309B8C` | Reserved accent — sigil root + the two bottom terminal nodes |

The whole palette is **garnet + rose + parchment with a teal accent**. The neutrals
(parchment + rose) are tuned as tints of the garnet hue rather than warm yellow/salmon,
so everything descends from the brand red. The **teal accent is the garnet's complement**
(≈172° vs ≈352°) — a textbook harmonious, high-contrast pairing that pops on both the
parchment and the red field. There is **no dark/navy panel** — the inverted variant sits
on the garnet red itself, with a parchment wordmark. (Cardomancer's `#1F1F4A` navy is
intentionally not used here.)

Wordmark/linework on the red field: parchment `#F2EFEF`.

## Assets

> **The garnet assets were removed on 2026-07-28.** The brand moved to plum
> (`#653C86`), and the old red lockups, icons and favicons were the only copies
> of the previous colourway still sitting in this folder. Keeping them around
> was an active hazard: they are the first thing a search for "lockup" turns up,
> and the evidence site shipped with a garnet lockup for exactly that reason.
> They remain in git history if a previous colourway is ever needed again.

| File | Use |
|---|---|
| `rulemancer-lockup-plum.svg` | Horizontal lockup on parchment, current colourway. Wordmark + tagline are outlined paths, so no font is needed. Used by the repo README. |
| `../frontend/assets/rulemancer-mark.svg` | The mark, plum. What the live app serves, and what the evidence site uses as its icon and favicon. |
| `../frontend/assets/rulemancer-wordmark.svg` | Wordmark alone, drawn with `fill="currentColor"` so it takes the colour of whatever embeds it. Inline it rather than linking it; an `<img>` cannot inherit `currentColor`. |

**No PNG or favicon variants currently exist in plum.** Rasterising needs
`cairosvg` (see `src/build_svg.py`), which is not installed here. Nothing in the
repo references a PNG logo any more, so this is a gap rather than a breakage: the
README and both sites are SVG-only.

**Plum values**, for regenerating anything from `src/`: ink `#653C86`, tagline
`#7C4E9E`, tome face `#E4D8EE`, tome edge `#CDB6DE`, parchment `#F2EFEF` and teal
`#309B8C` unchanged. The tagline is plum-500 rather than plum-400 so it holds
5.34:1 on parchment, above the 4.5:1 AA line; plum-400 would land at 3.72:1.

## Fonts

- **Wordmark:** Citadel of Blackrose (the Cardomancer display face). In the lockup
  SVGs the wordmark and tagline are **converted to outline paths**, so the files are
  self-contained and render identically without the font installed.
- **Body / mono** (for the eventual web app, matching Cardomancer): Inter, JetBrains Mono.

## Provenance

The tome icon is **original artwork** — built entirely from primitive geometry
(rounded rectangles, lines, circles, the sigil), no third-party vector or stock art.
No attribution is required. The only third-party asset is the Citadel of Blackrose
font, used to generate the outlined wordmark.
