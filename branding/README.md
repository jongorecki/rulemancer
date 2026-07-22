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

| File | Use |
|---|---|
| `rulemancer-icon.svg` | Primary mark (detailed line tome). Self-contained vector, scales to any size. |
| `rulemancer-lockup-light.svg` / `.png` / `@2x.png` | Horizontal lockup on parchment. Wordmark + tagline are outlined paths — no font needed. |
| `rulemancer-lockup-red.svg` / `.png` / `@2x.png` | Inverted lockup on the garnet red field (cream wordmark). |
| `rulemancer-icon-512-light.png` / `-red.png` | Square app icon, detailed mark, parchment or garnet background. |
| `rulemancer-favicon.svg` | **Bold** simplified mark (solid garnet tome). Use at small sizes where the fine linework collapses. |
| `favicon-512/180/32/16.png` | Favicon / touch-icon sizes rendered from `rulemancer-favicon.svg` (transparent). |

**Rule of thumb:** use the detailed `rulemancer-icon.svg` at ~64px and larger; use
the bold `rulemancer-favicon.*` at 48px and below (browser tabs, small app icons).

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
