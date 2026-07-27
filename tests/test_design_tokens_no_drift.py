# Palette-drift guard (2026-07-27 incident). What happened: frontend/index.html
# carried an inline <style> block that redefined --plum-*, --accent, and the
# whole dark-surface token set at runtime. Both real stylesheets --
# design-system/tokens.css and frontend/colors_and_type.css -- still described
# the OLD garnet palette and still mapped --accent to garnet. The app only
# *looked* plum because the inline override always won the cascade. Someone
# reading either stylesheet to find "the brand colour" would have read garnet,
# built a new page in the wrong colour, and been correct about what the file
# said and wrong about what the app did.
#
# Fix: the plum ramp and the accent mapping now live in the stylesheets
# themselves (frontend/colors_and_type.css, which the app actually loads, and
# design-system/tokens.css, the design system's canonical file); the inline
# override was deleted. These tests exist to make sure that never quietly
# reverts -- if you're reading this because one of them failed, the fix is
# almost always to delete whatever inline color code you just added and put
# the token in the stylesheet instead, not to delete the test.

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO / "frontend" / "index.html"
FRONTEND_TOKENS = REPO / "frontend" / "colors_and_type.css"
DESIGN_SYSTEM_TOKENS = REPO / "design-system" / "tokens.css"

# Brand tokens/values that must be defined exactly once, in the stylesheets,
# and never redefined inline in a page. If a legitimate new page-local need
# for one of these ever comes up, it belongs in colors_and_type.css as a new
# semantic token, not as a per-page override -- that's the pattern that broke.
_BRAND_TOKEN_RE = re.compile(r"--(?:plum-\d{2,3}|accent(?:-\w+)?)\s*:")


def test_index_html_does_not_redefine_brand_tokens_inline():
    html = INDEX_HTML.read_text(encoding="utf-8")
    hits = _BRAND_TOKEN_RE.findall(html)
    assert not hits, (
        "frontend/index.html redefines brand color token(s) inline: "
        f"{hits}. This is exactly the 2026-07-27 palette-drift bug: an inline "
        "<style> override in this file once redefined --plum-* and --accent, "
        "which made the app render plum while both design-system/tokens.css "
        "and frontend/colors_and_type.css still described garnet -- nobody "
        "reading the stylesheets could tell what the app actually looked "
        "like. Brand tokens belong ONLY in frontend/colors_and_type.css "
        "(what this page loads) and design-system/tokens.css (the design "
        "system's canonical copy). Add or change a token there, not here."
    )


def _extract_root_and_dark_blocks(css_text: str) -> str:
    """Grab the ':root {...}' and '[data-surface=\"dark\"] {...}' blocks so the
    drift check only compares token *values*, not comments or unrelated rules
    (button hover styles, etc.) that legitimately differ between the two files).
    Anchored to line start (^) so a mention of the selector text inside a
    /* comment */ can't be mistaken for the real rule."""
    blocks = []
    for selector in (r":root", r'(?:\.surface-dark,\s*)?\[data-surface="dark"\]'):
        m = re.search(r"^" + selector + r"\s*\{([^}]*)\}", css_text, re.M)
        if m:
            blocks.append(m.group(1))
    return "\n".join(blocks)


_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def _token_values(css_block: str) -> dict:
    # Strip comments first -- this repo's comments document token names using
    # the literal "--token-name:" syntax (e.g. explaining --fg-on-garnet), and
    # that reads as a real declaration to a naive regex.
    css_block = _CSS_COMMENT_RE.sub("", css_block)
    return dict(re.findall(r"--([\w-]+)\s*:\s*([^;]+);", css_block))


# Only the color/palette tokens are required to match byte-for-byte between
# the two files. Typography, shadow, spacing etc. are allowed to diverge --
# they were never part of the plum/garnet incident and the two files have
# legitimately differed on them since before this fix.
_COLOR_TOKEN_PREFIXES = ("plum-", "accent", "bg-", "fg-", "border-", "sigil")


def _is_color_token(name: str) -> bool:
    return any(name.startswith(p) for p in _COLOR_TOKEN_PREFIXES)


def test_frontend_and_design_system_palettes_do_not_drift():
    # frontend/colors_and_type.css (what the app actually loads) and
    # design-system/tokens.css (the design system's canonical file) are two
    # separate files with no shared import or build step -- design-system/ is
    # never mounted as static content by the FastAPI app, so a real @import
    # isn't possible without a server change. That means nothing but this
    # test keeps them in sync. If this fails, one file was edited without the
    # other -- update whichever one is now wrong so both name the same brand
    # colour again.
    frontend_tokens = _token_values(
        _extract_root_and_dark_blocks(FRONTEND_TOKENS.read_text(encoding="utf-8"))
    )
    design_system_tokens = _token_values(
        _extract_root_and_dark_blocks(DESIGN_SYSTEM_TOKENS.read_text(encoding="utf-8"))
    )

    shared_keys = {
        k for k in (set(frontend_tokens) & set(design_system_tokens)) if _is_color_token(k)
    }
    assert shared_keys, "expected at least one shared color token between the two files -- extraction regex may be broken"

    def _normalize(value: str) -> str:
        # Value equality, not formatting equality -- "rgba(0,0,0,.62)" and
        # "rgba(0, 0, 0, .62)" are the same color and shouldn't fail the guard.
        return re.sub(r"\s+", "", value.strip())

    mismatches = {
        k: (frontend_tokens[k], design_system_tokens[k])
        for k in sorted(shared_keys)
        if _normalize(frontend_tokens[k]) != _normalize(design_system_tokens[k])
    }
    assert not mismatches, (
        "frontend/colors_and_type.css and design-system/tokens.css disagree on "
        f"shared token value(s): {mismatches!r}. This is the palette-drift bug "
        "from 2026-07-27 happening again in a smaller way -- the two "
        "stylesheets have quietly diverged. Reconcile them so both describe "
        "the same brand colours."
    )


def test_accent_resolves_to_plum_in_both_stylesheets():
    # Belt-and-suspenders: even if the two files agreed with each other, they
    # could both have drifted back to garnet together. Pin the actual brand
    # colour, not just cross-file consistency.
    for path in (FRONTEND_TOKENS, DESIGN_SYSTEM_TOKENS):
        css = path.read_text(encoding="utf-8")
        light_accent = re.search(r":root\s*\{[^}]*?--accent:\s*([^;]+);", css, re.S)
        dark_accent = re.search(
            r'\[data-surface="dark"\]\s*\{[^}]*?--accent:\s*([^;]+);', css, re.S
        )
        assert light_accent and "plum" in light_accent.group(1), (
            f"{path}: light-surface --accent does not resolve to the plum "
            "ramp -- the brand colour is plum/indigo, not garnet (or "
            "anything else)."
        )
        assert dark_accent and "plum" in dark_accent.group(1), (
            f"{path}: dark-surface --accent does not resolve to the plum "
            "ramp -- the brand colour is plum/indigo, not garnet (or "
            "anything else)."
        )
