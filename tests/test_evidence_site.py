"""The evidence page publishes numbers, so the build refuses to publish a wrong one.

WHY: the whole project's credibility rests on numbers matching their data. A
hand-typed figure in an HTML template is exactly how a public page ends up
disagreeing with the repo it links to.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from evals.build_evidence_site import (
    DriftError,
    load_arms,
    load_findings,
    verify_finding,
)

REPO = Path(__file__).resolve().parents[1]
FINDINGS = REPO / "docs" / "evidence" / "findings.json"
METRICS = REPO / "evals" / "_metrics_history.json"


# ---------------------------------------------------------------- contract --

def test_findings_file_parses_and_is_non_empty():
    findings = load_findings(FINDINGS)
    assert len(findings) >= 6, "the page promises six findings"


def test_every_finding_declares_its_population():
    for f in load_findings(FINDINGS):
        assert f.get("population"), f"finding {f['id']} has no population string"
        assert f.get("headline"), f"finding {f['id']} has no headline"
        assert f.get("body"), f"finding {f['id']} has no body prose"


def test_every_finding_names_a_source():
    """Arm-backed or doc-backed, but never unattributed."""
    for f in load_findings(FINDINGS):
        assert f.get("arm") or f.get("source_doc"), (
            f"finding {f['id']} names neither an arm nor a source doc")


def test_arm_backed_findings_match_their_arm():
    arms = load_arms(METRICS)
    for f in load_findings(FINDINGS):
        if f.get("arm"):
            verify_finding(f, arms)  # raises DriftError on mismatch


def test_doc_backed_findings_point_at_a_real_doc():
    for f in load_findings(FINDINGS):
        doc = f.get("source_doc")
        if doc:
            assert (REPO / doc).exists(), f"finding {f['id']} cites missing {doc}"


def test_drift_is_detected():
    arms = {"fake_arm": {"arm": "fake_arm", "n": 100, "accuracy_flat": 0.80}}
    bad = {
        "id": "bogus",
        "headline": "x",
        "body": "y",
        "population": "z",
        "arm": "fake_arm",
        "claimed_accuracy": 0.95,
        "claimed_n": 100,
    }
    with pytest.raises(DriftError):
        verify_finding(bad, arms)


def test_missing_arm_is_an_error_not_a_silent_skip():
    bad = {
        "id": "bogus",
        "headline": "x",
        "body": "y",
        "population": "z",
        "arm": "no_such_arm",
        "claimed_accuracy": 0.5,
        "claimed_n": 1,
    }
    with pytest.raises(DriftError):
        verify_finding(bad, {})


def test_level_drift_is_detected():
    """A per-level figure is as publishable as the flat one, so it is checked too."""
    arms = {"a": {"arm": "a", "n": 10, "accuracy_flat": 0.5,
                  "by_level": {"3": {"correct": 5.0, "n": 10.0}}}}
    bad = {
        "id": "bogus", "headline": "x", "body": "y", "population": "z",
        "arm": "a", "claimed_levels": {"3": 0.90},
    }
    with pytest.raises(DriftError):
        verify_finding(bad, arms)


def test_unknown_claimed_level_is_an_error():
    arms = {"a": {"arm": "a", "n": 10, "accuracy_flat": 0.5,
                  "by_level": {"3": {"correct": 5.0, "n": 10.0}}}}
    bad = {
        "id": "bogus", "headline": "x", "body": "y", "population": "z",
        "arm": "a", "claimed_levels": {"7": 0.5},
    }
    with pytest.raises(DriftError):
        verify_finding(bad, arms)


# ------------------------------------------------------------------ render --

def test_render_includes_every_finding_headline():
    from evals.build_evidence_site import render_page

    findings = load_findings(FINDINGS)
    html = render_page(findings, load_arms(METRICS))
    for f in findings:
        assert f["headline"] in html, f"missing headline for {f['id']}"


def test_render_includes_every_population_line():
    """The population is the point of the page; it must survive rendering."""
    import html as html_mod

    from evals.build_evidence_site import render_page

    findings = load_findings(FINDINGS)
    html = render_page(findings, load_arms(METRICS))
    for f in findings:
        # Compare against the escaped form: populations are prose and may
        # contain apostrophes, which are escaped on the way into the page.
        wanted = html_mod.escape(f["population"], quote=True)[:60]
        assert wanted in html, f"missing population for {f['id']}"


def test_headlines_survive_escaping_unchanged():
    """The plan's headline test compares raw strings, so headlines stay plain.

    A headline containing an apostrophe or an ampersand would render correctly
    and still fail `test_render_includes_every_finding_headline`, which would
    look like a render bug rather than a copy choice. Say so here instead.
    """
    import html as html_mod

    for f in load_findings(FINDINGS):
        assert html_mod.escape(f["headline"], quote=True) == f["headline"], (
            f"headline for {f['id']} contains a character that HTML-escapes; "
            f"rewrite it without quotes, apostrophes or ampersands")


def test_render_escapes_content():
    from evals.build_evidence_site import render_page

    findings = [{
        "id": "x", "headline": "<script>alert(1)</script>",
        "body": "b", "population": "p", "source_doc": "d",
    }]
    html = render_page(findings, {})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_escapes_table_cells():
    """Tables take the same untrusted path as prose and must escape the same way."""
    from evals.build_evidence_site import render_page

    findings = [{
        "id": "x", "headline": "h", "body": "b", "population": "p",
        "source_doc": "d",
        "table": {"columns": ["<b>col</b>"], "rows": [["<i>cell</i>"]]},
    }]
    html = render_page(findings, {})
    assert "<b>col</b>" not in html
    assert "<i>cell</i>" not in html
    assert "&lt;i&gt;cell&lt;/i&gt;" in html


def test_page_never_states_the_headline_to_three_digits():
    from evals.build_evidence_site import render_page

    html = render_page(load_findings(FINDINGS), load_arms(METRICS))
    assert "85.88" not in html, "publish 'roughly 86%' with error bars instead"


def test_page_carries_no_em_dashes():
    """Jon's voice rule, enforced rather than remembered."""
    from evals.build_evidence_site import render_page

    html = render_page(load_findings(FINDINGS), load_arms(METRICS))
    assert "—" not in html, "em dashes are out per the voice rules"


def test_built_page_on_disk_matches_a_fresh_render():
    """site/index.html is committed, so a stale commit is a publishable mistake."""
    from evals.build_evidence_site import render_page

    from evals.build_evidence_site import load_page

    built = REPO / "site" / "index.html"
    if not built.exists():
        pytest.skip("site/index.html not generated yet")
    page = load_page(FINDINGS)
    fresh = render_page(page["findings"], load_arms(METRICS), page)
    assert built.read_text(encoding="utf-8") == fresh, (
        "site/index.html is out of date. Rebuild it with "
        "`.venv/Scripts/python.exe evals/build_evidence_site.py`")
