"""Freeze the three CARD-CHANNEL placebo arms for the retrieval-value A/B
follow-on (the CR-rules placebo, evals/build_ab_placebo_prompts.py, showed
the rules block contributes almost nothing -- 66.7% real vs 63.3% placebo).
The hypothesis under test here is that the work is being done by the CARD
channel -- oracle text and Scryfall rulings -- not the CR rules.

Reads evals/answers/_prompts_ab_real.json (frozen arm A) and, for every one
of its 120 rows, builds three sibling caches by TEXT SURGERY on the frozen
`user` string -- never by re-running build_prompt(). That is a deliberate
choice, not laziness: build_prompt() recomputes the "Symbol reference" block
from whichever `cards` it is given, so calling it with a donor's cards would
silently change a region outside the one each arm is supposed to touch (the
symbol legend would drift to match the borrowed cards instead of staying
byte-identical to arm A's). Splicing the already-frozen text guarantees the
untouched regions are untouched, by construction, and is exactly what
`split_user()` / `card_block_texts()` below exist to do safely.

  1. _prompts_ab_placebo_rulings.json   -- real rules, real oracle text,
     RULINGS swapped (per matching card, cycling through the donor's cards
     with rulings if the counts don't line up 1:1).
  2. _prompts_ab_placebo_carddata.json  -- real rules, the WHOLE "Card
     data:" section swapped for one donor's whole section (verbatim, so
     headers and rulings stay internally consistent -- never interleaved
     across donors).
  3. _prompts_ab_placebo_all.json       -- both: the rules half is spliced
     in from the EXISTING _prompts_ab_placebo.json (arm B) so the rules
     placebo is identical across arms B and E; the card half reuses arm D's
     (this script's cache #2) donor mapping so the card placebo is
     identical across arms D and E. Only arm E differs from B+D by being
     their union -- no new derangement is drawn for it.

DERANGEMENT SUBSETS, not the full 120 rows. Two rows can't donate or
receive a "borrowed" region because they don't have one to begin with:
  - rg1006 has no cards at all (a pure-rules question) -- excluded from the
    card-data derangement (cache #2/#3); its own row is left byte-identical
    to arm A in the card dimension because there is no Card data section to
    touch.
  - rg46, rg625, rg1006 have zero rulings anywhere in their card data (the
    cards are real but Scryfall has no rulings for them) -- excluded from
    the rulings derangement (cache #1) the same way.
A derangement is drawn (rejection sampling, fixed seed) over exactly the
subset that both needs a donor and can supply one; the excluded rows keep
their arm-A text for that one region and get `null` in `borrowed_from`,
recorded explicitly rather than silently reusing rg's own content.

Zero API/model cost: no retrieval, no embedding, no generation. Every
byte moved here was already paid for by build_ab_real_prompts.py.

Run: uv run python evals/build_ab_placebo_channel_prompts.py
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.generate.answer import _format_cards, label_rulings  # noqa: E402
from build_ab_real_prompts import ordered_cards  # noqa: E402

REPO = Path(__file__).parent.parent
REAL_CACHE = REPO / "evals" / "answers" / "_prompts_ab_real.json"
RULES_PLACEBO_CACHE = REPO / "evals" / "answers" / "_prompts_ab_placebo.json"
AB_ROWS = REPO / "evals" / "ab_rows.jsonl"

OUT_RULINGS = REPO / "evals" / "answers" / "_prompts_ab_placebo_rulings.json"
OUT_CARDDATA = REPO / "evals" / "answers" / "_prompts_ab_placebo_carddata.json"
OUT_ALL = REPO / "evals" / "answers" / "_prompts_ab_placebo_all.json"

# Independent RNG draws, distinct from build_ab_rows.py's 613 and
# build_ab_placebo_prompts.py's 613 (same value, different RNG instance/use)
# so the three swaps are not correlated with each other or with the rules
# derangement.
SEED_RULINGS = 727
SEED_CARDDATA = 841

CARD_DATA_HDR = "\n\nCard data:\n"
RULES_HDR = "Rules context:\n"
RULINGS_MARK = "\nRulings:\n"


def derangement(ids: list[str], seed: int) -> dict[str, str]:
    """A derangement of `ids` (no id maps to itself), reproducible under
    `seed`. Same algorithm as build_ab_placebo_prompts.derangement, kept
    local so this script doesn't pull in that module's heavy CR-parsing
    import chain for what is otherwise a pure text-splicing job."""
    n = len(ids)
    rng = random.Random(seed)
    idx = list(range(n))
    for _ in range(10_000):
        rng.shuffle(idx)
        if all(idx[i] != i for i in range(n)):
            return {ids[i]: ids[idx[i]] for i in range(n)}
    raise SystemExit(f"[ERROR] could not find a derangement of {n} elements in 10000 tries")


def split_user(user: str) -> tuple[str, str | None, str]:
    """(prefix, card_body_or_None, suffix). `prefix` always ends right after
    "Card data:\\n" when a card section exists, else right before whichever
    marker starts the suffix. `card_body` is exactly the text between the
    "Card data:\\n" header and the next marker -- never includes the header
    itself or the marker that follows."""
    if CARD_DATA_HDR in user:
        idx = user.index(CARD_DATA_HDR)
        prefix = user[: idx + len(CARD_DATA_HDR)]
        rest = user[idx + len(CARD_DATA_HDR):]
        markers = [m for m in ("\n\nSymbol reference", "\n\nQuestion:") if m in rest]
        cut = min(rest.index(m) for m in markers)
        return prefix, rest[:cut], rest[cut:]
    markers = [m for m in ("\n\nSymbol reference", "\n\nQuestion:") if m in user]
    cut = min(user.index(m) for m in markers)
    return user[:cut], None, user[cut:]


def card_block_texts(cards) -> list[str]:
    """Each card's own formatted block, computed independently. Matches
    _format_cards' per-card rendering exactly -- _format_cards processes
    cards independently and joins with "\\n\\n" -- verified against every
    row's frozen real text (build_ab_placebo_channel_prompts dev check):
    "\\n\\n".join(card_block_texts(cards)) == the real cache's card body for
    all 119 rows that have cards, 0 mismatches."""
    return [_format_cards([label_rulings(c)]) for c in cards]


def rulings_pool(cards) -> list[list[str]]:
    """One entry per donor card that HAS rulings: its own already-labelled
    ruling strings (e.g. "[Donor Card ruling #2] ..."), in card order. Cards
    with no rulings contribute nothing -- there is nothing to borrow from
    them."""
    pool = []
    for c in cards:
        labeled = label_rulings(c).rulings
        if labeled:
            pool.append(labeled)
    return pool


def apply_rulings_swap(block: str, donor_labeled: list[str]) -> str:
    """Replace only the bullet lines after "Rulings:" in one card's block
    with `donor_labeled` (already-labelled ruling strings, no leading
    "- "). The "Rulings:" heading itself, and everything above it (header +
    oracle text), is untouched."""
    head, _, _tail = block.partition(RULINGS_MARK)
    bullets = "\n".join(f"- {r}" for r in donor_labeled)
    return head + RULINGS_MARK + bullets


def load_rows() -> dict[str, str]:
    rows = {}
    for line in AB_ROWS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["id"]] = r["question"]
    return rows


def build_rulings_cache(real: dict, rows: dict[str, str]) -> dict:
    prompts = real["prompts"]
    qids = sorted(prompts)

    cards_of: dict[str, list] = {}
    pools: dict[str, list[list[str]]] = {}
    for qid in qids:
        cards, _missing = ordered_cards(rows[qid])
        cards_of[qid] = cards
        pools[qid] = rulings_pool(cards)

    eligible = [qid for qid in qids if pools[qid]]  # has >=1 card w/ rulings
    donor_of = derangement(eligible, SEED_RULINGS)
    # every qid gets an entry; non-eligible rows get null (nothing to swap)
    borrowed_from = {qid: donor_of.get(qid) for qid in qids}

    out_prompts: dict[str, dict] = {}
    for qid in qids:
        user = prompts[qid]["user"]
        donor = borrowed_from[qid]
        if donor is None:
            out_prompts[qid] = {"system": prompts[qid]["system"], "user": user}
            continue
        prefix, card_body, suffix = split_user(user)
        assert card_body is not None, f"{qid}: eligible (has rulings) but no card body?!"
        target_cards = cards_of[qid]
        orig_blocks = card_block_texts(target_cards)
        recon = "\n\n".join(orig_blocks)
        if recon != card_body:
            raise SystemExit(f"[ERROR] {qid}: reconstructed card body doesn't match frozen "
                              f"real text -- card data may have drifted since the real cache "
                              f"was built. Refusing to swap on a mismatched base.")
        pool = pools[donor]
        new_blocks = []
        pool_i = 0
        for c, block in zip(target_cards, orig_blocks):
            if c.rulings:
                new_blocks.append(apply_rulings_swap(block, pool[pool_i % len(pool)]))
                pool_i += 1
            else:
                new_blocks.append(block)
        new_card_body = "\n\n".join(new_blocks)
        out_prompts[qid] = {
            "system": prompts[qid]["system"],
            "user": prefix + new_card_body + suffix,
        }

    return {
        "derived_from": REAL_CACHE.name,
        "arm": "C_placebo_rulings",
        "rewrite_version": real["rewrite_version"],
        "ruling_query_mode": real["ruling_query_mode"],
        "vector_model": real["vector_model"],
        "top_k": real["top_k"],
        "n_questions": len(out_prompts),
        "borrowed_from": borrowed_from,
        "prompts": out_prompts,
    }


def build_carddata_donor_map(real: dict) -> dict[str, str | None]:
    """The card-data derangement, over rows that actually have a Card data
    section. Factored out so build_all_cache() can reuse it -- the whole
    point of arm E is that its card half is IDENTICAL to arm D's, not a
    fresh draw."""
    prompts = real["prompts"]
    qids = sorted(prompts)
    eligible = [qid for qid in qids if split_user(prompts[qid]["user"])[1] is not None]
    donor_of = derangement(eligible, SEED_CARDDATA)
    return {qid: donor_of.get(qid) for qid in qids}


def build_carddata_cache(real: dict, borrowed_from: dict[str, str | None]) -> dict:
    prompts = real["prompts"]
    qids = sorted(prompts)
    out_prompts: dict[str, dict] = {}
    for qid in qids:
        user = prompts[qid]["user"]
        donor = borrowed_from[qid]
        if donor is None:
            out_prompts[qid] = {"system": prompts[qid]["system"], "user": user}
            continue
        prefix, _card_body, suffix = split_user(user)
        _d_prefix, donor_body, _d_suffix = split_user(prompts[donor]["user"])
        assert donor_body is not None, f"{qid}: donor {donor} has no card body?!"
        out_prompts[qid] = {
            "system": prompts[qid]["system"],
            "user": prefix + donor_body + suffix,
        }
    return {
        "derived_from": REAL_CACHE.name,
        "arm": "D_placebo_carddata",
        "rewrite_version": real["rewrite_version"],
        "ruling_query_mode": real["ruling_query_mode"],
        "vector_model": real["vector_model"],
        "top_k": real["top_k"],
        "n_questions": len(out_prompts),
        "borrowed_from": borrowed_from,
        "prompts": out_prompts,
    }


def build_all_cache(real: dict, rules_placebo: dict, carddata_borrowed: dict[str, str | None]) -> dict:
    """Rules half from the EXISTING arm B cache (its own donor mapping,
    untouched); card half re-applied on top with the SAME donor mapping as
    arm D. Composable because split_user() only ever looks at the text it
    is given: feeding it arm B's already-rules-swapped user text yields a
    prefix that carries the swapped rules block, so splicing a donor's card
    body into THAT prefix produces "rules swapped AND card data swapped"
    without a third derangement draw."""
    real_prompts = real["prompts"]
    rb_prompts = rules_placebo["prompts"]
    qids = sorted(real_prompts)
    out_prompts: dict[str, dict] = {}
    for qid in qids:
        base_user = rb_prompts[qid]["user"]  # rules already swapped, cards still real
        donor = carddata_borrowed[qid]
        if donor is None:
            out_prompts[qid] = {"system": rb_prompts[qid]["system"], "user": base_user}
            continue
        prefix, _card_body, suffix = split_user(base_user)
        _d_prefix, donor_body, _d_suffix = split_user(real_prompts[donor]["user"])
        assert donor_body is not None, f"{qid}: donor {donor} has no card body?!"
        out_prompts[qid] = {
            "system": rb_prompts[qid]["system"],
            "user": prefix + donor_body + suffix,
        }
    return {
        "derived_from": [REAL_CACHE.name, RULES_PLACEBO_CACHE.name],
        "arm": "E_placebo_all",
        "rewrite_version": real["rewrite_version"],
        "ruling_query_mode": real["ruling_query_mode"],
        "vector_model": real["vector_model"],
        "top_k": real["top_k"],
        "n_questions": len(out_prompts),
        "borrowed_from": {
            "rules": rules_placebo["borrowed_from"],
            "carddata": carddata_borrowed,
        },
        "prompts": out_prompts,
    }


def main() -> None:
    real = json.loads(REAL_CACHE.read_text(encoding="utf-8"))
    rules_placebo = json.loads(RULES_PLACEBO_CACHE.read_text(encoding="utf-8"))
    rows = load_rows()

    rulings_cache = build_rulings_cache(real, rows)
    OUT_RULINGS.write_text(json.dumps(rulings_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    n_swapped = sum(1 for v in rulings_cache["borrowed_from"].values() if v is not None)
    print(f"wrote {OUT_RULINGS.name}: {rulings_cache['n_questions']} prompts "
          f"({n_swapped} rulings-swapped, {rulings_cache['n_questions'] - n_swapped} unchanged: no rulings to swap)")

    carddata_borrowed = build_carddata_donor_map(real)
    carddata_cache = build_carddata_cache(real, carddata_borrowed)
    OUT_CARDDATA.write_text(json.dumps(carddata_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    n_swapped = sum(1 for v in carddata_borrowed.values() if v is not None)
    print(f"wrote {OUT_CARDDATA.name}: {carddata_cache['n_questions']} prompts "
          f"({n_swapped} card-data-swapped, {carddata_cache['n_questions'] - n_swapped} unchanged: no cards)")

    all_cache = build_all_cache(real, rules_placebo, carddata_borrowed)
    OUT_ALL.write_text(json.dumps(all_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT_ALL.name}: {all_cache['n_questions']} prompts "
          f"(rules half reused from {RULES_PLACEBO_CACHE.name}, card half reused from {OUT_CARDDATA.name})")


if __name__ == "__main__":
    main()
