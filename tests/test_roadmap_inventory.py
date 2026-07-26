"""The roadmap inventory has to keep being true, not just start true.

Every status in `build_metrics_history.ROADMAP` was inferred by hand from commits
and code paths. Those references rot: a file moves, a commit is rewritten, a doc
is renamed, and a status that used to be earned quietly becomes an assertion.
The dashboard re-checks each reference at build time and renders a failure; these
tests make the same check fail the suite, so it is caught before anyone reads it.

They also enforce the two rules that keep the page honest under edit: every
"measured" claim cites the file that measured it, and no plan/spec doc may be
silently dropped from the inventory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "evals"))

import build_metrics_history as bmh  # noqa: E402

ROADMAP = bmh.ROADMAP
COST_KINDS = {"api_questions", "api_stated", "zero", "subscription", "hosting",
              "spent", "unknown"}
STATUSES = {"shipped", "partial", "open", "design-only", "cut", "superseded", "unknown"}
BASES = {"measured", "predicted", "unknown"}


def test_ids_are_unique():
    ids = [it["id"] for it in ROADMAP]
    assert len(ids) == len(set(ids)), "duplicate roadmap ids"


@pytest.mark.parametrize("item", ROADMAP, ids=lambda i: i["id"])
def test_item_shape(item):
    assert item["status"] in STATUSES, item["status"]
    assert item.get("one_line"), "every item needs a one-line description"
    assert item["cost"]["kind"] in COST_KINDS, item["cost"]["kind"]
    assert item["metric"]["basis"] in BASES, item["metric"]["basis"]
    assert item.get("evidence"), "a status with no evidence is a guess"


@pytest.mark.parametrize("item", ROADMAP, ids=lambda i: i["id"])
def test_measured_claims_cite_their_source(item):
    """A direction called 'measured' must name the file that measured it."""
    m = item["metric"]
    if m["basis"] == "measured":
        assert m.get("cite"), f"{item['id']}: measured with no citation"


@pytest.mark.parametrize("item", ROADMAP, ids=lambda i: i["id"])
def test_dependencies_resolve(item):
    known = {i["id"] for i in ROADMAP}
    for dep in item.get("deps", []):
        assert dep in known, f"{item['id']} depends on unknown item {dep}"


@pytest.mark.parametrize("item", ROADMAP, ids=lambda i: i["id"])
def test_referenced_paths_exist(item):
    for e in item["evidence"]:
        if e["kind"] in ("path", "doc"):
            assert (REPO / e["ref"]).exists(), f"{item['id']}: missing {e['ref']}"
        if e["kind"] == "path_absent":
            gone = not (REPO / e["ref"]).exists()
            untracked = e["ref"] not in bmh._tracked_files()
            assert gone or untracked, (
                f"{item['id']}: {e['ref']} is present AND tracked, so the "
                f"'never landed' claim is stale")
    for d in item.get("merged", []) + item.get("docs", []):
        assert (REPO / d).exists(), f"{item['id']}: merged/doc ref missing {d}"


def test_referenced_commits_exist():
    shas = {c["sha"] for c in bmh.git_commits()}
    if not shas:
        pytest.skip("git history unavailable in this environment")
    bad = [(it["id"], e["ref"]) for it in ROADMAP for e in it["evidence"]
           if e["kind"] == "commit" and e["ref"] not in shas]
    assert not bad, f"roadmap cites commits that are not in git log: {bad}"


def test_every_plan_and_spec_doc_is_accounted_for():
    """A backlog that silently drops a doc is worse than one that admits a gap."""
    cov = bmh._doc_coverage()
    assert cov["missing"] == [], (
        f"{len(cov['missing'])} plan/spec docs are in docs/ but in no roadmap row: "
        f"{cov['missing']}")


def test_thresholds_are_named_and_explained():
    """The recommendation is only auditable if every threshold shows its reason."""
    keys = [t["key"] for t in bmh.THRESHOLDS]
    assert len(keys) == len(set(keys))
    for t in bmh.THRESHOLDS:
        assert t.get("label") and t.get("why"), f"{t['key']} needs a label and a why"
        assert isinstance(t["value"], (int, float))
