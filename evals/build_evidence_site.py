"""Build the public evidence page from the eval data.

WHY THIS EXISTS. The page states numbers to strangers. Those numbers live in
`evals/_metrics_history.json`, which is built from the verdict and answers files
themselves. This script joins the two and REFUSES TO BUILD if a claimed number
disagrees with its arm, so the published page cannot drift from the repo.

A finding may be arm-backed or doc-backed. Arm-backed findings name an `arm` and
are checked. Doc-backed findings (the judge audit, for instance, whose numbers
come from a human audit rather than an arm) name a `source_doc` instead and are
NOT auto-checked -- they still carry a population string, and the page says where
they came from.

The render is deterministic on purpose: no build timestamp, no "generated on"
line. `site/index.html` is committed, and a test compares the committed file
against a fresh render, which only works if the same inputs always produce the
same bytes.

Run: `.venv/Scripts/python.exe evals/build_evidence_site.py`
"""
from __future__ import annotations

import html as html_mod
import json
import shutil
from pathlib import Path

# How far a claimed number may sit from its arm before the build fails.
# Tight on purpose: this is a typo guard, not a rounding allowance.
ACCURACY_TOLERANCE = 0.0005


class DriftError(Exception):
    """A published claim disagrees with the data that is supposed to support it."""


# ------------------------------------------------------------------ loading --

