"""Corpus measurement: calibrate the §3c layers-tool trigger.

MEASUREMENT ONLY. Not a build artifact -- created to answer a single
question ("does the two-conjunct trigger in docs/plan-layer-system-tool.md
§3c clear its stated bar of >=60% bucket-A recall with <10% adversarial
non-layers firing?"). No product code is created or modified by this
script; it only reads the corpus and the local Scryfall snapshot.

`_LAYERS_READOUT_RE`, `_CONTINUOUS_EFFECT_RE`, and `_needs_layers_tool`
below are copied VERBATIM from plan §3c (lines ~578-607) -- not retuned,
not "improved". The one adaptation is noted inline: the plan's pseudocode
reads `c.oracle_text` for a single Card object; this project's `Card`
contract (src/rulesagent/contracts.py) stores oracle text per-face on
`Card.faces[i].oracle_text` (the top-level `Card.oracle_text` field does
already carry a faces-joined value in practice -- see the report -- but the
task spec calls for computing the union explicitly from `faces`, so that is
what `_oracle_text_union()` below does, joined by "\n").

Run: PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/calibrate_layers_trigger.py
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from rulesagent.tools.scryfall import get_card  # noqa: E402
from rulesagent.contracts import Card  # noqa: E402

EVALS_DIR = REPO_ROOT / "evals"
UNION_SLICE_PATH = EVALS_DIR / "_layers_union_slice.jsonl"
BUCKETS_PATH = EVALS_DIR / "_layers_buckets.json"
FULL_CORPUS_PATH = EVALS_DIR / "rulesguru_full.jsonl"
RESULTS_JSON_PATH = EVALS_DIR / "_layers_trigger_calibration.json"
RESULTS_MD_PATH = EVALS_DIR / "_layers_trigger_calibration.md"


# =============================================================================
# COPIED VERBATIM from docs/plan-layer-system-tool.md §3c (lines ~578-607).
# Do not retune, extend, or "fix" these patterns -- we are measuring the
# proposal as written.
# =============================================================================

# Conjunct 1: the question asks for a characteristic readout.
_LAYERS_READOUT_RE = re.compile(
    r"\bcharacteristics\b"
    r"|\b(?:power and toughness|p/t)\b"
    r"|\bis\b.{0,40}?\ba creature\b"
    r"|\b(?:does|do|will)\b.{0,40}?\bhave\b"
    r"|\bwhat\b.{0,20}?\b(?:land )?(?:types?|subtypes?|colou?rs?)\b"
    r"|\bcolou?r\(s\)\b"
    r"|\btap\b.{0,25}?\bfor\b"
    r"|\blook like\b"
    r"|\bbe legendary\b",
    re.IGNORECASE | re.DOTALL,
)

# Conjunct 2: at least two loaded cards carry continuous-effect-shaped static text.
_CONTINUOUS_EFFECT_RE = re.compile(
    r"get\s*[+-]\d+/[+-]\d+"
    r"|\b(?:base power and toughness|loses? all abilities|can't have)\b"
    r"|\b(?:becomes?|are|is)\b.{0,30}?\b(?:creature|land|artifact|enchantment)s?\b"
    r"|\bhave\b.{0,20}?\bbase\b",
    re.IGNORECASE | re.DOTALL,
)


def _needs_layers_tool(question: str, cards: list[Card]) -> bool:
    if not _LAYERS_READOUT_RE.search(question):
        return False
    hits = sum(1 for c in cards if _CONTINUOUS_EFFECT_RE.search(c.oracle_text or ""))
    return hits >= 2


# =============================================================================
# END verbatim copy.
# =============================================================================


def _oracle_text_union(card: Card) -> str:
    """Union of every face's oracle_text, joined by newline.

    Per the task's spec-discrepancy note: the plan's pseudocode calls
    `c.oracle_text` directly, but this project's Card contract documents
    oracle text as living per-face. In practice this project's
    scripts/refresh_scryfall_bulk.py and scryfall.py's live-fallback path
    BOTH already populate the top-level `Card.oracle_text` as a faces-joined
    value (joined with "\\n//\\n") for multi-faced cards, so the two are
    usually equivalent -- but we compute the union from `faces` explicitly
    here per instruction, joined by "\\n", rather than relying on the
    top-level field. Falls back to the top-level field if `faces` is empty
    (should not happen for a resolved card, but keeps this defensive).
    """
    if card.faces:
        return "\n".join(f.oracle_text or "" for f in card.faces)
    return card.oracle_text or ""


class _FakeCardForRegex:
    """Adapter so `_needs_layers_tool`'s verbatim `c.oracle_text` access
    reads our faces-union text instead of the raw top-level field, without
    editing the copied function body at all."""

    __slots__ = ("oracle_text",)

    def __init__(self, oracle_text: str) -> None:
        self.oracle_text = oracle_text


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def truncate(s: str, n: int = 160) -> str:
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


class CardCache:
    """Fetches get_card() once per distinct name, local DB only."""

    def __init__(self) -> None:
        self._cache: dict[str, Card | None] = {}
        self.unresolved: set[str] = set()

    def resolve(self, names: list[str]) -> list[_FakeCardForRegex]:
        out = []
        for name in names:
            if name not in self._cache:
                self._cache[name] = get_card(name, no_refresh=True)
            card = self._cache[name]
            if card is None:
                self.unresolved.add(name)
                continue
            out.append(_FakeCardForRegex(_oracle_text_union(card)))
        return out

    def continuous_effect_hits(self, names: list[str]) -> int:
        cards = self.resolve(names)
        return sum(1 for c in cards if _CONTINUOUS_EFFECT_RE.search(c.oracle_text or ""))


def evaluate_row(row: dict, cache: CardCache) -> dict:
    question = row["question"]
    names = row.get("cards", [])
    cards = cache.resolve(names)
    c1 = bool(_LAYERS_READOUT_RE.search(question))
    n_cont_hits = sum(1 for c in cards if _CONTINUOUS_EFFECT_RE.search(c.oracle_text or ""))
    c2 = n_cont_hits >= 2
    fires = c1 and c2
    return {
        "id": row["id"],
        "question": question,
        "n_cards": len(names),
        "n_cont_hits": n_cont_hits,
        "c1": c1,
        "c2": c2,
        "fires": fires,
    }


def main() -> None:
    union_rows = load_jsonl(UNION_SLICE_PATH)
    buckets = json.loads(BUCKETS_PATH.read_text(encoding="utf-8"))
    full_rows = load_jsonl(FULL_CORPUS_PATH)

    union_ids = {r["id"] for r in union_rows}
    assert union_ids == set(buckets.keys()), (
        f"bucket file / union slice id mismatch: "
        f"{union_ids ^ set(buckets.keys())}"
    )

    bucket_counts = {"A": 0, "B": 0, "C": 0}
    for v in buckets.values():
        bucket_counts[v] += 1

    cache = CardCache()

    rows_by_id = {r["id"]: r for r in union_rows}
    bucket_a_ids = [i for i, b in buckets.items() if b == "A"]
    bucket_c_ids = [i for i, b in buckets.items() if b == "C"]

    bucket_a_results = [evaluate_row(rows_by_id[i], cache) for i in bucket_a_ids]
    bucket_c_results = [evaluate_row(rows_by_id[i], cache) for i in bucket_c_ids]

    a_fired = sum(1 for r in bucket_a_results if r["fires"])
    a_total = len(bucket_a_results)
    a_recall = a_fired / a_total if a_total else 0.0

    a_pass_c1 = sum(1 for r in bucket_a_results if r["c1"])
    a_pass_c2 = sum(1 for r in bucket_a_results if r["c2"])
    a_pass_both = sum(1 for r in bucket_a_results if r["c1"] and r["c2"])

    c_fired = sum(1 for r in bucket_c_results if r["fires"])
    c_total = len(bucket_c_results)
    c_fire_rate = c_fired / c_total if c_total else 0.0

    misses = [r for r in bucket_a_results if not r["fires"]]

    # Non-layers samples: exclude the 68 union-slice ids from the full corpus.
    non_union_rows = [r for r in full_rows if r["id"] not in union_ids]

    random.seed(613)
    plain_sample = random.sample(non_union_rows, 100)

    adversarial_population = [r for r in non_union_rows if len(r.get("cards", [])) >= 2]
    random.seed(613)
    adversarial_sample = random.sample(adversarial_population, 100)

    plain_results = [evaluate_row(r, cache) for r in plain_sample]
    plain_fired = sum(1 for r in plain_results if r["fires"])
    plain_rate = plain_fired / len(plain_results)

    adversarial_results = [evaluate_row(r, cache) for r in adversarial_sample]
    adv_fired = sum(1 for r in adversarial_results if r["fires"])
    adv_rate = adv_fired / len(adversarial_results)
    adv_false_positives = [r for r in adversarial_results if r["fires"]]

    verdict_pass = (a_recall >= 0.60) and (adv_rate < 0.10)

    # ---- machine-readable output ----
    output = {
        "bucket_counts": bucket_counts,
        "expected_bucket_counts": {"A": 51, "B": 1, "C": 16},
        "bucket_a": {
            "total": a_total,
            "fired": a_fired,
            "recall": a_recall,
            "pass_c1": a_pass_c1,
            "pass_c2": a_pass_c2,
            "pass_both": a_pass_both,
            "results": bucket_a_results,
        },
        "bucket_c": {
            "total": c_total,
            "fired": c_fired,
            "fire_rate": c_fire_rate,
            "results": bucket_c_results,
        },
        "non_layers_plain": {
            "n": len(plain_results),
            "fired": plain_fired,
            "fire_rate": plain_rate,
        },
        "non_layers_adversarial": {
            "n": len(adversarial_results),
            "fired": adv_fired,
            "fire_rate": adv_rate,
            "false_positives": adv_false_positives,
        },
        "unresolved_card_names": {
            "count": len(cache.unresolved),
            "names": sorted(cache.unresolved),
        },
        "verdict": {
            "bar": "bucket_a_recall >= 0.60 AND non_layers_adversarial_fire_rate < 0.10",
            "bucket_a_recall": a_recall,
            "adversarial_fire_rate": adv_rate,
            "pass": verdict_pass,
        },
    }
    RESULTS_JSON_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    # ---- human-readable markdown ----
    lines = []
    lines.append("# Layers-tool trigger calibration (§3c)\n")
    lines.append(f"Bucket counts: A={bucket_counts['A']}, B={bucket_counts['B']}, "
                  f"C={bucket_counts['C']} (expected A=51, B=1, C=16)\n")
    lines.append(f"## Bucket A recall: {a_fired}/{a_total} = {a_recall:.1%}\n")
    lines.append(f"Conjunct isolation on bucket A: pass conjunct 1 = {a_pass_c1}/{a_total}, "
                 f"pass conjunct 2 = {a_pass_c2}/{a_total}, pass both (fires) = {a_pass_both}/{a_total}\n")
    lines.append(f"## Bucket C firing rate: {c_fired}/{c_total} = {c_fire_rate:.1%}\n")
    lines.append(f"## Non-layers PLAIN sample firing rate: {plain_fired}/{len(plain_results)} = {plain_rate:.1%}\n")
    lines.append(f"## Non-layers ADVERSARIAL sample firing rate: {adv_fired}/{len(adversarial_results)} = {adv_rate:.1%}\n")
    lines.append(f"## Unresolved card names: {len(cache.unresolved)}\n")
    if cache.unresolved:
        lines.append(", ".join(sorted(cache.unresolved)) + "\n")
    lines.append(f"\n## VERDICT: {'PASS' if verdict_pass else 'FAIL'} "
                 f"(bucket-A recall {a_recall:.1%} {'>=' if a_recall>=0.6 else '<'} 60%, "
                 f"adversarial firing {adv_rate:.1%} {'<' if adv_rate<0.1 else '>='} 10%)\n")

    lines.append("\n## Bucket-A misses (did not fire)\n")
    for r in misses:
        if not r["c1"] and not r["c2"]:
            failed = "both"
        elif not r["c1"]:
            failed = "c1"
        else:
            failed = "c2"
        lines.append(
            f"{r['id']} | failed={failed} | n_cards={r['n_cards']} | "
            f"n_cont_hits={r['n_cont_hits']} | {truncate(r['question'])}"
        )

    lines.append("\n## Adversarial sample false positives (fired)\n")
    for r in adv_false_positives:
        lines.append(
            f"{r['id']} | n_cards={r['n_cards']} | n_cont_hits={r['n_cont_hits']} | "
            f"{truncate(r['question'])}"
        )

    RESULTS_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- stdout summary (what the caller reads) ----
    print(f"Bucket counts: A={bucket_counts['A']} B={bucket_counts['B']} C={bucket_counts['C']} "
          f"(expected A=51 B=1 C=16)")
    print(f"Bucket A recall: {a_fired}/{a_total} = {a_recall:.1%}")
    print(f"Conjunct isolation: c1_pass={a_pass_c1} c2_pass={a_pass_c2} both_pass={a_pass_both} (of {a_total})")
    print(f"Bucket C firing rate: {c_fired}/{c_total} = {c_fire_rate:.1%}")
    print(f"Non-layers PLAIN firing rate: {plain_fired}/{len(plain_results)} = {plain_rate:.1%}")
    print(f"Non-layers ADVERSARIAL firing rate: {adv_fired}/{len(adversarial_results)} = {adv_rate:.1%}")
    print(f"Unresolved names: PLAIN+ADV+bucketA+bucketC total distinct unresolved = {len(cache.unresolved)}")
    print(f"VERDICT: {'PASS' if verdict_pass else 'FAIL'}")
    print()
    print("=== BUCKET-A MISSES ===")
    for r in misses:
        if not r["c1"] and not r["c2"]:
            failed = "both"
        elif not r["c1"]:
            failed = "c1"
        else:
            failed = "c2"
        print(f"{r['id']} | failed={failed} | n_cards={r['n_cards']} | "
              f"n_cont_hits={r['n_cont_hits']} | {truncate(r['question'])}")
    print()
    print("=== ADVERSARIAL FALSE POSITIVES ===")
    for r in adv_false_positives:
        print(f"{r['id']} | n_cards={r['n_cards']} | n_cont_hits={r['n_cont_hits']} | "
              f"{truncate(r['question'])}")


if __name__ == "__main__":
    main()
