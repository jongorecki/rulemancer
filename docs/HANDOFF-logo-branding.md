# Handoff — Rulemancer logo & branding

You are picking up the **logo/branding** work for **Rulemancer**, a RAG agent
over the MTG Comprehensive Rules (product name; code package is `rulesagent`).
Rulemancer is a deliberate **sibling to Cardomancer**, Jon's self-built MTG
card-sorting machine. The logo must feel like part of that family.

Jon reviews every pass and iterates. Ask before assuming; he makes the calls.

## The Cardomancer brand (match this — it's the source of truth)

All under `D:\Card_Sorter\Scripts\`:
- **Logo:** `static/branding/cardomancer-logo.png` — horizontal lockup: a
  line-art icon (two cards + a vertical arcane sigil) on the left, an ornate
  serif wordmark "Cardomancer" on the right, a letter-spaced caps tagline
  ("TRADING CARD COLLECTION SYSTEM") under the wordmark. Thin refined strokes,
  rounded corners, small corner dots.
- **Fonts:** wordmark = **Citadel of Blackrose**
  (`static/branding/fonts/CitadelOfBlackrose.ttf`, 99KB — the actual
  hand-lettered face); fallback **Cormorant Garamond**. Body = **Inter**.
  Mono = **JetBrains Mono**.
- **Palette** (`static/tokens.css`, `.claude/worktrees/agent-a07a399362584c35a/plans/design-system/colors_and_type.css`):
  indigo primary `#383888` (wordmark), `#534AB7` (tagline), lavender `#E8E8F8`;
  **parchment** canvas `#F4EFE4` / `#FBF8F1`; ink text `#1B1A2E`; **amber**
  `#D4A537` (reserved for ritual/accent moments); deep panel `#1F1F4A`.

## Rulemancer design decisions (Jon's, locked so far)

- **Color scheme: deep red + parchment** (a rules/law-tome feel). Deep garnet
  ~`#7C2530`. Parchment is the shared bridge to Cardomancer; red is the distinct
  primary so the two apps feel related but different.
- **Composition: crystal ball IN FRONT of an open book.** Jon supplied two
  reference images (an open book with fanned, *pointed* pages; and a crystal
  ball on a small stand with a 4-point sparkle top-right). **Recreate an
  original version in our brand — do not trace stock art.**
- **Crystal ball:** opaque enough to **mask the book lines behind it** (book
  must not show through). Rose-tinted fill **distinct from the parchment bg**.
  **Amber sparkle in the ball's TOP-RIGHT quadrant** (not centered). **No sigil
  inside the ball** (removed). Clean linework like Cardomancer's.
- **Fill:** the ball and/or book need a fill color different from the parchment
  background (a light rose).
- **Tagline:** "ASK MORE · LEARN MORE · KNOW MORE · WIN MORE" with tight
  letter-spacing (an earlier "KNOW MORE - WIN MORE" was too spread out).
- **Wordmark:** "Rulemancer" in Citadel of Blackrose, deep red.
- **Layout:** horizontal lockup mirroring Cardomancer (icon left, wordmark
  right, tagline under the wordmark, thin divider line).

## Where it stands + the open problem

- Rendered so far with **Pillow** (`uv run --with pillow`), because at first no
  SVG renderer respected the custom font. Latest render:
  `<scratchpad>/rulemancer_logo2.png` (script `<scratchpad>/logo2.py`).
- **What's GOOD:** wordmark in the real Citadel face, deep-red-on-parchment
  palette, the "ASK/LEARN/KNOW/WIN" tagline, amber sparkle on the ball's
  top-right, rose fills.
- **THE BLOCKER:** the **open book still looks bad** — lumpy panels, not a clean
  fanned open book. Hand-tuned Pillow bezier control points won't converge to a
  crisp book.

## The unlock (do this)

**`cairosvg` now works** (`uv run --with cairosvg`), and so do `svglib` and
`resvg-py`. So build the **icon as real SVG** (precise open-book curves + crystal
ball + stand + amber sparkle, in red/rose/parchment), render it crisp to PNG (the
icon has no text, so any SVG renderer is fine), then **composite the wordmark +
tagline via Pillow** with the real Citadel `.ttf` (and Arial bold as an Inter
stand-in for the tagline, drawn char-by-char for letter-spacing; supersample then
LANCZOS-downsample for clean lines). Get the **book looking professional** — that
is the whole task right now.

Alternatively test whether cairosvg renders an SVG with the font embedded as a
base64 `@font-face` (would let the whole logo be one SVG).

## Deliverables once Jon approves the direction

1. Horizontal lockup (icon + wordmark + tagline).
2. Icon-only mark (favicon / app icon).
3. Dark-panel variant on Cardomancer's `#1F1F4A`.
4. Drop the final SVG into the repo as the real asset (the eventual Rulemancer
   web app will use Cardomancer's styling — same fonts/tokens, red primary).

## Gotchas

- Windows: prefix Python with `PYTHONIOENCODING=utf-8`.
- Scratchpad for temp files:
  `C:\Users\Jon\AppData\Local\Temp\claude\D--Job-hunt-mtg-rules-bot\<session>\scratchpad\`
  (existing: `logo.py`, `logo2.py`, `rulemancer_logo*.png`). New sessions get a
  new scratchpad path — check the system prompt.
- Read images with the Read tool to inspect your own renders before showing Jon
  (verify-by-rendering).
- The reference images are **inspiration**, not to be copied pixel-for-pixel.
