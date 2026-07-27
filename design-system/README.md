# Rulemancer Design System

The visual foundation for **Rulemancer**, a Magic: The Gathering rules assistant.
It is a deliberate sibling to **Cardomancer** — same structure, fonts, spacing, and
component conventions. The brand accent is **plum/indigo**, with teal as the
secondary accent.

## Files
- `tokens.css` — **the design system's canonical file for color.** Raw palette
  (`--plum-*`, `--parchment-*`, `--ink-*`, `--teal-*`) plus the semantic mapping
  (`--accent`, `--bg-page`, etc.) for both the light default and the
  `[data-surface="dark"]` block, plus typography, spacing, radius, shadow, and
  motion tokens.
- `colors_and_type.css` — an older, still-garnet-colored copy used only by the
  `preview/` cards below (see "Palette history" — not part of the plum fix and
  not loaded by the running app).
- `preview/` — design-system cards (auto-register via first-line `@dsCard` markers):
  `colors-garnet`, `colors-neutrals`, `type`, `components-buttons`,
  `components-forms`, `brand-mark`. These still render the retired garnet
  palette because they import `colors_and_type.css`, not `tokens.css` — see
  "Palette history".
- `assets/` — `rulemancer-mark.svg` (tome icon), `rulemancer-logo.png` (lockup),
  `rulemancer-favicon.svg`.
- `fonts/CitadelOfBlackrose.ttf` — the display/wordmark face.

## Palette (raw axes)
- **Plum** (primary): `--plum-600 #653C86` on light surfaces, `--plum-400 #9469B4`
  on dark; full ramp `#F4EFF8 … #241334`.
- **Parchment** (neutral canvas): `--parchment-100 #F2EFEF`.
- **Ink** (text): `--ink-900 #241519`.
- **Teal** (secondary accent): `--teal-500 #309B8C`.
- Status greens/yellows/reds preserved for functional UI.
- **Garnet is retired.** It was the original primary axis; the app now runs on
  plum. `--fg-on-garnet` survives in the app stylesheets under its old name
  only because two live templates (`frontend/gate.html`,
  `src/rulesagent/api/main.py`'s inline gate page) still reference it — its
  value was never garnet-derived (a plain near-white for text on `--accent`),
  so the name is legacy, not the color.

## Palette history — read before touching color tokens

**2026-07-27 incident.** The app's real brand color was plum, but it only
rendered that way because `frontend/index.html` carried an inline `<style>`
override that redefined `--plum-*` and `--accent` at runtime, on top of the
stylesheet. Both `design-system/tokens.css` and `frontend/colors_and_type.css`
(the file the app actually loads) still defined the old garnet palette and
still mapped `--accent` to garnet. Someone who read either stylesheet to find
"the brand color" would have read garnet, correctly, and been wrong about what
the app rendered — and would have built a new page in the wrong color. That
already happened once; this section and the guard tests below exist so it
doesn't happen again.

**Fix:** the plum ramp and the accent mapping now live in
`frontend/colors_and_type.css` (what `index.html` and `gate.html` actually
load) and in `design-system/tokens.css` (this design system's canonical
file). The inline override in `index.html` was deleted. There is no build
step or static mount connecting the two CSS files — `design-system/` is never
served by the FastAPI app — so they can't literally share one definition
without a server change. Instead, `tests/test_design_tokens_no_drift.py`
parses both files and fails if their color tokens disagree, and separately
fails if `index.html` (or any future page) redefines a brand token inline.
Read that test's failure messages if it trips; they explain the rule instead
of just failing.

**What was deliberately left alone:** `design-system/colors_and_type.css`
(a third, older copy used only by the local `preview/` cards, never served by
the running app) still describes garnet, as do the preview pages themselves
(`colors-garnet.html`, etc.) and the `branding/` image assets (lockups, icons,
favicons — see the repo root `README.md`, which displays one at the top).
None of those were in scope for the 2026-07-27 fix; they're flagged here so
the next person doesn't assume the whole design system is plum just because
the app and `tokens.css` are. A handful of literal garnet-tinted values were
also kept on purpose because changing them would move rendered pixels:
`--bg-overlay` on the light surface (`rgba(73,21,28,0.6)`) and the
`--shadow-*` tints in both CSS files. They're cosmetically stale, not broken
references — nothing points at a token that no longer exists.

## Notes
- The neutrals are tuned as tints of the (now-retired) garnet hue in the
  still-garnet `colors_and_type.css`; `tokens.css` uses plum-tinted neutrals
  in its accent mapping instead. Teal is the accent's complement either way.
- Body = Inter, mono = JetBrains Mono, display/wordmark = Citadel of Blackrose.

Mirrors the "Rulemancer Design System" project in Claude Design (claude.ai/design).
