"""Gold-by-ablation for card questions (docs/plan-card-gold-ablation.md).

For each card question: hold the card data (oracle text + all rulings) FIXED,
generate the full-pool answer as the reference (Jon vouches it's correct), then
remove retrieved rules one at a time and see which ones the model actually
needs to still reach the same conclusion. The minimal necessary set is the gold;
its redundancy structure gives match=any vs all.

We ablate only the CITED rules: the generator's prompt now REQUIRES every rule
it relies on to appear in citations, so the cited set IS the used set -- an
uncited rule can't be load-bearing. That makes ablation cheap and sound.

Each subset is generated TRIALS times and judged by majority (sonnet-5 has no
temperature pin, so one run can flip on noise -- the #3a lesson). A Haiku judge
runs alongside the sonnet-5 judge on the same pairs to measure whether Haiku is
a reliable (cheaper) judge for scale.

Reports STRUCTURE (necessary / removable / alternatives) per question; does NOT
auto-write gold -- encoding it (esp. the mixed "all of X + any of Y" case our
match field can't express) is Jon's call. Run:
  uv run python evals/ablate_gold.py
"""

import re
import sys
from collections import Counter
from pathlib import Path

import anthropic
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.contracts import Answer, Card, Retrieved  # noqa: E402
from rulesagent.generate.answer import (  # noqa: E402
    GEN_MODEL, REWRITE_MODEL, REWRITE_N, SYSTEM, _format_cards, _format_context,
)
from rulesagent.index.store import VectorStore  # noqa: E402
from rulesagent.retrieve.rewrite import rewrite_query  # noqa: E402
from rulesagent.tools.scryfall import get_card, parse_card_refs  # noqa: E402

REPO = Path(__file__).parent.parent
CARDS_PATH = REPO / "evals" / "cards.jsonl"
VECTOR_MODEL = "voyage-4-large"
TOP_K = 15
TRIALS = 3
JUDGE_MODEL = "claude-sonnet-5"
HAIKU_JUDGE = "claude-haiku-4-5"
RULE_RE = re.compile(r"^\d{3}\.\d")  # a citation that's a rule number, not a card name

client = anthropic.Anthropic()


def load_cards():
    import json
    return [json.loads(l) for l in CARDS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def generate(retrieved: list[Retrieved], cards: list[Card], question: str) -> Answer:
    """Generate an answer from a CONTROLLED rule subset + fixed card data --
    the same prompt assembly answer.py uses, but with the rule set we choose so
    we can ablate it."""
    user = f"Rules context:\n{_format_context(retrieved)}"
    if cards:
        user += f"\n\nCard data:\n{_format_cards(cards)}"
    user += f"\n\nQuestion: {question}"
    try:
        resp = client.messages.parse(
            model=GEN_MODEL, max_tokens=8192, system=SYSTEM,
            messages=[{"role": "user", "content": user}], output_format=Answer,
        )
        return resp.parsed_output or Answer(text="(empty)", citations=[], answered=False)
    except Exception:
        return Answer(text="(generation failed)", citations=[], answered=False)


class _Verdict(BaseModel):
    verdict: str  # "same" | "different"
    reason: str


JUDGE_SYS = (
    "You compare a CANDIDATE answer to a REFERENCE answer that is known correct, "
    "for the same Magic: The Gathering rules question. Decide whether the "
    "candidate reaches the SAME core ruling/conclusion as the reference. Focus "
    "ONLY on the final ruling -- ignore wording, length, and how much supporting "
    "detail each gives. If the candidate reaches the same bottom-line answer, "
    "verdict is 'same'. If it reaches a different, wrong, or materially "
    "incomplete conclusion (e.g. it now declines, or gets the ruling backwards), "
    "verdict is 'different'."
)


def judge(question: str, reference: str, candidate: str, model: str) -> str:
    user = (f"Question: {question}\n\nREFERENCE (correct):\n{reference}\n\n"
            f"CANDIDATE:\n{candidate}")
    try:
        resp = client.messages.parse(
            model=model, max_tokens=1024, system=JUDGE_SYS,
            messages=[{"role": "user", "content": user}], output_format=_Verdict,
        )
        v = resp.parsed_output
        return v.verdict if v else "different"
    except Exception:
        return "different"


def majority_different(question, reference, candidate_answers, agree_tally) -> bool:
    """3 candidates (the trials). Judge each vs reference with BOTH models;
    return True if the SONNET judge majority says 'different' (answer broke).
    Also tallies sonnet-vs-haiku judge agreement for Jon's Haiku question."""
    sonnet_verdicts = []
    for cand in candidate_answers:
        sv = judge(question, reference, cand, JUDGE_MODEL)
        hv = judge(question, reference, cand, HAIKU_JUDGE)
        sonnet_verdicts.append(sv)
        agree_tally["total"] += 1
        agree_tally["agree"] += (sv == hv)
    return sonnet_verdicts.count("different") > len(sonnet_verdicts) // 2


def trials(retrieved, cards, question, n=TRIALS):
    return [generate(retrieved, cards, question).text for _ in range(n)]


def main():
    store = VectorStore.load(REPO / "data" / "parsed" / f"vector_{VECTOR_MODEL}.pkl")
    agree = {"total": 0, "agree": 0}
    for row in load_cards():
        q = row["question"]
        stripped, refs = parse_card_refs(q)
        cards = [c for r in refs if (c := get_card(r)) is not None]
        rw = rewrite_query(stripped, REWRITE_MODEL, REWRITE_N, client)
        top = store.search(rw.queries[0], TOP_K)
        top_ids = [r.chunk.source_id for r in top]

        full = generate(top, cards, q)
        reference = full.text
        cited = [c for c in full.citations if RULE_RE.match(c) and c in top_ids]

        print("=" * 90)
        print(f"{row['id']}: {q}")
        print(f"  cited rules (ablation candidates): {cited}")
        if not cited:
            print("  NO cited rules retrieved -- rulings/card data may answer it alone. FLAG.")
            continue

        necessary = []
        for R in cited:
            subset = [r for r in top if r.chunk.source_id != R]
            cands = trials(subset, cards, q)
            broke = majority_different(q, reference, cands, agree)
            print(f"  remove {R:<9} -> {'NECESSARY (answer broke)' if broke else 'removable (held)'}")
            if broke:
                necessary.append(R)

        removable = [c for c in cited if c not in necessary]
        alt_group = []
        if len(removable) >= 2:
            subset = [r for r in top if r.chunk.source_id not in removable]
            broke = majority_different(q, reference, trials(subset, cards, q), agree)
            if broke:
                alt_group = removable
                print(f"  remove-all-removable {removable} -> BROKE => alternatives (match=any among them)")
            else:
                print(f"  remove-all-removable {removable} -> held => genuinely redundant (not gold)")

        # sanity: remove every cited rule -> should break if rules matter at all
        subset = [r for r in top if r.chunk.source_id not in cited]
        sanity_broke = majority_different(q, reference, trials(subset, cards, q), agree)

        print(f"  --> NECESSARY (match=all core): {necessary}")
        print(f"  --> ALTERNATIVES (match=any group): {alt_group}")
        print(f"  --> sanity (remove all cited): {'broke (rules matter)' if sanity_broke else 'HELD -- rulings alone answer it, FLAG'}")
        print()

    if agree["total"]:
        print("=" * 90)
        print(f"JUDGE AGREEMENT (Haiku vs sonnet-5): {agree['agree']}/{agree['total']} "
              f"= {agree['agree']/agree['total']:.0%}")


if __name__ == "__main__":
    main()
