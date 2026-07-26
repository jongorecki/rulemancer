# Plan — frontend cache-busting (micro-slice)

## Why

After commits 682dded/b50af2a landed, Jon's browser kept serving a cached
pre-fix `index.html`, so a fixed bug still reproduced on his screen. A stale
page silently masking an upgrade is exactly the failure mode to close before
anyone else runs this.

## What

1. **`run.py`:** serve `index.html` (the `/` route and any explicit
   `/index.html` hit) with `Cache-Control: no-cache`. `no-cache` means
   "revalidate before using" — the browser may keep a copy but must check
   with the server first, so a changed file is always picked up on plain
   refresh. Static *assets* keep default caching.
2. **`frontend/index.html`:** append a version query-string to the asset
   references it pulls in (`colors_and_type.css?v=<n>`, the font URL inside
   the CSS stays as-is — it's referenced by the CSS, which itself gets the
   `?v=`). Bump `<n>` when an asset changes. Since index.html always
   revalidates (step 1), a bumped `?v=` propagates immediately.

## Contract / interface

- No API change. No behavior change beyond HTTP caching headers.
- The entry point revalidates; everything else is cache-friendly.

## Edge cases

- `StaticFiles` serves the whole frontend dir; the header only needs to hit
  the HTML entry point. If run.py currently mounts everything under one
  `StaticFiles`, add a tiny explicit route for `/` that sets the header and
  falls through to the file.

## Verification

- `curl -sI http://127.0.0.1:8000/` shows `Cache-Control: no-cache`.
- `curl -sI` on a CSS asset does NOT show it.
- Browser check: edit a visible string in index.html, plain-refresh (not
  hard-refresh) the page, see the change.
