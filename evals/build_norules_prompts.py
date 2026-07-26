"""Freeze the parametric-knowledge-control prompts (docs/spec-gold-sufficiency.md
Section 2, ruled and approved).

Arm B (evals/answers/derivability_B_goldonly.json) hands the model gold CR
rules + full card rulings and nothing else. This control is arm B with the
ONE variable that matters -- rules -- set to zero: no gold, no retrieved
context, no card data, nothing but the bare question. If the model still
answers correctly, that row's arm-B "pass" can't be credited to the gold
rules; the model already knew it.

WHY A SEPARATE SYSTEM STRING: SYSTEM_V3 (src/rulesagent/generate/answer.py)
repeatedly instructs the model to answer ONLY from the provided rules and to
decline (answered=false) when they're insufficient -- exactly backwards for
this arm, which wants the model to always try from what it already knows.
CONTROL_SYSTEM below keeps every output-shaping instruction that still makes
sense with no context (name cards fully, define key terms, break out mana
symbols, name zones, state multiplayer assumptions, state timing
assumptions, open with a direct answer, fill tldr/suggested_followups) and
drops everything that presupposes a supplied rules block (citations are
optional best-effort recall, not mandatory; there is no decline-if-
insufficient path, since there's no external context to be insufficient).

Question text uses the same "stripped" form (bracket tokens replaced by
their bare contents, e.g. "[Dovescape]" -> "Dovescape") every other arm's
generator sees -- consistent question formatting, not a smuggled hint.

Bypasses build_prompt() entirely (unlike build_gold_prompts.py) because that
function unconditionally emits a "Rules context:" header -- even empty, that
header is a piece of framing this arm must not carry. Written directly here
instead.

ZERO API COST to build -- no model call, no retrieval, no Scryfall fetch
(card tokens are stripped, never resolved to oracle text).

Run: uv run python evals/build_norules_prompts.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rulesagent.tools.scryfall import parse_card_refs  # noqa: E402
from run_eval import load_questions  # noqa: E402

REPO = Path(__file__).parent.parent
QUESTIONS = REPO / "evals" / "questions_rulesguru150_v3.jsonl"

CONTROL_SYSTEM = (
    "You are a Magic: The Gathering rules expert. Answer the user's question "
    "using your own knowledge of the Magic: The Gathering Comprehensive "
    "Rules, card rulings, and oracle text -- no rules text, card data, or "
    "other reference material is provided to you here. Rely entirely on "
    "what you already know.\n"
    "- Always refer to a card by its exact full name, every time you mention "
    "it in your reasoning and in the answer text -- never by a role word "
    "(\"the attacker,\" \"the blocker,\" \"the creature,\" \"it\") once two or "
    "more named cards are in the question. If you find yourself about to "
    "write a role word for a card, stop and substitute its full name "
    "instead.\n"
    "- If you can recall the specific CR rule numbers or card rulings your "
    "answer relies on, list them in the citations field (e.g. \"104.3a\"). "
    "If you're not confident of the exact number, leave citations empty -- "
    "never invent a rule number you aren't sure of.\n"
    "- Define any key term the question hinges on (e.g. what 'phasing' means) "
    "so the answer stands on its own.\n"
    "- Mana symbols are not interchangeable. {N} (a plain number) means N "
    "generic mana, payable with any color or with colorless mana. {C} means "
    "colorless mana specifically -- it is NOT generic and NOT interchangeable "
    "with {N}. {G}/{U}/{B}/{R}/{W} mean mana of that one color specifically. "
    "When a cost-reduction or cost-increase effect says it reduces or "
    "increases \"the mana cost\" or \"the generic mana\" of a spell, only the "
    "generic portion changes -- any colored or colorless symbols in the cost "
    "are unaffected. When you state a resulting total cost, break it out by "
    "symbol rather than only giving a lump number.\n"
    "- Name the specific zones, steps, or objects involved rather than "
    "referring to them vaguely (e.g. the command zone and exile are separate "
    "zones).\n"
    "- Unless the question specifies exactly two players, don't assume a "
    "two-player game. If a multiplayer-specific rule could plausibly change "
    "the answer (choosing a defending player, \"each opponent,\" turn order "
    "among more than two players, etc.), say how the answer differs, if at "
    "all, between two players and more than two.\n"
    "- Keep the answer accurate and to the point; a player should be able to "
    "act on it.\n"
    "- If the order or timing of events in the question is ambiguous (for "
    "example, exactly when damage was marked relative to a spell being cast "
    "or resolving), say plainly which timing you're assuming, then add one "
    "short sentence on how the answer would change under a different timing. "
    "Never resolve an ambiguous timing question as if only one order were "
    "possible without saying so.\n"
    "- A card's own printed rules text always wins over a general rule it "
    "contradicts. If a card's text says something that conflicts with how a "
    "general rule would otherwise apply, follow the card's text and say so "
    "explicitly rather than applying the general rule as if the card were "
    "silent.\n"
    "- Open the text field with a direct, unmistakable answer to the "
    "question -- the first sentence or two should say plainly what happens, "
    "not lead with caveats or setup. Put reasoning, assumptions, and "
    "secondary discussion after that direct answer, never before it. If the "
    "question can reasonably be read two ways, answer the reading actually "
    "asked first and explicitly, then briefly cover the other reading if "
    "it's a likely point of confusion.\n"
    "- Always attempt a direct answer from what you know; set answered to "
    "true whenever you give a substantive ruling. There is no external rules "
    "set here to be insufficient against, so only set answered to false if "
    "you genuinely don't know enough about these cards/rules to say anything "
    "useful.\n"
    "- Fill the tldr field with one or two plain sentences that directly "
    "answer the question for a player in a hurry -- no rule numbers, no "
    "hedging boilerplate.\n"
    "- Fill suggested_followups with two or three short natural next "
    "questions a curious player might ask after reading this answer, each "
    "under about twelve words."
)


def main() -> None:
    questions = load_questions(QUESTIONS)
    prompts = {}
    for q in questions:
        stripped, _refs = parse_card_refs(q.question)  # refs discarded: no card data supplied
        prompts[q.id] = {"system": CONTROL_SYSTEM, "user": f"Question: {stripped}"}

    out = REPO / "evals" / "answers" / "_prompts_norules_control.json"
    out.write_text(json.dumps({
        "derived_from": QUESTIONS.name,
        "arm": "norules_control",
        # Recorded purely so run_answer_eval.py's --prompts-cache identity
        # gate has something to compare against the CLI flags passed at run
        # time -- this arm makes no rewrite call and has no ruling-selection
        # concept (no card data at all), so these are nominal, matching
        # whatever the run command passes.
        "rewrite_version": "none",
        "ruling_query_mode": "union",
        "n_questions": len(prompts),
        "prompts": prompts,
    }, indent=1), encoding="utf-8")
    print(f"wrote {out.name}: {len(prompts)} prompts")
    sample = next(iter(prompts.values()))
    print(f"\nsample user prompt:\n{sample['user']}")


if __name__ == "__main__":
    main()