def load_findings(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data["findings"]


def load_page(path: Path) -> dict:
    """The whole findings document: title, intro, findings, links."""
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_arms(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return {arm["arm"]: arm for arm in data["arms"]}


# --------------------------------------------------------------- verifying --

def verify_finding(finding: dict, arms: dict[str, dict]) -> None:
    """Raise DriftError unless the finding's claimed numbers match its arm."""
    arm_id = finding["arm"]
    arm = arms.get(arm_id)
    if arm is None:
        raise DriftError(
            f"finding {finding['id']!r} names arm {arm_id!r}, "
            f"which is not in the metrics history. Rebuild it with "
            f"`python evals/build_metrics_history.py` or fix the arm id."
        )

    claimed_n = finding.get("claimed_n")
    if claimed_n is not None and arm.get("n") != claimed_n:
        raise DriftError(
            f"finding {finding['id']!r} claims n={claimed_n} "
            f"but arm {arm_id!r} has n={arm.get('n')}"
        )

    claimed_acc = finding.get("claimed_accuracy")
    if claimed_acc is not None:
        actual = arm.get("accuracy_flat")
        if actual is None:
            raise DriftError(
                f"finding {finding['id']!r} claims an accuracy but arm "
                f"{arm_id!r} records none"
            )
        if abs(actual - claimed_acc) > ACCURACY_TOLERANCE:
            raise DriftError(
                f"finding {finding['id']!r} claims accuracy {claimed_acc} "
                f"but arm {arm_id!r} measures {actual}"
            )

    # Per-level figures are published on the page too, so they get the same
    # treatment as the flat number. The headline's level table is the most
    # quoted thing here and the easiest to mistype.
    for level, claimed in (finding.get("claimed_levels") or {}).items():
        by_level = arm.get("by_level") or {}
        row = by_level.get(level)
        if row is None:
            raise DriftError(
                f"finding {finding['id']!r} claims level {level!r} "
                f"but arm {arm_id!r} has no such level "
                f"(it has {sorted(by_level)})"
            )
        actual = row["correct"] / row["n"]
        if abs(actual - claimed) > ACCURACY_TOLERANCE:
            raise DriftError(
                f"finding {finding['id']!r} claims level {level!r} at {claimed} "
                f"but arm {arm_id!r} measures {actual}"
            )

    # A finding that compares two runs states two numbers, and both are
    # published, so both get checked. The reversal is the case that matters:
    # it quotes the real-rules arm and the scrambled-rules arm side by side.
    for companion in finding.get("companions") or []:
        verify_finding({**companion, "id": f"{finding['id']}/{companion['arm']}"}, arms)


# ----------------------------------------------------------------- render --

REPO = Path(__file__).resolve().parents[1]

# The brand assets the page uses. These are the PLUM ones under frontend/assets,
# the same pair the live demo serves. branding/ still holds the older garnet
# lockups; those are not current and must not be used here.
MARK_SVG = REPO / "frontend" / "assets" / "rulemancer-mark.svg"
WORDMARK_SVG = REPO / "frontend" / "assets" / "rulemancer-wordmark.svg"


def _esc(text) -> str:
    return html_mod.escape(str(text), quote=True)


def _wordmark(path: Path = WORDMARK_SVG) -> str:
    """The wordmark, inlined rather than linked.

    It is drawn with `fill="currentColor"`, and an <img> cannot inherit colour
    from the page that embeds it, so linking it would render it black on a dark
    background. Inlined, it takes `color` from CSS and stays legible in any
    theme. The markup is a repo asset, not user content, so it goes in raw on
    purpose; nothing from findings.json is ever inlined this way.
    """
    if not path.is_file():
        return '<img class="wordmark" src="assets/rulemancer-wordmark.svg" alt="Rulemancer">'
    svg = path.read_text(encoding="utf-8").strip()
    return svg.replace("<svg ", '<svg class="wordmark" ', 1)


def _paras(body) -> str:
    """Body prose is a string or a list of paragraphs. Both render the same."""
    chunks = body if isinstance(body, list) else [body]
    return "".join(f"\n        <p>{_esc(c)}</p>" for c in chunks)


def _table(spec: dict) -> str:
    head = "".join(f"<th scope=\"col\">{_esc(c)}</th>" for c in spec["columns"])
    rows = "".join(
        "<tr>"
        + "".join(
            f"<th scope=\"row\">{_esc(cell)}</th>" if i == 0 else f"<td>{_esc(cell)}</td>"
            for i, cell in enumerate(row)
        )
        + "</tr>"
        for row in spec["rows"]
    )
    caption = (
        f"\n            <caption>{_esc(spec['caption'])}</caption>"
        if spec.get("caption") else ""
    )
    note = (
        f"\n          <p class=\"note\">{_esc(spec['note'])}</p>"
        if spec.get("note") else ""
    )
    return f"""
        <div class="table-wrap">
          <table>{caption}
            <thead><tr>{head}</tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>{note}"""


def _quote(spec: dict) -> str:
    cite = (
        f"\n          <figcaption>{_esc(spec['attribution'])}</figcaption>"
        if spec.get("attribution") else ""
    )
    return f"""
        <figure class="quote">
          <blockquote><p>{_esc(spec['text'])}</p></blockquote>{cite}
        </figure>"""


def _points(items: list) -> str:
    lis = "".join(f"\n            <li>{_esc(i)}</li>" for i in items)
    return f"\n        <ul class=\"points\">{lis}\n        </ul>"


def _source_line(finding: dict) -> str:
    """Where the numbers came from. Arm ids first, then any doc that carries
    figures the arms do not (a human audit, for instance)."""
    bits = []
    arms = [finding["arm"]] if finding.get("arm") else []
    arms += [c["arm"] for c in finding.get("companions") or []]
    if arms:
        joined = " and ".join(f"<code>{_esc(a)}</code>" for a in arms)
        bits.append(f"arm {joined}" if len(arms) == 1 else f"arms {joined}")
    if finding.get("source_doc"):
        bits.append(f"<code>{_esc(finding['source_doc'])}</code>")
    return "Source: " + ", ".join(bits) if bits else "Source: see repo"


def _finding_section(finding: dict) -> str:
    fid = _esc(finding["id"])
    parts = [
        f"""
      <section class="finding" id="{fid}" aria-labelledby="{fid}-h">
        <h2 id="{fid}-h">{_esc(finding['headline'])}</h2>
        <p class="population"><span class="population-label">Measured over</span>
           {_esc(finding['population'])}</p>{_paras(finding['body'])}"""
    ]
    if finding.get("table"):
        parts.append(_table(finding["table"]))
    if finding.get("quote"):
        parts.append(_quote(finding["quote"]))
    if finding.get("points"):
        parts.append(_points(finding["points"]))
    if finding.get("aside"):
        parts.append(f"\n        <p class=\"aside\">{_esc(finding['aside'])}</p>")
    parts.append(f"""
        <p class="source">{_source_line(finding)}</p>
      </section>""")
    return "".join(parts)


def _try_it(spec: dict) -> str:
    """The public try-it card: a live URL and the shared access code.

    The code is deliberately publishable. It carries its own query cap, so the
    worst a scraper can do is exhaust it, and the honest framing (shared pool,
    may already be gone) is part of the copy rather than a surprise 402.
    """
    if not spec:
        return ""
    body = "".join(f"\n        <p>{_esc(p)}</p>" for p in spec.get("body", []))
    return f"""
      <section class="try-it" aria-labelledby="try-it-h">
        <h2 id="try-it-h">{_esc(spec['heading'])}</h2>
        <p class="try-it-line">
          <a class="try-it-url" href="{_esc(spec['url'])}">{_esc(spec['url'])}</a>
          <span class="try-it-code">access code <code>{_esc(spec['code'])}</code></span>
        </p>{body}
      </section>"""


def _contents(findings: list[dict]) -> str:
    items = "".join(
        f"\n          <li><a href=\"#{_esc(f['id'])}\">{_esc(f.get('nav', f['headline']))}</a></li>"
        for f in findings
    )
    return f"""
      <nav class="contents" aria-label="Findings">
        <h2 class="contents-h">What's on this page</h2>
        <ol>{items}
        </ol>
      </nav>"""


def render_page(findings: list[dict], arms: dict[str, dict], page: dict | None = None) -> str:
    """Verify every arm-backed claim, then emit the whole page as a string."""
    for f in findings:
        if f.get("arm"):
            verify_finding(f, arms)

    page = page or {}
    links = page.get("links", {})
    title = page.get("title", "Rulemancer, what was measured")
    tagline = page.get("tagline", "")
    intro = page.get("intro", [])
    closing = page.get("closing", [])

    sections = "".join(_finding_section(f) for f in findings)
    intro_html = "".join(f"\n        <p>{_esc(p)}</p>" for p in intro)
    closing_html = "".join(f"\n        <p>{_esc(p)}</p>" for p in closing)

    link_items = "".join(
        f"\n          <li><a href=\"{_esc(url)}\">{_esc(label)}</a></li>"
        for label, url in links.items()
    )
    link_html = (
        f"\n        <ul class=\"links\">{link_items}\n        </ul>" if link_items else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<meta name="description" content="{_esc(tagline)}">
<link rel="stylesheet" href="assets/tokens.css">
<link rel="stylesheet" href="assets/evidence.css">
<link rel="icon" href="assets/rulemancer-mark.svg">
</head>
<body data-surface="dark">
<a class="skip" href="#findings">Skip to the findings</a>
<main>
  <header class="hero">
    <div class="lockup">
      <img class="mark" src="assets/rulemancer-mark.svg" alt="" width="56" height="56">
      {_wordmark()}
    </div>
    <p class="tagline">{_esc(tagline)}</p>
  </header>

  <section class="intro">{intro_html}
  </section>
{_contents(findings)}
  <div id="findings">{sections}
  </div>
{_try_it(page.get("try_it", {}))}
  <footer>
    <h2>How this page is made</h2>{closing_html}{link_html}
  </footer>
</main>
</body>
</html>
"""


# -------------------------------------------------------------------- main --

def main(out_dir: Path) -> None:
    repo = REPO
    page = load_page(repo / "docs" / "evidence" / "findings.json")
    findings = page["findings"]
    arms = load_arms(repo / "evals" / "_metrics_history.json")
    html = render_page(findings, arms, page)

    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy(repo / "design-system" / "tokens.css", assets / "tokens.css")
    # The mark doubles as the favicon, exactly as the live demo uses it. The
    # wordmark is inlined by the renderer, so it is not copied.
    shutil.copy(MARK_SVG, assets / "rulemancer-mark.svg")
    for stale in ("rulemancer-lockup-red.svg", "rulemancer-favicon.svg"):
        (assets / stale).unlink(missing_ok=True)

    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"wrote {out_dir / 'index.html'} ({len(findings)} findings)")


if __name__ == "__main__":
    main(Path(__file__).resolve().parents[1] / "site")
