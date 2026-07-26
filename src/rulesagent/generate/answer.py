"""Generation: turn retrieved rules into a cited answer.

Days 6-9. Retrieves the top-k chunks with pure vector (the Phase C decision:
hybrid didn't help, vector's top-10 is the best simple candidate set), hands
them to Claude, and gets back a structured Answer -- cited, and honest when
the rules don't cover the question (the low-confidence / groundedness guard).

Reads ANTHROPIC_API_KEY from the environment (.env). Model is pinned for
reproducible answer evals -- see DECISIONS.md.
"""

import json
import logging
import re

import anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from rulesagent.contracts import Answer, Card, CardFace, Retrieved
from rulesagent.index.store import VectorStore
from rulesagent.retrieve.crossrefs import expand_crossrefs
from rulesagent.retrieve.hybrid import rrf_fuse
from rulesagent.retrieve.rewrite import rewrite_query
from rulesagent.tools.cost_calculator import calculate_cost
from rulesagent.tools.layer_resolver import resolve_layers
from rulesagent.tools.ruling_retrieval import ruling_id, select_rulings, select_rulings_union
from rulesagent.tools.scryfall import ATTRIBUTION, get_card, parse_card_refs, pop_fuzzy_fallbacks

load_dotenv()

logger = logging.getLogger(__name__)

GEN_MODEL = "claude-opus-5"  # pinned; one-line swap to A/B other models
# Valid output_config.effort levels (docs/spec-effort-and-norewrite.md Task 1).
# NOT a production default -- production stays on the API's own default effort
# unless a caller passes RulesAgent(effort=...) explicitly. Listed here so an
# unknown level fails at agent construction instead of at the API.
GEN_EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
# The effort GEN_MODEL was measured at, and the one production must therefore
# run. Jon's ruling 2026-07-26 was "opus-5 AT effort=low" -- the head-to-head
# that justified the swap (same 54 questions, rewrite v2, ruling raw, system v3,
# frozen judge) scored opus-low 75.9%/72.2% against sonnet's 66.7%/63.0%, at 23%
# lower cost and ~2.5x faster. Opus at the API's DEFAULT effort is an unmeasured
# arm and a more expensive one, so shipping the model id without this would
# discard the cost argument the decision rests on.
#
# Kept here, next to GEN_MODEL, because the two are one decision -- but applied
# by the API entry point (api/main.py) rather than as the RulesAgent default, so
# the "bare RulesAgent sends a byte-identical request body" invariant guarded by
# tests/test_prompt_identity.py survives, and eval arms keep defining effort
# explicitly (run_answer_eval.py always passes effort=args.effort, so an arm
# without --effort stays a distinct default-effort experiment).
GEN_EFFORT = "low"
# Production generation cap. sonnet-5 runs adaptive thinking by default and
# max_tokens bounds thinking AND visible text together, so on hard multi-step
# questions most of this budget is thinking the user never sees.
#
# RAISED 16384 -> 32768 (Jon, 2026-07-24) on measured evidence. On the Slice 0
# bucket-A arm 8% of rows truncated at 16384; the failure mode is a TOTAL LOSS,
# not a short answer -- rg131 (Blood Moon + Life and Limb) spent the entire cap
# on thinking twice over and returned a 98-char degrade sentinel. Re-run at
# 32768 it answered correctly.
#
# The point is margin, not size. rg131's recovered run used 12,550 output
# tokens -- UNDER the old cap. Adaptive thinking length is stochastic (rg87
# drew 12,419 then 10,206; rg130 drew 15,712 then 7,266 on identical config),
# so the old cap had no headroom for the tail of that distribution and a
# variance spike fell off a cliff. Raising it is close to free: you are billed
# for tokens generated, so only the runs that would have died cost more.
GEN_MAX_TOKENS = 32768

# Non-streaming requests are refused by the SDK when it ESTIMATES from
# max_tokens that the call could exceed ~10 minutes -- which 32768 does. An
# explicit per-request timeout suppresses that guard, so this constant is not
# optional decoration: GEN_MAX_TOKENS cannot be raised without it, and setting
# one without the other breaks every production call.
#
# 900s is ~7x the slowest generation observed at 32768 (132s), so it is
# generous for real work while still bounding a hung connection -- relevant
# because a stalled call inside a long unattended eval batch blocks the queue.
# Streaming remains the better long-term fix (residuals, rg3391); this is the
# cheap one and it leaves the messages.parse() structured-output path alone.
GEN_REQUEST_TIMEOUT = 900.0

# The largest max_tokens the SDK will accept on a NON-streaming call without an
# explicit timeout. Derived from anthropic._base_client
# ._calculate_nonstreaming_timeout: it raises when
# (3600 * max_tokens / 128_000) > 600, i.e. above 128_000 * 600 / 3600.
# Recomputed here rather than hardcoded so the reasoning is auditable; it is
# used only for a fail-fast construction check, never to size a request.
_SDK_NONSTREAMING_MAX_TOKENS = int(128_000 * 600 / 3600)
TOP_K = 15  # pure-vector top-15 (raised from 10: near-miss rules like a
# multiplayer clause at rank ~13 were just outside the old window)

PROMPT_VERSION = 3
# Bump on EVERY change to SYSTEM or the Answer schema, and note what changed.
# Stamped into the public-demo query log so feedback stays interpretable
# across deploys (plan-limitations-and-deploy.md L8).
#
# ALL SYSTEM texts are kept and selectable via SYSTEM_VERSIONS below, the same
# way rewrite.py keeps rw-v1 alongside rw-v2. A version that has been reverted
# in production must stay a fully runnable prompt, not a historical comment --
# the A/B harness needs to generate from it (docs/plan-v5-symbol-injection.md
# Slice 1). PROMPT_VERSION selects which one production ships.
#
#   v1: through the 31/31 grade + trust-the-ruling + transcript-in-message.
#   v2: L8 batch -- tldr, suggested_followups, cite-rulings-by-label.
#   v3: docs/plan-prompt-tuning.md Sec 1 (Jon-approved 2026-07-22) -- six
#   bullets targeting F1 full-card-names, F2 mana-symbol semantics, F4
#   multiplayer defaults (replaces the old bullet), F5 timing-assumption
#   disclosure, F7 card-text-overrides-rules, and F3/F6 direct-answer-first.
#   *** CURRENT PRODUCTION *** -- see the v4 note below.
#   v4: docs/plan-prompt-v4.md (Jon-approved 2026-07-23, six rulings) -- 4a
#   REPLACES the v3 mana bullet with a full Scryfall/CR-notation legend
#   (CORE tier: generic/colorless/colored/hybrid/Phyrexian/{X}/tap/untap,
#   REFERENCE tier: energy/snow/loyalty, both build-time-verified against
#   the Comprehensive Rules per ruling #6, plus a no-lecture guard and the
#   retained mana-arithmetic worked example per ruling #3); 4b revises the
#   multiplayer bullet (defending player(s) plurality); 4c adds a
#   generalized assumption-disclosure bullet ALONGSIDE the unchanged v3
#   timing bullet (ruling #5 -- not merged); 4d adds an
#   answer-the-intended-question bullet before the direct-answer bullet;
#   4e appends a no-false-starts clause to that bullet; 3b adds a short
#   redundant-emphasis assumption-disclosure clause to the intro paragraph.
#   NOT IN PRODUCTION -- shipped 2026-07-23, REVERTED 2026-07-25 after its
#   own A/B failed the go criterion: sonnet 46 -> 46 with ZERO divergence
#   across all 50 questions and both runs, for ~+1,215 tokens on every query
#   (no prompt caching exists on either path, so that is paid in full), and
#   gpt-5-mini 45 -> 43. It never moved c014, the mana-arithmetic failure the
#   legend was built for. Retained here because the v5 grid generates from it
#   (evals/report-v4e.md, DECISIONS.md 2026-07-25).

# Plan #3a: the winning rewriter config from evals/run_eval.py's 2x2 grid
# (rewrite count x rewriter model, see docs/plan-3a-query-rewriting.md).
# Kept as module constants -- not inlined below -- so picking a different
# cell later is a one-line change here rather than a code change.
REWRITE_MODEL = "claude-haiku-4-5"
# Multi-query. Jon ruled 3 on 2026-07-26, OVERRIDING A NULL RESULT: measured
# against v3 gold at production TOP_K=15, groups@15 went 16.5% (n=1, the
# previous production value) -> 20.3% (n=3), paired +10/-4, for +$0.0005 per
# question with generation cost unchanged. That +3.8pp is BELOW the 7pp bar
# fixed before the run, so this is a cost-benefit call on a nearly-free and
# trivially revertible change, not a cleared bar. Recorded as such because the
# bar existing and being missed is part of the result.
#
# n=1 is still better at the very top (groups@5: 8.9% vs 3.8%); n=3 wins deeper,
# and at TOP_K=15 it is ahead only just.
#
# Raising this above 1 also ACTIVATES A PREVIOUSLY DORMANT PRODUCTION PATH --
# the RRF fusion branch in answer() runs only when REWRITE_N > 1, so production
# retrieval now fuses several rankings instead of taking one. That path was
# exercised by the retrieval evals, not by production traffic.
#
# NOT reachable from the CLI: run_answer_eval.py's --rewrite-version sets the
# PROMPT version, not the count, and answer() reads this module constant
# directly -- so this cannot be A/B'd on ANSWERS today, only on retrieval
# recall. Threading it as a constructor param + --rewrite-n (the pattern
# `effort` and `cache_prompt` already follow) is what that would take.
REWRITE_N = 3
REWRITE_FUSION_DEPTH = 100  # candidates pulled per rewrite before RRF fusion
# when REWRITE_N > 1 -- matches evals/run_eval.py's DEPTH, so production
# retrieval is fused at the same depth the eval actually measured, not a
# smaller ad hoc one.

SYSTEM_V3 = (
    "You are a Magic: The Gathering rules expert. Answer the user's question "
    "using ONLY the numbered rules provided in the context below. Rules are "
    "labeled with their number in brackets, e.g. [104.3a].\n"
    # 1a (F1 card-role confusion) -- new first bullet, before the old [1].
    "- Always refer to a card by its exact full name, every time you mention "
    "it in your reasoning and in the answer text -- never by a role word "
    "(\"the attacker,\" \"the blocker,\" \"the creature,\" \"it\") once two or "
    "more named cards are in the question. If you find yourself about to "
    "write a role word for a card, stop and substitute its full name "
    "instead.\n"
    "- Cite the exact rule numbers you relied on in the citations field. Every "
    "rule number you reference anywhere in the answer text MUST also appear in "
    "the citations field, and whenever answered is true the citations field MUST "
    "be non-empty -- that field is what makes the answer verifiable, so an "
    "answer that relies on rules can never leave it blank. If you genuinely "
    "cannot ground the answer in any provided rule, set answered to false "
    "instead of answering without citations.\n"
    "- If the provided rules don't contain enough to answer, set answered to "
    "false and say what's missing -- do NOT fill the gap with outside "
    "knowledge or guesses.\n"
    "- Define any key term the question hinges on (e.g. what 'phasing' means) "
    "so the answer stands on its own.\n"
    # 1b (F2 mana-symbol semantics) -- new, right after the define-key-term
    # bullet.
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
    # 1c (F4 multiplayer defaults) -- REPLACES the old "If the provided rules
    # cover multiplayer or Commander cases..." bullet.
    "- Unless the question specifies exactly two players, don't assume a "
    "two-player game. If the provided context includes any rule about "
    "multiplayer play (choosing a defending player, \"each opponent,\" turn "
    "order among more than two players, etc.), say how the answer differs, if "
    "at all, between two players and more than two. If the context contains "
    "ONLY two-player-framed rules, say plainly that your answer is for the "
    "two-player case and that a multiplayer table may follow different rules "
    "-- do not invent multiplayer rules that weren't provided.\n"
    "- Keep the answer accurate and to the point; a player should be able to "
    "act on it.\n"
    # 1d (F5 unstated timing/ordering assumptions) -- new, right after the
    # accurate-and-to-the-point bullet.
    "- If the order or timing of events in the question is ambiguous (for "
    "example, exactly when damage was marked relative to a spell being cast "
    "or resolving), say plainly which timing you're assuming, then add one "
    "short sentence on how the answer would change under a different timing. "
    "Never resolve an ambiguous timing question as if only one order were "
    "possible without saying so.\n"
    "- You may also be given specific cards' oracle text and rulings, "
    "labeled \"Card data\" below the rules context. Treat that as additional "
    "ground truth alongside the rules -- if you rely on a card, cite it by "
    "name in the citations field, the same way you cite rule numbers.\n"
    # 1e (F7 card-text-overrides-rules) -- new, right after the card-data
    # bullet.
    "- A card's own printed rules text always wins over a general rule it "
    "contradicts. If a card's text says something that conflicts with how a "
    "general rule would otherwise apply, follow the card's text and say so "
    "explicitly (name the specific text and note that card text overrides "
    "the general rule) rather than applying the general rule as if the card "
    "were silent.\n"
    "- A provided ruling is itself authoritative, self-sufficient grounding. If "
    "a ruling directly states what happens in the interaction, rely on it and "
    "answer -- do NOT decline or hedge just because the underlying numbered rule "
    "isn't also in the context. (You still must not invent rules or rulings that "
    "weren't provided.)\n"
    "- Card rulings in the context are labeled like \"[Card Name ruling #4]\". "
    "When you rely on a ruling, put that exact label in the citations field, "
    "the same way you cite rule numbers.\n"
    # 1f (F3 intent misses + F6 answer clarity, merged) -- new, right after
    # the ruling-label bullet and before tldr.
    "- Open the text field with a direct, unmistakable answer to the "
    "question -- the first sentence or two should say plainly what happens, "
    "not lead with caveats or setup. Put reasoning, assumptions, and "
    "secondary discussion after that direct answer, never before it. If the "
    "question can reasonably be read two ways (for example, \"who gets "
    "priority\" could mean right after a spell is cast or right after it "
    "resolves), answer the reading actually asked first and explicitly, then "
    "briefly cover the other reading if it's a likely point of confusion -- "
    "don't let a second reading delay or bury the direct answer to the "
    "first.\n"
    "- Fill the tldr field with one or two plain sentences that directly answer "
    "the question for a player in a hurry -- no rule numbers, no hedging "
    "boilerplate. If answered is false, the tldr plainly says the provided "
    "rules don't settle it.\n"
    "- Fill suggested_followups with two or three short natural next questions "
    "a curious player might ask after reading this answer, each under about "
    "twelve words."
)

SYSTEM_V4 = (
    "You are a Magic: The Gathering rules expert. Answer the user's question "
    "using ONLY the numbered rules provided in the context below. Rules are "
    "labeled with their number in brackets, e.g. [104.3a]. State assumptions "
    "when the context doesn't cover something.\n"
    # 3b (TheJudge-derived redundant-emphasis technique, plan-prompt-v4.md
    # Sec 3 row 3b) -- short intro-paragraph restatement of the assumption-
    # disclosure behavior that 4c states in full below; a deliberate repeat,
    # not a duplicate instruction.
    # 1a (F1 card-role confusion) -- new first bullet, before the old [1].
    "- Always refer to a card by its exact full name, every time you mention "
    "it in your reasoning and in the answer text -- never by a role word "
    "(\"the attacker,\" \"the blocker,\" \"the creature,\" \"it\") once two or "
    "more named cards are in the question. If you find yourself about to "
    "write a role word for a card, stop and substitute its full name "
    "instead.\n"
    "- Cite the exact rule numbers you relied on in the citations field. Every "
    "rule number you reference anywhere in the answer text MUST also appear in "
    "the citations field, and whenever answered is true the citations field MUST "
    "be non-empty -- that field is what makes the answer verifiable, so an "
    "answer that relies on rules can never leave it blank. If you genuinely "
    "cannot ground the answer in any provided rule, set answered to false "
    "instead of answering without citations.\n"
    "- If the provided rules don't contain enough to answer, set answered to "
    "false and say what's missing -- do NOT fill the gap with outside "
    "knowledge or guesses.\n"
    "- Define any key term the question hinges on (e.g. what 'phasing' means) "
    "so the answer stands on its own.\n"
    # 4a (docs/plan-prompt-v4.md Sec 2, ruling #6) -- REPLACES v3's 1b mana
    # bullet in place, same insert point, right after the define-key-term
    # bullet. Full Scryfall/CR notation legend, two tiers: CORE (mana math +
    # tap/untap symbols -- these all appear in the eval corpus) and
    # REFERENCE (energy/snow/loyalty -- not exercised by the current 19-
    # question card eval, shipped as deploy-insurance for the fuller card
    # pool per ruling #6, labeled as such). Every symbol below was verified
    # against the live Comprehensive Rules text at build time (Scryfall's
    # own card-symbols doc returned HTTP 403 to a live fetch), never from
    # model memory -- see the implementation report for the per-symbol
    # source list. No-lecture guard included per ruling #6 (Opus-4.x
    # lesson: a glossary in the prompt makes models explain notation
    # unprompted). The mana-arithmetic bullet and its worked example are
    # ruling #3's retained v3-style worked example, now folded into the
    # legend rather than standing alone. Fix-loop correction (review pass):
    # the hybrid sentence originally implied both halves of every hybrid
    # are "one mana of a color," which is false for the numeral half of a
    # monocolored hybrid like {2/B} -- CR 107.4e's own wording ("either one
    # black mana or two mana of any type") is now folded in as a general
    # clause plus the monocolored case, per repo CR copy `data/raw/
    # MagicCompRules 20260619.txt` line 504. Second fix-loop pass: the
    # colorless-hybrid/hybrid-Phyrexian/{C/P}/{H} families, the mana-value
    # counting rule, and the REFERENCE-tier rare/non-mana symbols below are
    # all sourced from Scryfall's "Colors and Costs" API doc
    # (https://scryfall.com/docs/api/colors) -- that page 403s an automated
    # fetch, so the controller retrieved it through a real browser and
    # supplied the verbatim table; not independently fetched here.
    "- Notation legend, CORE tier (for interpreting the mana costs and "
    "abilities in the rules and card data below -- do not recite, define, "
    "or lecture about any of these symbols to the user unless they "
    "explicitly ask what a symbol means): {N} where N is a plain number "
    "means N generic mana, payable with any color or with colorless mana. "
    "{C} means colorless mana specifically -- it is NOT generic and is "
    "never satisfied by colored mana. {W}/{U}/{B}/{R}/{G} each mean one "
    "mana of that single color. A hybrid symbol such as {W/U} is itself a "
    "colored symbol and means the cost can be paid with one mana of EITHER "
    "named color. More generally, a hybrid symbol is paid in one of the "
    "two ways shown by its two halves -- a monocolored hybrid symbol such "
    "as {2/B} can be paid with either one mana of that color or two mana "
    "of any type. A Phyrexian symbol such as {W/P} is also a colored "
    "symbol and means the cost can be paid with one mana of that color OR "
    "by paying 2 life instead. The same two-halves pattern extends "
    "further: a colorless hybrid symbol such as {C/W} is paid with one "
    "colorless mana or one mana of the named color; a hybrid Phyrexian "
    "symbol such as {W/U/P} is paid with one mana of either named color "
    "or 2 life; {C/P} is paid with one colorless mana or 2 life; and {H} "
    "is paid with one colored mana of any color, or 2 life. {X} is a "
    "variable fixed when the spell or ability is cast or activated -- "
    "resolve X to its actual value before doing any of the arithmetic "
    "below. {T} in a cost means \"tap this permanent\"; {Q} means \"untap "
    "this permanent.\" A cost written as {2}{U}{U} is 2 generic + 2 blue "
    "= 4 total mana, never \"4 mana of any color.\" For a mana value or "
    "total-cost COUNT (as opposed to what you actually pay): every "
    "hybrid symbol -- two-color, colorless, or hybrid Phyrexian alike -- "
    "counts as 1 no matter which half would be paid; a monocolored "
    "hybrid such as {2/W} counts as 2; and {X}, {Y}, and {Z} count as 0 "
    "wherever the object isn't on the stack.\n"
    "- Cost math: a cost-REDUCTION effect (\"this costs {1} less\") only "
    "lowers the generic portion and never goes below {0} generic -- it "
    "cannot touch colored or {C} symbols. A cost-INCREASE effect that sets "
    "a floor on the total cost (read the card's own wording for exactly "
    "how it's phrased -- don't assume a specific card's wording without "
    "seeing it) applies to the TOTAL mana paid, not just the generic part. "
    "When more than one cost-changing effect applies, apply them one at a "
    "time in the order described by the rules provided, and always restate "
    "the final total cost broken out by symbol, not just a lump number. "
    "Worked example: a spell that costs {1}{G}{G} (3 total: 1 generic + 2 "
    "green) with a \"spells cost {1} less\" effect becomes {G}{G} (2 total "
    "-- the 1 generic mana is gone, the 2 green mana is untouched); if a "
    "total-cost floor of 3 also applies, the total goes back up to 3 "
    "(typically {1}{G}{G} again, since the floor cares about the total "
    "mana count, not which symbols make it up).\n"
    "- Notation legend, REFERENCE tier (not exercised by the current eval "
    "question set -- included as deploy-insurance for the fuller card "
    "pool; the same no-lecture rule applies): {E} means one energy counter "
    "-- paying {E} removes one energy counter from yourself. {S} in a cost "
    "means it can be paid with one mana of any type produced by a snow "
    "source -- snow is not itself a color or a type of mana. A loyalty "
    "symbol on a planeswalker ability, written [+N], [-N], or [0], means "
    "put N loyalty counters on the permanent for [+N] and [0], or remove N "
    "loyalty counters for [-N]; a loyalty ability with a negative cost "
    "can't be activated unless the permanent already has at least that "
    "many loyalty counters on it. Rarer mana symbols on unusual cards: "
    "{L} means one mana from a legendary source; {Y} and {Z} work like "
    "{X} as extra variables. Non-mana symbols that can appear in card "
    "text: {PW} marks a planeswalker, {CHAOS} is the Chaos symbol, "
    "{A} is an acorn counter, {TK} is a ticket counter, and {D} "
    "means one potential land drop. A bare {P} with no color letter is a "
    "MODAL BUDGET PAWPRINT, NOT Phyrexian mana -- Phyrexian mana always "
    "has a color component, as in {W/P} or {W/U/P}.\n"
    "- Name the specific zones, steps, or objects involved rather than "
    "referring to them vaguely (e.g. the command zone and exile are separate "
    "zones).\n"
    # 4b (docs/plan-prompt-v4.md Sec 2) -- REVISES v3's 1c multiplayer
    # bullet in place, same insert point. Jon's verbatim wording: state each
    # outcome separately (not just "differs, if at all"), "defending
    # player(s)" plurality, don't over-claim beyond what's provided.
    "- If the outcome would be different assuming a multiplayer game "
    "compared to a two-player game, state each outcome separately and say "
    "which is which. If the outcome is the same regardless of player "
    "count, say that plainly instead of silently defaulting to a "
    "two-player framing. When referring to who defends or is affected, say "
    "\"defending player(s)\" (plural-aware) rather than assuming there is "
    "exactly one, since some multiplayer variants can have more than one. "
    "If the provided context only contains two-player-framed rules, say "
    "your answer is for the two-player case and that a multiplayer table "
    "may follow different rules -- do not invent multiplayer rules that "
    "weren't provided.\n"
    "- Keep the answer accurate and to the point; a player should be able to "
    "act on it.\n"
    # 1d (F5 unstated timing/ordering assumptions) -- new, right after the
    # accurate-and-to-the-point bullet.
    "- If the order or timing of events in the question is ambiguous (for "
    "example, exactly when damage was marked relative to a spell being cast "
    "or resolving), say plainly which timing you're assuming, then add one "
    "short sentence on how the answer would change under a different timing. "
    "Never resolve an ambiguous timing question as if only one order were "
    "possible without saying so.\n"
    # 4c (docs/plan-prompt-v4.md Sec 2, ruling #5) -- NEW bullet, added
    # ALONGSIDE 1d immediately above, which stays unchanged and separate.
    # Jon ruled these must not be merged ("timing is incredibly important
    # in the game of Magic") -- 4c generalizes assumption-disclosure to any
    # unstated fact, accepting the minor overlap with 1d's timing case.
    "- When the answer depends on a fact the question doesn't state (an "
    "unknown mana value, an unspecified zone, an ambiguous order or "
    "timing, an uncertain player count, etc.), say plainly what you "
    "assumed instead of silently picking one option. If a different "
    "assumption would change the answer, add one short sentence on how. "
    "This is disclosure, not a request for more information -- answer "
    "with your best assumption stated, don't ask the question back to the "
    "user.\n"
    "- You may also be given specific cards' oracle text and rulings, "
    "labeled \"Card data\" below the rules context. Treat that as additional "
    "ground truth alongside the rules -- if you rely on a card, cite it by "
    "name in the citations field, the same way you cite rule numbers.\n"
    # 1e (F7 card-text-overrides-rules) -- new, right after the card-data
    # bullet.
    "- A card's own printed rules text always wins over a general rule it "
    "contradicts. If a card's text says something that conflicts with how a "
    "general rule would otherwise apply, follow the card's text and say so "
    "explicitly (name the specific text and note that card text overrides "
    "the general rule) rather than applying the general rule as if the card "
    "were silent.\n"
    "- A provided ruling is itself authoritative, self-sufficient grounding. If "
    "a ruling directly states what happens in the interaction, rely on it and "
    "answer -- do NOT decline or hedge just because the underlying numbered rule "
    "isn't also in the context. (You still must not invent rules or rulings that "
    "weren't provided.)\n"
    "- Card rulings in the context are labeled like \"[Card Name ruling #4]\". "
    "When you rely on a ruling, put that exact label in the citations field, "
    "the same way you cite rule numbers.\n"
    # 4d (docs/plan-prompt-v4.md Sec 2) -- NEW bullet, immediately before
    # 1f. Targets c019/q008: figure out which question is actually being
    # asked before opening with a direct answer to it.
    "- Answer the practical question a player is actually asking, not only "
    "the narrowest literal reading of the words. If the situation clearly "
    "involves resolving multiple copies or instances of an effect and the "
    "literal wording could be read as asking about just one, answer the "
    "practical version (e.g. the total after everything resolves) first, "
    "and only note the narrower literal reading afterward if it's "
    "genuinely ambiguous which one was meant.\n"
    # 1f (F3 intent misses + F6 answer clarity, merged) -- new, right after
    # the ruling-label bullet and before tldr. 4e (docs/plan-prompt-v4.md
    # Sec 2) appends the no-false-starts clause below, same bullet.
    "- Open the text field with a direct, unmistakable answer to the "
    "question -- the first sentence or two should say plainly what happens, "
    "not lead with caveats or setup. Put reasoning, assumptions, and "
    "secondary discussion after that direct answer, never before it. If the "
    "question can reasonably be read two ways (for example, \"who gets "
    "priority\" could mean right after a spell is cast or right after it "
    "resolves), answer the reading actually asked first and explicitly, then "
    "briefly cover the other reading if it's a likely point of confusion -- "
    "don't let a second reading delay or bury the direct answer to the "
    "first. Never write a claim in the text field that you're about to "
    "contradict a sentence later -- work out the right answer before "
    "writing, then write only that; if you catch a false start, discard it "
    "rather than \"correcting\" it in place.\n"
    "- Fill the tldr field with one or two plain sentences that directly answer "
    "the question for a player in a hurry -- no rule numbers, no hedging "
    "boilerplate. If answered is false, the tldr plainly says the provided "
    "rules don't settle it.\n"
    "- Fill suggested_followups with two or three short natural next questions "
    "a curious player might ask after reading this answer, each under about "
    "twelve words."
)


# CR 613.6 + 611.3a, pasted verbatim from
# data/raw/MagicCompRules 20260619.txt (read with encoding="utf-8-sig").
# This is the Slice 0 CONTROL ARM intervention (plan-layer-system-tool.md
# Sec 6.1) -- deliberately minimal: the two rule texts plus one framing
# clause, no coaching or worked examples. A heavily-coached bullet would be
# a different intervention than the one Sec 6.1 specifies, and a win by it
# would not be interpretable as "the prompt bullet works".
LAYERS_CR_BULLET = (
    "When reasoning about continuous effects and the layer system, apply "
    "these rules exactly as written:\n"
    "613.6. If an effect should be applied in different layers and/or "
    "sublayers, the parts of the effect each apply in their appropriate "
    "ones. If an effect starts to apply in one layer and/or sublayer, it "
    "will continue to be applied to the same set of objects in each other "
    "applicable layer and/or sublayer, even if the ability generating the "
    "effect is removed during this process.\n"
    "611.3a A continuous effect generated by a static ability isn’t "
    "“locked in”; it applies at any given moment to whatever its "
    "text indicates."
)

SYSTEM_V3_613 = SYSTEM_V3 + "\n" + LAYERS_CR_BULLET


# v4nl == v5 plan's "cell C" (docs/plan-v5-symbol-injection.md Sec 3/5a):
# v4's bullets 4b/4c/4d/4e and the 3b intro clause, MINUS the per-symbol
# notation legend (both CORE and REFERENCE tiers). Derived by copying
# SYSTEM_V4 verbatim and cutting two things: (1) the "Notation legend,
# REFERENCE tier" bullet, removed whole -- it is pure per-symbol
# definitions, no arithmetic guidance; (2) the "Notation legend, CORE
# tier" bullet, reduced to ONLY its trailing mana-value-COUNT sentence --
# the rest of that bullet (what {N}/{C}/{W}.../hybrid/Phyrexian/{X}/{T}/
# {Q} each individually mean, plus the "{2}{U}{U} = 4 total" illustration)
# is per-symbol definition content and moves to SYMBOL_DEFS below instead.
# The separate "Cost math: a cost-REDUCTION effect..." bullet is untouched
# -- arithmetic guidance, not a definition, per the plan's own distinction.
# Every other bullet (1a, cite, define-key-term, zones, accurate-and-to-
# -the-point, 1d timing, card-data, 1e card-text-overrides, ruling-
# authoritative, ruling-label, tldr, suggested_followups) is copy-pasted
# unchanged from SYSTEM_V4 -- nothing here is retyped prose.
SYSTEM_V4NL = (
    "You are a Magic: The Gathering rules expert. Answer the user's question "
    "using ONLY the numbered rules provided in the context below. Rules are "
    "labeled with their number in brackets, e.g. [104.3a]. State assumptions "
    "when the context doesn't cover something.\n"
    "- Always refer to a card by its exact full name, every time you mention "
    "it in your reasoning and in the answer text -- never by a role word "
    "(\"the attacker,\" \"the blocker,\" \"the creature,\" \"it\") once two or "
    "more named cards are in the question. If you find yourself about to "
    "write a role word for a card, stop and substitute its full name "
    "instead.\n"
    "- Cite the exact rule numbers you relied on in the citations field. Every "
    "rule number you reference anywhere in the answer text MUST also appear in "
    "the citations field, and whenever answered is true the citations field MUST "
    "be non-empty -- that field is what makes the answer verifiable, so an "
    "answer that relies on rules can never leave it blank. If you genuinely "
    "cannot ground the answer in any provided rule, set answered to false "
    "instead of answering without citations.\n"
    "- If the provided rules don't contain enough to answer, set answered to "
    "false and say what's missing -- do NOT fill the gap with outside "
    "knowledge or guesses.\n"
    "- Define any key term the question hinges on (e.g. what 'phasing' means) "
    "so the answer stands on its own.\n"
    # The only surviving piece of the CORE-tier notation legend bullet --
    # everything before this sentence in SYSTEM_V4 was a per-symbol
    # definition and moved to SYMBOL_DEFS.
    "- For a mana value or total-cost COUNT (as opposed to what you actually "
    "pay): every hybrid symbol -- two-color, colorless, or hybrid Phyrexian "
    "alike -- counts as 1 no matter which half would be paid; a monocolored "
    "hybrid such as {2/W} counts as 2; and {X}, {Y}, and {Z} count as 0 "
    "wherever the object isn't on the stack.\n"
    "- Cost math: a cost-REDUCTION effect (\"this costs {1} less\") only "
    "lowers the generic portion and never goes below {0} generic -- it "
    "cannot touch colored or {C} symbols. A cost-INCREASE effect that sets "
    "a floor on the total cost (read the card's own wording for exactly "
    "how it's phrased -- don't assume a specific card's wording without "
    "seeing it) applies to the TOTAL mana paid, not just the generic part. "
    "When more than one cost-changing effect applies, apply them one at a "
    "time in the order described by the rules provided, and always restate "
    "the final total cost broken out by symbol, not just a lump number. "
    "Worked example: a spell that costs {1}{G}{G} (3 total: 1 generic + 2 "
    "green) with a \"spells cost {1} less\" effect becomes {G}{G} (2 total "
    "-- the 1 generic mana is gone, the 2 green mana is untouched); if a "
    "total-cost floor of 3 also applies, the total goes back up to 3 "
    "(typically {1}{G}{G} again, since the floor cares about the total "
    "mana count, not which symbols make it up).\n"
    # Notation legend, REFERENCE tier -- removed whole (pure definitions).
    "- Name the specific zones, steps, or objects involved rather than "
    "referring to them vaguely (e.g. the command zone and exile are separate "
    "zones).\n"
    "- If the outcome would be different assuming a multiplayer game "
    "compared to a two-player game, state each outcome separately and say "
    "which is which. If the outcome is the same regardless of player "
    "count, say that plainly instead of silently defaulting to a "
    "two-player framing. When referring to who defends or is affected, say "
    "\"defending player(s)\" (plural-aware) rather than assuming there is "
    "exactly one, since some multiplayer variants can have more than one. "
    "If the provided context only contains two-player-framed rules, say "
    "your answer is for the two-player case and that a multiplayer table "
    "may follow different rules -- do not invent multiplayer rules that "
    "weren't provided.\n"
    "- Keep the answer accurate and to the point; a player should be able to "
    "act on it.\n"
    "- If the order or timing of events in the question is ambiguous (for "
    "example, exactly when damage was marked relative to a spell being cast "
    "or resolving), say plainly which timing you're assuming, then add one "
    "short sentence on how the answer would change under a different timing. "
    "Never resolve an ambiguous timing question as if only one order were "
    "possible without saying so.\n"
    "- When the answer depends on a fact the question doesn't state (an "
    "unknown mana value, an unspecified zone, an ambiguous order or "
    "timing, an uncertain player count, etc.), say plainly what you "
    "assumed instead of silently picking one option. If a different "
    "assumption would change the answer, add one short sentence on how. "
    "This is disclosure, not a request for more information -- answer "
    "with your best assumption stated, don't ask the question back to the "
    "user.\n"
    "- You may also be given specific cards' oracle text and rulings, "
    "labeled \"Card data\" below the rules context. Treat that as additional "
    "ground truth alongside the rules -- if you rely on a card, cite it by "
    "name in the citations field, the same way you cite rule numbers.\n"
    "- A card's own printed rules text always wins over a general rule it "
    "contradicts. If a card's text says something that conflicts with how a "
    "general rule would otherwise apply, follow the card's text and say so "
    "explicitly (name the specific text and note that card text overrides "
    "the general rule) rather than applying the general rule as if the card "
    "were silent.\n"
    "- A provided ruling is itself authoritative, self-sufficient grounding. If "
    "a ruling directly states what happens in the interaction, rely on it and "
    "answer -- do NOT decline or hedge just because the underlying numbered rule "
    "isn't also in the context. (You still must not invent rules or rulings that "
    "weren't provided.)\n"
    "- Card rulings in the context are labeled like \"[Card Name ruling #4]\". "
    "When you rely on a ruling, put that exact label in the citations field, "
    "the same way you cite rule numbers.\n"
    "- Answer the practical question a player is actually asking, not only "
    "the narrowest literal reading of the words. If the situation clearly "
    "involves resolving multiple copies or instances of an effect and the "
    "literal wording could be read as asking about just one, answer the "
    "practical version (e.g. the total after everything resolves) first, "
    "and only note the narrower literal reading afterward if it's "
    "genuinely ambiguous which one was meant.\n"
    "- Open the text field with a direct, unmistakable answer to the "
    "question -- the first sentence or two should say plainly what happens, "
    "not lead with caveats or setup. Put reasoning, assumptions, and "
    "secondary discussion after that direct answer, never before it. If the "
    "question can reasonably be read two ways (for example, \"who gets "
    "priority\" could mean right after a spell is cast or right after it "
    "resolves), answer the reading actually asked first and explicitly, then "
    "briefly cover the other reading if it's a likely point of confusion -- "
    "don't let a second reading delay or bury the direct answer to the "
    "first. Never write a claim in the text field that you're about to "
    "contradict a sentence later -- work out the right answer before "
    "writing, then write only that; if you catch a false start, discard it "
    "rather than \"correcting\" it in place.\n"
    "- Fill the tldr field with one or two plain sentences that directly answer "
    "the question for a player in a hurry -- no rule numbers, no hedging "
    "boilerplate. If answered is false, the tldr plainly says the provided "
    "rules don't settle it.\n"
    "- Fill suggested_followups with two or three short natural next questions "
    "a curious player might ask after reading this answer, each under about "
    "twelve words."
)


# The registry. Add a version here and it is immediately runnable by both
# production (via PROMPT_VERSION) and the A/B harness (via an explicit
# version argument) -- evals/build_prompts_variant.py takes a version name
# rather than importing whatever `SYSTEM` currently happens to be bound to,
# so the eval instrument is not coupled to what production ships today.
SYSTEM_VERSIONS: dict[int | str, str] = {
    3: SYSTEM_V3,
    4: SYSTEM_V4,
    "v4nl": SYSTEM_V4NL,
    # Slice 0 harness control-arm intervention (docs/spec-slice0-harness.md
    # Task 2a) -- v3 plus the CR 613.6/611.3a bullet, nothing else.
    "v3+613": SYSTEM_V3_613,
}

# What production actually sends. Kept as a module-level name so every
# existing import site (build_prompt, the OpenRouter arms, the identity
# fixture) keeps working unchanged.
SYSTEM = SYSTEM_VERSIONS[PROMPT_VERSION]


# Slice 2, selective symbol injection (docs/plan-v5-symbol-injection.md
# Sec 5a). SYMBOL_DEFS is v4's CORE+REFERENCE notation legend (SYSTEM_V4,
# untouched above) decomposed to one entry per symbol -- reused VERBATIM,
# never re-derived from memory, since the wording was build-time-verified
# against the repo's own CR and Scryfall's Colors-and-Costs doc (see the
# SYSTEM_V4 comment block). Where the legend states several symbols in one
# semicolon/comma-joined sentence (e.g. the colorless-hybrid / hybrid-
# Phyrexian / {C/P} / {H} sentence), each clause is split into its own
# entry with only mechanical edits: a leading lowercase "a" -> "A" when a
# clause becomes sentence-initial, and the joining semicolon/comma -> a
# period. No clause's wording was rewritten. Two exceptions, both
# deliberate:
#   - The {2}{U}{U} "= 4 total mana, never 4 mana of any color" sentence
#     is dropped. It doesn't define a NEW symbol (both {2}/generic and
#     {U}/color are already covered above) -- it's a worked illustration,
#     and cutting it is the ambiguous edge of "only definitions move"
#     (see the implementation report).
#   - The loyalty-symbol sentence ("written [+N], [-N], or [0]...") is
#     dropped from this dict. It uses SQUARE brackets, not curly braces,
#     so it can never be matched by _symbols_present's `\{[^}]{1,8}\}`
#     regex -- keeping it here would be a dead entry no code path can ever
#     reach. Flagged in the implementation report rather than silently
#     included.
# Dict order is the canonical legend order (CORE tier, then REFERENCE
# tier) and doubles as _collapse_families's output order -- one source of
# truth, no separate ordering list to drift out of sync.
SYMBOL_DEFS: dict[str, str] = {
    "generic": (
        "{N} where N is a plain number means N generic mana, payable with "
        "any color or with colorless mana."
    ),
    "{C}": (
        "{C} means colorless mana specifically -- it is NOT generic and is "
        "never satisfied by colored mana."
    ),
    "{W}": "{W}/{U}/{B}/{R}/{G} each mean one mana of that single color.",
    "{U}": "{W}/{U}/{B}/{R}/{G} each mean one mana of that single color.",
    "{B}": "{W}/{U}/{B}/{R}/{G} each mean one mana of that single color.",
    "{R}": "{W}/{U}/{B}/{R}/{G} each mean one mana of that single color.",
    "{G}": "{W}/{U}/{B}/{R}/{G} each mean one mana of that single color.",
    "hybrid": (
        "A hybrid symbol such as {W/U} is itself a colored symbol and "
        "means the cost can be paid with one mana of EITHER named color. "
        "More generally, a hybrid symbol is paid in one of the two ways "
        "shown by its two halves."
    ),
    "monocolored_hybrid": (
        "A monocolored hybrid symbol such as {2/B} can be paid with "
        "either one mana of that color or two mana of any type."
    ),
    "phyrexian": (
        "A Phyrexian symbol such as {W/P} is also a colored symbol and "
        "means the cost can be paid with one mana of that color OR by "
        "paying 2 life instead."
    ),
    "colorless_hybrid": (
        "A colorless hybrid symbol such as {C/W} is paid with one "
        "colorless mana or one mana of the named color."
    ),
    "hybrid_phyrexian": (
        "A hybrid Phyrexian symbol such as {W/U/P} is paid with one mana "
        "of either named color or 2 life."
    ),
    "{C/P}": "{C/P} is paid with one colorless mana or 2 life.",
    "{H}": "{H} is paid with one colored mana of any color, or 2 life.",
    "{X}": (
        "{X} is a variable fixed when the spell or ability is cast or "
        "activated -- resolve X to its actual value before doing any of "
        "the arithmetic below."
    ),
    "{T}": "{T} in a cost means \"tap this permanent\".",
    "{Q}": "{Q} means \"untap this permanent.\"",
    "{E}": (
        "{E} means one energy counter -- paying {E} removes one energy "
        "counter from yourself."
    ),
    "{S}": (
        "{S} in a cost means it can be paid with one mana of any type "
        "produced by a snow source -- snow is not itself a color or a "
        "type of mana."
    ),
    "{L}": "{L} means one mana from a legendary source.",
    "{Y}": "{Y} and {Z} work like {X} as extra variables.",
    "{Z}": "{Y} and {Z} work like {X} as extra variables.",
    "{PW}": "{PW} marks a planeswalker.",
    "{CHAOS}": "{CHAOS} is the Chaos symbol.",
    "{A}": "{A} is an acorn counter.",
    "{TK}": "{TK} is a ticket counter.",
    "{D}": "{D} means one potential land drop.",
    "{P}": (
        "A bare {P} with no color letter is a MODAL BUDGET PAWPRINT, NOT "
        "Phyrexian mana -- Phyrexian mana always has a color component, "
        "as in {W/P} or {W/U/P}."
    ),
}

_SYMBOL_RE = re.compile(r"\{[^}]{1,8}\}")
_MANA_COLORS = {"W", "U", "B", "R", "G"}


def _symbols_present(text: str) -> set[str]:
    """Every distinct `{...}` token in `text`, 1-8 chars inside the braces
    (matches everything from `{X}` to `{CHAOS}`). No semantic filtering --
    that's _collapse_families's job."""
    return set(_SYMBOL_RE.findall(text))


def _classify_symbol(raw: str) -> str | None:
    """Map one raw `{...}` token to its SYMBOL_DEFS key, or None if it
    isn't a symbol this dict defines (e.g. an Un-set half-mana/infinity
    symbol, or anything else not in the legend -- silently dropped, never
    guessed at)."""
    inner = raw[1:-1]
    if inner.isdigit():
        return "generic"
    if inner in _MANA_COLORS:
        return f"{{{inner}}}"
    if inner == "C/P":
        return "{C/P}"
    if inner in ("C", "X", "Y", "Z", "T", "Q", "H", "E", "S", "L", "PW",
                 "CHAOS", "A", "TK", "D", "P"):
        return f"{{{inner}}}"
    parts = inner.split("/")
    if len(parts) == 2:
        a, b = parts
        if a in _MANA_COLORS and b in _MANA_COLORS:
            return "hybrid"
        if a.isdigit() and b in _MANA_COLORS:
            return "monocolored_hybrid"
        if a in _MANA_COLORS and b == "P":
            return "phyrexian"
        if a == "C" and b in _MANA_COLORS:
            return "colorless_hybrid"
    elif len(parts) == 3:
        a, b, c = parts
        if a in _MANA_COLORS and b in _MANA_COLORS and c == "P":
            return "hybrid_phyrexian"
    return None


def _collapse_families(symbols: set[str]) -> list[str]:
    """The ten two-color hybrids collapse to ONE 'hybrid' entry; likewise
    Phyrexian (5), hybrid Phyrexian (10), {C/x} colorless hybrids (5),
    {2/x} monocolored hybrids (5), and generic numerals {0}..{20} (one
    'generic' entry). Returns SYMBOL_DEFS keys, in the dict's own
    (legend) order, so the emitted block reads CORE-tier-then-REFERENCE-
    tier regardless of the input set's arbitrary order."""
    present = {_classify_symbol(s) for s in symbols}
    present.discard(None)
    return [key for key in SYMBOL_DEFS if key in present]


def _symbol_reference_block(symbols: set[str]) -> str:
    """"" when `symbols` is empty (or contains nothing SYMBOL_DEFS
    defines) -- zero symbols, zero tokens. Otherwise one definition line
    per collapsed family/symbol, verbatim from SYMBOL_DEFS. The five
    colored-mana keys ({W}/{U}/{B}/{R}/{G}) share one identical sentence
    in v4's source text (it names all five colors at once) -- deduped
    here by TEXT, not just by key, so e.g. a card with both {B} and {G}
    gets that sentence once, not twice. Paying for the same sentence
    twice is exactly the waste this slice exists to cut."""
    keys = _collapse_families(symbols)
    seen: set[str] = set()
    lines = []
    for k in keys:
        d = SYMBOL_DEFS[k]
        if d not in seen:
            seen.add(d)
            lines.append(d)
    if not lines:
        return ""
    body = "\n".join(f"- {d}" for d in lines)
    return f"Symbol reference (notation used in the cards/question above):\n{body}"


def _card_symbol_text(cards: list[Card]) -> str:
    """mana_cost + oracle_text off every card AND every face (a modal DFC's
    top-level mana_cost is empty -- each face carries its own), joined into
    one scan target for _symbols_present. Never includes retrieved rules
    context -- see the WHY comment in build_prompt."""
    parts = []
    for c in cards:
        parts.append(c.mana_cost)
        parts.append(c.oracle_text)
        for f in c.faces:
            parts.append(f.mana_cost)
            parts.append(f.oracle_text)
    return " ".join(parts)


# --- calculate_cost tool (docs/plan-cost-calculator-tool.md Sec 3b) --------
#
# The codebase's first real model-facing tool-use round trip. The plan's own
# spike (docs/spike-tool-use-findings.md) settled the SDK-level question --
# `client.messages.parse(tools=..., output_format=Answer)` needs no separate
# "tools-off final call"; the same call shape is reissued each round of
# RulesAgent.answer()'s tool loop below.
#
# Gated behind a deterministic per-question TRIGGER (_needs_cost_tool),
# rather than attached on every call: production's non-tool path must stay
# byte-behaviour-identical (task requirement), which a tool schema + extra
# system sentence on EVERY call would break, and the plan's own Sec 6/8
# flags that a round trip is not free and needs measuring rather than
# assuming free on every query. This mirrors the existing precedent for
# "when" -- the selective symbol-injection seam at build_prompt (Sec 3b.3
# cites this exact precedent) -- rather than the plan's alternative reading
# (an always-on system sentence with tools always attached); that reading
# was rejected here specifically because it cannot satisfy "byte-identical
# on the non-tool path."
CALCULATE_COST_TOOL = {
    "name": "calculate_cost",
    "description": (
        "Given a spell or ability's base mana cost and a list of "
        "cost-modifying effects you have already identified from the rules "
        "and card text (each labeled reduction, increase, or floor_total, "
        "with an amount and a short cite), computes the exact resulting "
        "cost per CR 601.2f -- optionally across a range of {X} values. "
        "This tool does NOT decide which effects apply or what kind they "
        "are -- identify that from the provided rules/card data first, "
        "then call this only for the arithmetic. Never state a combined "
        "or compared cost without calling this tool when more than one "
        "cost-modifying effect is in play."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "base_cost": {
                "type": "object",
                "description": "The printed base mana cost, decomposed.",
                "properties": {
                    "generic": {"type": "integer", "minimum": 0},
                    "colored": {
                        "type": "object",
                        "properties": {
                            c: {"type": "integer", "minimum": 0}
                            for c in ("W", "U", "B", "R", "G", "C")
                        },
                        "additionalProperties": False,
                    },
                    "x_coefficient": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Number of {X} symbols in the printed cost (0 if none).",
                    },
                },
                "required": ["generic", "colored", "x_coefficient"],
                "additionalProperties": False,
            },
            "modifiers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["reduction", "increase", "floor_total"],
                        },
                        "amount": {"type": "integer", "minimum": 1},
                        "cite": {"type": "string"},
                    },
                    "required": ["kind", "amount", "cite"],
                    "additionalProperties": False,
                },
            },
            "x_values": {
                "type": ["array", "null"],
                "items": {"type": "integer", "minimum": 0},
                "description": "Required (non-empty) when base_cost.x_coefficient > 0.",
            },
        },
        "required": ["base_cost", "modifiers"],
        "additionalProperties": False,
    },
}

TOOL_TRIGGER_SENTENCE = (
    "- When a question requires combining more than one cost-changing "
    "effect, or comparing a cost across different values of {X}, call "
    "calculate_cost with the modifiers you've identified (each labeled "
    "reduction, increase, or floor_total) rather than doing that "
    "arithmetic yourself."
)

# --- resolve_layers tool (docs/plan-layer-system-tool.md Sec 3a/9, Slice 4) -
#
# The model-facing schema for the layer-system resolver engine
# (tools/layer_resolver.py, Slices 1-3). Same discipline as CALCULATE_COST_
# TOOL above: this tool never decides which layer an effect belongs to,
# never assigns a timestamp, and never decides whether a dependency exists
# (CR 613.8a) -- those stay the model's job (plan Sec 2/4). The description
# quotes CR 613.6 and 613.8a verbatim, per the plan's own reasoning (Sec 4,
# last paragraph): putting the rule text in the tool description guarantees
# it's in context exactly when a layers question is being answered, which is
# the retrieval gap rg633 exposed.
RESOLVE_LAYERS_TOOL = {
    "name": "resolve_layers",
    "description": (
        "Given an object's base characteristics (its copiable values, post-"
        "layer-1) and a list of continuous-effect parts you have already "
        "identified from the rules and card text -- each already assigned "
        "to a CR 613 layer/sublayer, grouped under the ability (source_id) "
        "that produces it, and given a relative timestamp -- applies them "
        "in CR 613 order and returns the resulting characteristics plus a "
        "per-step trace. This tool does NOT read oracle text, does NOT "
        "decide which layer an effect belongs to, does NOT assign "
        "timestamps, and does NOT decide whether a dependency exists "
        "between two effects -- identify all of that from the provided "
        "rules/card data first, then call this only for the ordering "
        "bookkeeping. "
        "CR 613.6: 'If an effect starts to apply in one layer and/or "
        "sublayer, it will continue to be applied to the same set of "
        "objects in each other applicable layer and/or sublayer, even if "
        "the ability generating the effect is removed during this "
        "process.' "
        "CR 613.8a: an effect depends on another if (a) it's applied in "
        "the same layer (and sublayer) as the other effect; (b) applying "
        "the other would change the text or existence of the first "
        "effect, what it applies to, or what it does to any of the "
        "things it applies to; and (c) neither effect is from a "
        "characteristic-defining ability or both effects are from "
        "characteristic-defining abilities. Declare a dependency only "
        "when this test is actually met, and say why in "
        "dependency_reason -- do not assert an ordering as a shortcut."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "base": {
                "type": ["object", "null"],
                "description": "The object's copiable values, post-layer-1.",
                "properties": {
                    "name": {"type": "string"},
                    "card_types": {"type": "array", "items": {"type": "string"}},
                    "supertypes": {"type": "array", "items": {"type": "string"}},
                    "subtypes": {"type": "array", "items": {"type": "string"}},
                    "colors": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["W", "U", "B", "R", "G"]},
                    },
                    "abilities": {"type": "array", "items": {"type": "string"}},
                    "power": {"type": ["integer", "null"]},
                    "toughness": {"type": ["integer", "null"]},
                    "controller": {"type": ["string", "null"]},
                },
                "required": ["card_types", "supertypes", "subtypes", "colors", "abilities"],
            },
            "effects": {
                "type": "array",
                "description": (
                    "Flat list of effect parts. Parts sharing a source_id "
                    "are one ability split across layers (CR 613.6)."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Unique part id, e.g. 'e1c'."},
                        "source_id": {
                            "type": "string",
                            "description": "The ability this part comes from.",
                        },
                        "layer": {
                            "type": "string",
                            "enum": ["2", "4", "5", "6", "7a", "7b", "7c", "7d"],
                        },
                        "timestamp": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Relative order only.",
                        },
                        "is_cda": {
                            "type": "boolean",
                            "description": "Feeds CR 613.3/613.4a ordering (CDAs first).",
                        },
                        "source_on_this_object": {
                            "type": "boolean",
                            "description": (
                                "True if this part's source_id is itself an "
                                "ability of the object being resolved (so a "
                                "later remove_abilities part can strip it, "
                                "per CR 613.6) -- false for an ability that "
                                "lives on a different object, e.g. Muraganda "
                                "Petroglyphs affecting a creature."
                            ),
                        },
                        "depends_on": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": "Part ids this part depends on, per CR 613.8a.",
                        },
                        "dependency_reason": {
                            "type": ["string", "null"],
                            "description": "Required whenever depends_on is non-empty.",
                        },
                        "operation": {
                            "type": "object",
                            "description": (
                                "A closed union, one shape per layer: layer "
                                "2 {kind:set_controller,value}; layer 4 "
                                "{kind:set_types|add_types|remove_types,"
                                "card_types,subtypes,supertypes}; layer 5 "
                                "{kind:set_colors|add_colors,value}; layer 6 "
                                "{kind:add_abilities|remove_abilities|"
                                "remove_all_abilities|cant_have_abilities,"
                                "value}; layer 7a {kind:cda_pt,power,"
                                "toughness}; layer 7b {kind:set_pt,power,"
                                "toughness}; layer 7c {kind:modify_pt,power,"
                                "toughness} (signed; counters use this); "
                                "layer 7d {kind:switch_pt}."
                            ),
                        },
                        "applies_if": {
                            "type": ["object", "null"],
                            "description": (
                                "Optional conditional applicability -- "
                                "exactly one of: has_no_abilities (bool), "
                                "has_ability (string), has_color (one of "
                                "W/U/B/R/G), has_type (string), has_subtype "
                                "(string), power_gte (integer), evaluated "
                                "against live state at the moment of "
                                "application. Plus an optional 'expect' "
                                "boolean -- what you expect it to evaluate "
                                "to; a mismatch comes back as a warning, "
                                "not a refusal."
                            ),
                        },
                        "cite": {"type": "string", "description": "CR/oracle cite."},
                    },
                    "required": ["id", "source_id", "layer", "timestamp", "operation"],
                },
            },
        },
        "required": ["base", "effects"],
        "additionalProperties": False,
    },
}

LAYERS_TRIGGER_SENTENCE = (
    "- When a question asks what an object's characteristics (power/"
    "toughness, colors, types, subtypes, or abilities) end up being, and "
    "more than one continuous effect from the layer system (CR 613) could "
    "be interacting on it -- especially CR 613.6 (an effect that already "
    "started applying keeps applying even if the ability generating it is "
    "later removed) -- call resolve_layers with the effect parts you've "
    "identified (grouped by source ability, assigned to a layer, and "
    "timestamped) rather than working out the layer interaction yourself."
)

TOOL_ROUND_CAP = 4
# Guard against a confused model looping (plan Sec 3d / spike Sec 3): round
# trips = tool calls + 1, and the spike observed clean 2-3-round convergence
# on a toy tool. Raised from 3 to 4 per docs/plan-layer-system-tool.md Sec
# 8.3 (Jon's ruling): rounds 0-2 are tool-capable and round 3 is the
# forced-answer round (is_last_round = TOOL_ROUND_CAP - 1, so the
# cap-exhaustion guard below moves with the cap instead of being pinned to
# round 2). 4 covers one chained pair of tool calls (spike Case B) plus the
# terminal structured-Answer turn, with headroom for a resolve_layers
# self-correcting second call; calculate_cost's real use case (one call per
# question) converges in 2. Not measured at production complexity -- see
# the report's "if messier than the spike" note.

_COST_TRIGGER_RE = re.compile(r"costs?\s*\{?\d+\}?\s*(less|more)\b", re.IGNORECASE)

# Change B (docs/report-costtool-validation.md Stage 2, rg289): calculate_cost
# computes a PAID cost via CR 601.2f -- the wrong instrument for a question
# asking how much mana an ability ADDS (produces), e.g. Ice Cauldron's second
# ability "Add this artifact's last noted type and amount of mana." rg289's
# card text tripped the old trigger ({X} from Ice Cauldron's activation cost
# + "cost {2} more" from Suppression Field), but the question itself is about
# production, not payment. Scoped to the QUESTION text only, never card
# oracle text -- oracle text routinely contains "Add {mana}" templating on
# perfectly legitimate cost questions too (a mana rock's own line, alongside
# an unrelated cost-modifier card), so scanning cards here would risk
# excluding a real cost question. Narrow phrasing ("how much/many mana ...
# add") rather than a bare "add" keyword, so it doesn't accidentally match
# Converge/color-count questions (rg6636/rg6916), which never use "add" --
# they ask what something COSTS or how much to PAY. A false negative here
# just means the model does the arithmetic in prose as before (no
# regression), so narrow is the safe direction per this trigger's own
# docstring philosophy.
_MANA_PRODUCTION_RE = re.compile(
    r"how (?:much|many) mana\b.{0,60}?\badd(?:s|ed|ing)?\b", re.IGNORECASE | re.DOTALL
)


def _is_mana_production_question(question: str) -> bool:
    """True for a "how much mana does X add" shape (rg289) -- see the
    _MANA_PRODUCTION_RE comment above for why this is scoped to the
    question text only and to this narrow phrasing."""
    return bool(_MANA_PRODUCTION_RE.search(question))


def _needs_cost_tool(question: str, cards: list[Card]) -> bool:
    """Deterministic v1 trigger: fires only when BOTH an {X} symbol AND a
    cost-reduction/increase phrase ("costs {N} less/more") are present in
    the cards' oracle text/mana costs or the question -- the shape of a
    genuine multi-modifier cost question (c014: "...cost {1} less... cast
    it with X=0..."). Deliberately narrow, not an exhaustive detector of
    every possible cost-math question: a false negative just means the
    model does the arithmetic in prose as it does today (no regression);
    a false positive costs one extra system sentence + tool schema on that
    call. Reuses the same cards+question text _symbols_present already
    scans for symbol injection, so this never diverges from what the model
    can already see. Additionally excludes mana-PRODUCTION questions (Change
    B, rg289) -- see _is_mana_production_question. Converge/color-count
    questions (rg6636/rg6916) are genuine multi-modifier {X}-cost firings
    and are NOT excluded."""
    text = f"{_card_symbol_text(cards)} {question}"
    if "{X}" not in _symbols_present(text):
        return False
    if not _COST_TRIGGER_RE.search(text):
        return False
    return not _is_mana_production_question(question)


# --- resolve_layers trigger (docs/plan-layer-system-tool.md Sec 3c, plus the
# "CALIBRATION RESULT" subsection that supersedes the section's original
# proposal) ------------------------------------------------------------------
#
# Two conjuncts, mirroring _needs_cost_tool's own shape. Rules vocabulary
# ("layer", "timestamp", "depends") is essentially ABSENT from real layers
# questions (measured: 0-1 of 51 bucket-A rows), so conjunct 1 looks for the
# CHARACTERISTIC-READOUT shape a layers question actually takes ("what are
# its power and toughness", "does X have flying") -- which is far too wide on
# its own, since that is also just an ordinary Magic question shape. Conjunct
# 2 is what makes this a layers detector rather than a bare "characteristics"
# detector: at least one loaded card's oracle text (ALL faces -- see
# _oracle_all_faces) has to carry continuous-effect-shaped text.
#
# Copied VERBATIM from the plan's shipped (calibrated) version -- measured at
# 77.8% bucket-A recall / 5.1% non-layers firing over the full corpus. Do NOT
# retune here; the plan is the source of truth for these patterns.
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

# Conjunct 2: at least ONE loaded card carries continuous-effect-shaped
# static text. (Threshold was >= 2 as originally proposed; RULED down to
# >= 1 by Jon 2026-07-24 after calibration -- see the plan's "CALIBRATION
# RESULT" subsection.)
_CONTINUOUS_EFFECT_RE = re.compile(
    r"gets?\s*[+-]\d+/[+-]\d+"
    r"|\b(?:base power and toughness|loses? all abilities|can't have)\b"
    r"|\b(?:becomes?|are|is)\b.{0,30}?\b(?:creature|land|artifact|enchantment)s?\b"
    r"|\bhave\b.{0,20}?\bbase\b"
    r"|\b(?:are|becomes?|is)\b.{0,30}?\b(?:Mountains?|Islands?|Swamps?|Forests?|Plains)\b",
    re.IGNORECASE | re.DOTALL,
)


def _oracle_all_faces(c: Card) -> str:
    """Newline-joined union of every face's oracle text. Plan Sec 3c's
    Slice-4 note: the trigger's pseudocode reads `_oracle_all_faces(c)`, not
    `c.oracle_text` -- oracle text on this project's Card contract is
    per-face (`Card.faces[i].oracle_text`); the top-level `oracle_text`
    field happens to carry a joined value today (tools/scryfall.py), but the
    faces union is the contract-correct read and is what the plan's
    calibration measured against."""
    return "\n".join(f.oracle_text for f in c.faces if f.oracle_text)


def _needs_layers_tool(question: str, cards: list[Card]) -> bool:
    """Calibrated two-conjunct trigger, copied verbatim from
    docs/plan-layer-system-tool.md Sec 3c CALIBRATION RESULT. Conjunct 1: the
    question asks for a characteristic readout. Conjunct 2: at least one
    loaded card's oracle text (all faces) carries continuous-effect-shaped
    static text. Both conjuncts required -- see the module comment above."""
    if not _LAYERS_READOUT_RE.search(question):
        return False
    hits = sum(1 for c in cards if _CONTINUOUS_EFFECT_RE.search(_oracle_all_faces(c)))
    return hits >= 1


def _run_calculate_cost(input_: dict) -> dict:
    """Dispatch one calculate_cost tool_use block. calculate_cost() itself
    never raises on malformed input (returns {"ok": False, "error": ...});
    this also guards against a tool_use block whose `input` doesn't even
    have the expected keys (e.g. base_cost missing entirely), same
    broad-except posture as get_card's own fetch-error handling
    (tools/scryfall.py) -- a tool-dispatch crash must never take down the
    whole generation call."""
    try:
        return calculate_cost(
            base_cost=input_.get("base_cost"),
            modifiers=input_.get("modifiers") or [],
            x_values=input_.get("x_values"),
        )
    except Exception as e:  # pragma: no cover - defensive
        return {"ok": False, "error": f"calculate_cost failed on malformed input: {e!r}"}


def _run_resolve_layers(input_: dict) -> dict:
    """Dispatch one resolve_layers tool_use block. resolve_layers() itself
    never raises on malformed input -- it returns {"ok": False, "error":
    ...} for every refusal (plan Sec 3b: duplicate part ids, an illegal
    operation.kind for its layer, a non-integer timestamp, an unresolvable
    timestamp tie, a malformed applies_if, a depends_on with no
    dependency_reason, etc.), and this dispatcher passes that dict straight
    through UNCHANGED -- it never adds a second layer of error handling that
    reinterprets or swallows an engine refusal. The try/except below only
    guards the one case the engine itself cannot: a tool_use block whose
    `input` doesn't even have the expected top-level shape (e.g. `input_`
    isn't a dict at all), the same defensive posture as _run_calculate_cost
    above."""
    try:
        return resolve_layers(
            base=input_.get("base"),
            effects=input_.get("effects") or [],
        )
    except Exception as e:  # pragma: no cover - defensive
        return {"ok": False, "error": f"resolve_layers failed on malformed input: {e!r}"}


# Name-routed tool dispatch (docs/plan-layer-system-tool.md Sec 3d must-fix
# 4): the dispatch loop below used to call _run_calculate_cost
# unconditionally on any tool_use block, which was safe only because there
# had ever been exactly one registered tool. Routing by block.name means a
# second tool can be registered here later without touching the loop, and an
# unrecognized name gets an explicit {"ok": False, ...} tool_result instead
# of silently being fed to the wrong handler.
_TOOL_DISPATCH = {
    "calculate_cost": _run_calculate_cost,
    "resolve_layers": _run_resolve_layers,
}


def _dispatch_tool_call(name: str, input_: dict) -> dict:
    handler = _TOOL_DISPATCH.get(name)
    if handler is None:
        return {"ok": False, "error": f"unknown tool: {name!r}"}
    return handler(input_)


def _format_context(retrieved: list[Retrieved]) -> str:
    return "\n\n".join(f"[{r.chunk.source_id}] {r.chunk.text}" for r in retrieved)


_RULING_LABEL_RE = re.compile(r"^\[.+? ruling #\d+\] ")


def label_rulings(card: Card, indices: list[int] | None = None) -> Card:
    """Return a copy of `card` whose rulings carry their citation labels.

    THE INVARIANT THIS EXISTS TO HOLD. The system prompt promises the model that
    "Card rulings in the context are labeled like [Card Name ruling #4]" and tells
    it to cite that exact label. Anything that renders cards without applying
    these labels ships a prompt that breaks its own promise, and the model has no
    option but to invent a numbering -- it counts the bullets 1-based, so the last
    ruling of an N-ruling card is cited as #N, one past the end of the 0-based
    scheme. That is exactly what happened to the derivability arms (69% of citing
    rows affected; docs/report-ruling-citation-offbyone.md), because the labelling
    lived in RulesAgent.answer() while the rendering lived in build_prompt().
    Labelling now happens at the boundary, so a future prompt builder cannot
    reintroduce the defect by not knowing it had to.

    `indices` selects a SUBSET of `card.rulings` by original Scryfall index -- the
    selection path, where the model sees a few rulings but must cite them by the
    index that maps back to `ruling_id()` and the gold `oracle_id#index`. None
    labels every ruling with its own position, which is correct when the whole
    list is present (union / dump-all).

    **Idempotent by design.** `answer()` labels a filtered subset before calling
    build_prompt(), which labels again; an already-labelled ruling is returned
    untouched, so production prompts stay byte-identical (guarded by
    tests/test_prompt_identity.py) and double labels are impossible.
    """
    src = card.rulings
    picks = range(len(src)) if indices is None else indices
    out = [
        src[i] if _RULING_LABEL_RE.match(src[i]) else f"[{card.name} ruling #{i}] {src[i]}"
        for i in picks
    ]
    return card.model_copy(update={"rulings": out})


def build_prompt(question: str, retrieved: list[Retrieved], cards: list[Card],
                 convo_ctx: str | None = None,
                 rewrite_queries: list[str] | None = None,
                 system_override: str | None = None) -> tuple[str, str]:
    """Assemble the exact (system, user) prompt pair the generator is called
    with. Extracted from RulesAgent.answer() (plan-openrouter-models.md) so
    the OpenRouter A/B arms generate from the byte-identical prompt the
    pinned Anthropic path sees -- tests/fixtures/prompt_identity.json guards
    that this stays true. `convo_ctx` is the condensed transcript (None =
    single-turn); `rewrite_queries` is the show_rewrite transparency block
    (None = off, the shipped default). `system_override` (docs/spec-slice0-
    harness.md Task 2b): when given, used as the base system string instead
    of the module-level SYSTEM -- lets RulesAgent's system_version knob
    thread a different registered SYSTEM_VERSIONS entry through without
    touching this function's default behaviour. None (the default)
    preserves today's behaviour byte-for-byte: every existing caller
    (evals/build_prompts_variant.py, evals/build_prompts_v4.py,
    evals/run_openrouter_arm.py, the identity fixtures) omits this argument
    and keeps generating from SYSTEM exactly as before."""
    context = _format_context(retrieved)
    user = f"Rules context:\n{context}"
    if cards:
        # Card data goes in AFTER the rules context, per Jon's call in
        # the plan -- it enriches generation, it never touches
        # retrieval or the (unchanged) rewrite step.
        #
        # Label at the boundary, not in the caller: every prompt builder routes
        # through here, so the citation labels the system prompt promises cannot
        # go missing for a caller that didn't know to add them. Idempotent, so
        # answer()'s subset labelling (with original indices) passes through
        # untouched. See label_rulings().
        user += f"\n\nCard data:\n{_format_cards([label_rulings(c) for c in cards])}"
    # Slice 2, selective symbol injection (docs/plan-v5-symbol-injection.md
    # Sec 5a). Scan ONLY the cards (mana_cost + oracle_text, every face)
    # and the question text -- NEVER `context`/`retrieved`, the assembled
    # rules-context string above.
    #
    # WHY cards-not-context: CR 107.4 is a single chunk enumerating every
    # mana symbol in the game, so if that chunk (or any rules chunk that
    # happens to quote a symbol in passing) is ever retrieved, a
    # context-wide scan would inject MORE of the legend than the static
    # v4 dictionary did -- worse than what this slice exists to fix.
    # Measured, not argued: on c014's frozen user block (docs/plan-v5-
    # symbol-injection.md Sec 2), the whole assembled block contains 8
    # distinct symbols; the card block alone contains 6. The 2-symbol
    # difference comes from the rules context, which the cards and
    # question never asked about.
    #
    # WHY no rewriter guard is needed: rewrite_query() runs (in
    # RulesAgent.answer(), well before this function is called) BEFORE
    # build_prompt() assembles anything -- there is no code path where the
    # rewriter can see this injected block, so no flag/guard is needed to
    # keep it structurally invisible to the rewriter.
    #
    # Card-less questions still get scanned (Jon's ruling #7: inject when
    # a symbol appears in the question with no card attached), so this is
    # NOT nested inside `if cards:` above -- the block is anchored
    # immediately before "\n\nQuestion:" either way.
    symbols = _symbols_present(f"{_card_symbol_text(cards)} {question}")
    symbol_block = _symbol_reference_block(symbols)
    if symbol_block:
        user += f"\n\n{symbol_block}"
    user += f"\n\nQuestion: {question}"
    if rewrite_queries is not None:
        # Jon's idea: let the generator see BOTH the user's own words and
        # the reinterpretation retrieval actually searched on, so the
        # stronger model can notice when they've drifted apart. A
        # transparency/faithfulness lever, not a recall one -- see the
        # show_rewrite flag notes in RulesAgent.__init__.
        searched = "\n".join(f"- {q}" for q in rewrite_queries)
        user += (
            f"\n\nFor context: to search the rules, that question was "
            f"reinterpreted as:\n{searched}\n"
            "Answer the question the user actually asked. If the "
            "reinterpretation drifted from their intent, or the rules "
            "retrieved answer a broader or narrower question than they "
            "asked, say so plainly rather than answering the "
            "reinterpretation."
        )
    system = system_override if system_override is not None else SYSTEM
    if convo_ctx is not None:
        # Appends onto `system` (the already-resolved override-or-SYSTEM
        # value from above), not a hardcoded SYSTEM -- byte-identical to the
        # old `SYSTEM + (...)` for every existing caller (system_override is
        # always None there, so `system` already equals SYSTEM at this
        # point), but correctly composes with a real system_override too.
        system = system + (
            "\n- This conversation has earlier turns, provided as a "
            "transcript at the top of the message. Read the final question "
            "in their context -- it may refine or correct an earlier one -- "
            "but ground the answer ONLY in the rules and card data provided."
        )
        user = f"Conversation so far (for context only):\n{convo_ctx}\n\n{user}"
    return system, user


def _degenerate(a: Answer) -> bool:
    """A parseable draw that is nonetheless a non-answer: declined, cited
    nothing, and said almost nothing. Deliberately narrow so an HONEST decline
    -- answered=false with a real explanation of what's missing (200+ chars
    across the eval history) -- never matches. The 80-char bound clears the
    observed degenerate specimens (0 and ~70 chars, 2026-07-22) with margin."""
    if not a.answered:
        return not a.citations and len(a.text.strip()) < 80
    # answered=True but no actual content: q029 (2026-07-21, L1 gate 4) drew
    # answered:true with fully blank text. Deliberately blank-only (not a
    # length threshold) so a legitimately short answered=True answer never
    # matches -- that's the only shape observed.
    return not a.text.strip()


# --- malformed-answer guard (phase-1 cost-tool repro follow-up) -----------
#
# The terminal tool_choice=none fix (TOOL_ROUND_CAP loop above) eliminated
# empty-output cap-exhaustion, but 7 of 24 phase-1 generations then shipped
# `answered=True` GARBLED text instead -- a shape `_degenerate()` never
# catches, since it only inspects blank/near-blank text. Confirmed real
# examples, evals/_phase1_costtool_repro_AFTER.log (rg6636 rep0/1/2/3, rg897
# rep2, rg6916 rep2): chat-template/scratchpad leakage
# (".. assistantfinal{"), and bare fragments ("content", "Not needed", ",",
# ",-.text field..{|answ|>"). Two of the seven (rg6636 rep2's "Cite
# N-------A 27,]ards)..." word salad and c014 rep0's "with, X=0 t
# m={0,..." word-salad-with-real-tokens) are deliberately left uncaught --
# see the docstring below for why catching them risks a real-answer false
# positive.
_MALFORMED_MARKERS = (
    "assistantfinal",
    "the above thinking is chatter",
    "now write final",
    "actual final answer below",
    "completed inline in json",
)

_MALFORMED_MIN_LEN = 30
# High-precision bare-fragment threshold. Every fragment fixture above tops
# out at 23 chars (",-.text field..{|answ|>"); every real (coherent) answer
# observed across the whole eval history is 100+ chars -- the SYSTEM prompt
# itself requires a direct answer plus reasoning/definitions/citations
# whenever answered=True, so a genuine answer this short essentially never
# occurs. 30 leaves 3x+ margin below the shortest real answer on record
# while safely catching every known bare-fragment specimen.


def _malformed(text: str) -> bool:
    """High-precision detector for GARBLED (not merely blank) answer text:
    chat-template/scratchpad leakage, or a bare fragment with no
    substantive content. `text` is the RAW model draw -- callers must check
    this BEFORE the Scryfall attribution is appended (RulesAgent.answer()
    does). Deliberately narrow: word-salad that still contains real prose
    tokens (rg6636 rep2, c014 rep0) is NOT matched here, since a length or
    marker check loose enough to catch it risks matching a genuinely short
    or terse-but-real answer instead -- see the guard's callsite comment in
    RulesAgent.answer() for why a coherent-but-uncited answer must never
    match this (that stays the separate last_uncited_success path)."""
    stripped = text.strip()
    lowered = stripped.lower()
    if any(marker in lowered for marker in _MALFORMED_MARKERS):
        return True
    return len(stripped) < _MALFORMED_MIN_LEN


def _face_block(f: CardFace, label: str = "") -> str:
    """One face rendered as a header line (name, cost, type, P/T or loyalty or
    defense, color indicator) followed by its oracle text."""
    header = label + f.name
    if f.mana_cost:
        header += f" {f.mana_cost}"
    attrs = []
    if f.type_line:
        attrs.append(f.type_line)
    if f.power != "" or f.toughness != "":
        attrs.append(f"{f.power}/{f.toughness}")
    if f.loyalty:
        attrs.append(f"loyalty {f.loyalty}")
    if f.defense:
        attrs.append(f"defense {f.defense}")
    if f.color_indicator:
        attrs.append("color indicator " + "/".join(f.color_indicator))
    if attrs:
        header += " -- " + " -- ".join(attrs)
    return header + (f"\n{f.oracle_text}" if f.oracle_text else "")


def _format_cards(cards: list[Card]) -> str:
    # Enrich with every printed, rules-relevant field, layout-first: a
    # single-faced card folds its card-level meta (mana value, color identity,
    # layout) onto its one header line; a multi-face card leads with the layout
    # + meta, then renders EACH face so the generator sees each face's own cost
    # and type (docs/plan-card-enrichment-fields.md).
    parts = []
    for c in cards:
        meta = []
        if c.layout and c.layout != "normal":
            meta.append(c.layout)
        meta.append(f"MV {c.mana_value:g}")
        if c.color_identity:
            meta.append("color identity " + "/".join(c.color_identity))
        meta_str = ", ".join(meta)

        lines = []
        if len(c.faces) > 1:
            lines.append(f"{c.name}  ({meta_str})")
            for i, f in enumerate(c.faces, 1):
                lines.append(_face_block(f, label=f"Face {i}: "))
        else:
            f = c.faces[0] if c.faces else CardFace(
                name=c.name, oracle_text=c.oracle_text,
                type_line=c.type_line, mana_cost=c.mana_cost,
            )
            first, _, rest = _face_block(f).partition("\n")
            lines.append(f"{first}  ({meta_str})")
            if rest:
                lines.append(rest)

        if c.rulings:
            lines.append("Rulings:")
            lines.extend(f"- {r}" for r in c.rulings)
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _cacheable_system(system: str, cache: bool):
    """The `system=` argument for the generation call.

    `cache` False -> the plain string, exactly what every prior run sent. This
    is the whole safety story: an agent constructed without cache_prompt= makes
    a byte-identical request, so no fixture, schema test, or historical number
    moves.

    `cache` True -> a one-block list carrying `cache_control: ephemeral`, which
    caches the tools+system prefix (render order is tools -> system ->
    messages). Cache writes cost 1.25x and reads 0.1x, so it pays back from the
    second question with the same prefix onward.

    Returns the string itself rather than a one-element list in the off case on
    purpose -- wrapping unconditionally would change the request body for every
    existing caller to no benefit.
    """
    if not cache:
        return system
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


class RulesAgent:
    def __init__(self, store: VectorStore, client: anthropic.Anthropic | None = None,
                 model: str = GEN_MODEL, k: int = TOP_K, rewrite: bool = True,
                 show_rewrite: bool = False, card_no_refresh: bool = False,
                 ruling_select: bool = True, rewrite_version: str = "v2",
                 ruling_query_mode: str = "raw", layers_tool: bool = True,
                 system_version: int | str = PROMPT_VERSION,
                 max_tokens: int = GEN_MAX_TOKENS,
                 request_timeout: float | None = GEN_REQUEST_TIMEOUT,
                 effort: str | None = None, cache_prompt: bool = False):
        self.store = store
        self.client = client or anthropic.Anthropic()
        # Generation output cap, and the per-request timeout override that
        # makes raising it possible at all.
        #
        # The comment at the generation call site says raising the cap "is not
        # the fix and actively backfires" because 32768 trips the SDK's
        # non-streaming 10-minute-timeout guard. That is accurate but
        # incomplete: the guard is an ESTIMATE the SDK makes from max_tokens,
        # and it is suppressible either by streaming or by passing an explicit
        # timeout. Streaming is the better long-term fix (residuals, rg3391);
        # this knob is the cheap one, and it leaves the structured-output
        # `messages.parse()` path completely unchanged.
        #
        # These two defaults MOVE TOGETHER or not at all. 32768 without a
        # timeout override is refused by the SDK before it ever reaches the
        # API; a timeout without the raised cap is harmless but pointless.
        # Passing request_timeout=None restores the SDK's own default and
        # will therefore break at GEN_MAX_TOKENS -- only do that alongside a
        # max_tokens low enough to clear the guard.
        self.max_tokens = max_tokens
        self.request_timeout = request_timeout
        # with_options() is an SDK affordance the scripted test doubles don't
        # implement (_ScriptedClient, _RecordingClient). Degrade to the client
        # as-is rather than requiring every fake to grow the method: a double
        # makes no HTTP request, so there is no timeout guard to suppress and
        # nothing to configure. Real clients always have it, so production
        # still gets the override it needs to run at GEN_MAX_TOKENS.
        self._gen_client = self.client
        if request_timeout is not None:
            with_options = getattr(self.client, "with_options", None)
            if with_options is not None:
                self._gen_client = with_options(timeout=request_timeout)
        elif max_tokens > _SDK_NONSTREAMING_MAX_TOKENS and hasattr(self.client, "with_options"):
            # Fail HERE, not 40 minutes into an unattended batch. The SDK's
            # messages.parse() refuses a non-streaming call whose max_tokens
            # implies >10 min (_calculate_nonstreaming_timeout), and it only
            # skips that check when a timeout is given per-request or the
            # client's own timeout differs from the SDK default. Passing
            # request_timeout=None explicitly (e.g. an argparse default) makes
            # the raised cap unusable, and the resulting ValueError surfaces
            # deep inside the generation call with no mention of this class.
            raise ValueError(
                f"max_tokens={max_tokens} exceeds the SDK's non-streaming limit of "
                f"~{_SDK_NONSTREAMING_MAX_TOKENS} but request_timeout is None. Pass a "
                f"request_timeout (production uses {GEN_REQUEST_TIMEOUT}s) or lower "
                f"max_tokens; otherwise messages.parse() raises at call time."
            )
        self.model = model
        # Generation effort (docs/spec-effort-and-norewrite.md Task 1).
        #
        # Measured cost is ~90% thinking tokens (rg3868 spent 10,622 output
        # tokens on a ~700-token answer), and every Anthropic call in this repo
        # has until now run at the API's default effort. This is the knob that
        # makes that cost expressible.
        #
        # None (the default) means the request body is BYTE-IDENTICAL to
        # before: _effort_kwargs stays empty, so no output_config key is added
        # at all and every existing caller/test/run-file is unaffected
        # (guarded by tests/test_prompt_identity.py).
        #
        # Validated HERE rather than at call time, same discipline as
        # system_version below and the max_tokens/request_timeout guard above:
        # an unknown level must never surface 40 minutes into an unattended
        # batch.
        #
        # Safe to merge with output_format=Answer: the SDK's messages.parse()
        # does `{**output_config, "format": transformed_output_format}`
        # (anthropic 0.117.0), so a caller-supplied effort survives into the
        # request body rather than being dropped or overwriting the schema.
        #
        # Deliberately NOT applied to the rewriter call: REWRITE_MODEL is
        # claude-haiku-4-5, which has no effort parameter at all.
        if effort is not None and effort not in GEN_EFFORT_LEVELS:
            raise ValueError(
                f"unknown effort {effort!r}; valid levels: {sorted(GEN_EFFORT_LEVELS)}"
            )
        self.effort = effort
        self._effort_kwargs: dict = (
            {"output_config": {"effort": effort}} if effort is not None else {}
        )
        # Prompt caching (Jon, 2026-07-25: "get prompt caching implemented
        # first so we can cut down ablation costs"). Same posture as `effort`
        # above: default False leaves `system=` a plain str, so the request is
        # BYTE-IDENTICAL to before and every existing fixture still matches.
        #
        # What gets cached: the whole system string, which is the tail of the
        # prefix (render order is tools -> system -> messages). Tools are
        # attached per-question by the cost/layers gates, so a run produces up
        # to four distinct prefixes (no tool / cost / layers / both) and each
        # caches independently -- that is correct, not a bug: a shared
        # breakpoint across differing tool sets would never hit.
        #
        # Worth it because SYSTEM alone is ~1,400 tokens, over Claude Opus 5's
        # 512-token cacheable minimum, and it is identical on every question.
        # The real payoff is ablation, which re-sends the same prefix hundreds
        # of times against one question.
        self.cache_prompt = cache_prompt
        self.k = k
        self.rewrite = rewrite
        self.show_rewrite = show_rewrite
        self.card_no_refresh = card_no_refresh
        self.ruling_select = ruling_select
        # Selectable rewriter prompt version (docs/plan-prompt-tuning.md Sec
        # 2, Task 1 in docs/plan-v3-execution-tasks.md), threaded straight
        # into every rewrite_query() call below -- "v1" (byte-identical to
        # the pre-v2 rewriter prompt) or "v2" (default; adds the mana-symbol
        # and multiplayer-phrasing bullets). The prompt-v3 A/B's condition B
        # runs gen-v3 + rewrite-v1 on purpose, so this must stay overridable
        # per agent instance, not hardcoded to the new default.
        self.rewrite_version = rewrite_version
        if ruling_query_mode not in ("raw", "union"):
            raise ValueError(f"ruling_query_mode must be 'raw' or 'union', got {ruling_query_mode!r}")
        # Part B ruling-query union toggle (docs/plan-l1-crossref-expansion.md
        # Part B; exposed for real generation here -- previously only
        # runnable as a measurement-only report via evals/run_openrouter_arm
        # .py's `--ruling-query union`, which never touched RulesAgent or a
        # generated answer). "raw" (default, unchanged): select_rulings()
        # scores each card's rulings against the bare question only. "union":
        # select_rulings_union() scores against the question UNIONED with the
        # rewriter's own rewrite phrasing(s), so a ruling can clear the
        # relevance floor via whichever angle actually matches it. Needs
        # `rewrite=True` to have any rewrites to union with; falls back to a
        # one-query union (just the question) when rewrite=False, which is
        # still a valid select_rulings_union() call.
        self.ruling_query_mode = ruling_query_mode
        # Slice 0 harness (docs/spec-slice0-harness.md Task 1): master
        # suppression switch for the resolve_layers tool, independent of
        # _needs_layers_tool's own calibrated trigger. Default True:
        # production behaviour is unchanged unless a caller explicitly opts
        # out (e.g. a Slice 0 control-arm run that must carry no layers
        # tool at all, so the base/control comparison is meaningful). The
        # cost tool deliberately has no equivalent switch -- it stays at its
        # production default in every arm so it's constant and can't
        # confound the comparison (spec Task 1).
        self.layers_tool = layers_tool
        # Slice 0 harness Task 2b: selectable system-prompt version,
        # independent of PROMPT_VERSION/SYSTEM (which stay pinned to what
        # production ships -- see the SYSTEM_VERSIONS registry comment).
        # Validated eagerly here (fail at construction) so an unknown key
        # never silently reaches a live API call.
        if system_version not in SYSTEM_VERSIONS:
            valid = sorted(SYSTEM_VERSIONS.keys(), key=str)
            raise ValueError(
                f"unknown system_version {system_version!r}; valid keys: {valid}"
            )
        self.system_version = system_version
        # Cross-ref expansion (L1, docs/plan-l1-crossref-expansion.md): id ->
        # Chunk, built ONCE here from the store's own chunks so expand_crossrefs
        # can resolve a "see rule X" mention without re-parsing the CR. Same
        # dict api/main.py used to build itself in its lifespan -- the agent is
        # now its one owner, and the API reads agent.chunk_map instead.
        # getattr-guarded: a store double that only implements .search() (e.g.
        # tests/test_prompt_identity.py's _FrozenStore) has no .chunks, and
        # should degrade to an empty map -- expand_crossrefs then resolves
        # nothing and appends nothing, an inert no-op -- rather than crash.
        self.chunk_map = {c.source_id: c for c in getattr(store, "chunks", [])}
        # Per-card ruling mini-RAG (plan-rulings-on-demand.md): when True (the
        # default), a referenced card's rulings are relevance-filtered against
        # the question instead of dumped wholesale. False restores the old
        # dump-all behavior, so the answer eval can A/B the two.
        self.last_ruling_selection: dict | None = None
        # {card name -> [ruling_id, ...]} chosen on the last answer() call (None
        # if ruling_select is off). Read by the rulings-recall eval, mirroring
        # last_rewritten.
        self.last_cards: list | None = None
        self.last_retrieved: list | None = None
        # Also recorded per answer() call, for the API to build an enriched
        # response: the resolved cards used (each already carrying its
        # mini-RAG-selected rulings) and the retrieved rule chunks. Not part of
        # the Answer contract -- read right after answer(), same pattern as
        # last_rewritten / last_ruling_selection.
        # Passed straight through to get_card()'s no_refresh -- eval-
        # reproducibility freeze mode (plan #3b): use any cached card entry
        # regardless of its TTL age, so a card eval re-run is byte-
        # identical instead of drifting if Scryfall adds a ruling mid-eval.
        # Default False: the live/interactive path wants TTL freshness.
        # show_rewrite (EXPERIMENTAL, default OFF): hand the generator the
        # rewrite alongside the user's original wording (see answer() below) so
        # it can flag when retrieval drifted from intent. Default off because
        # an early spot-check showed the extra instruction can make the model
        # cite rules in prose while leaving the structured `citations` field
        # empty -- which breaks the exact field the groundedness eval reads. A
        # flag, not hardcoded, so the answer eval can A/B it (--show-rewrite)
        # and only adopt it if it earns its keep. No effect when rewrite=False.
        # rewrite=True is the shipped default (plan #3a, Jon's "Decided:
        # always-on"): rewriting measurably helps retrieval and the honest
        # cost -- one extra LLM call plus ~1-2s of latency per question -- is
        # small enough to always pay rather than gate behind an overfit
        # confidence threshold. See docs/plan-3a-query-rewriting.md.
        self.last_rewritten = None
        # Set by answer() on every call when rewrite=True (None otherwise).
        # Not part of the Answer contract -- callers that need the rewrites
        # used or the clarification for a given answer (e.g.
        # evals/run_answer_eval.py, recording them alongside the answer)
        # read it right after calling answer() rather than answer() growing
        # a second return value.
        self.last_crossref: dict | None = None
        # Set by answer() on every call: {"refs_found": [...], "appended":
        # [...], "skipped": [...]} from expand_crossrefs -- so a label-like
        # ref that resolved to no chunk (e.g. 701.5 "Cast") is an observable
        # miss, not a silent one. Same pattern as last_rewritten.
        self.last_uncited_success: bool = False
        # Set by answer() on every call (Plan A amendment, docs/plan-q029-
        # empty-answer-guard.md header ruling 1, Jon 2026-07-23): True when
        # the final draw is answered=true but cites nothing -- "then it's
        # not grounding in the rules." Flag ONLY, never a retry trigger (a
        # legitimately card-only-grounded answer can look like this, so
        # auto-retrying risks false positives) -- surfaced via a warning log
        # and Debug.uncited_success so every ungrounded "success" is
        # auditable in telemetry.
        self.last_unresolved_refs: list[dict] | None = None
        # Set by answer() on every call (c012 observability, docs/plan-q029-
        # empty-answer-guard.md Plan B): [{"ref": ..., "reason": "not_found" |
        # "error"}, ...] for every `[bracket]` token that failed to resolve to
        # a Card, either a confirmed Scryfall miss or a fetch exception (the
        # latter previously crashed the whole request). Same lifecycle/
        # pattern as last_crossref -- read right after answer() by the API.
        self.last_tool_calls: list[dict] | None = None
        # Set on every answer() call (plan Sec 5.4): None when the
        # calculate_cost trigger didn't fire this turn (no tool round trip
        # attempted at all); otherwise a list of {"name", "input", "result"}
        # dicts, one per calculate_cost invocation on the attempt that
        # produced the returned Answer -- so "did it use the calculator, and
        # what did it compute" is answerable from telemetry without
        # re-running the question, same pattern as last_crossref/
        # last_ruling_selection.
        #
        # Slice 0 harness telemetry (docs/spec-slice0-harness.md Task 3).
        # last_tool_calls above does NOT let a caller derive the round count:
        # a single round can carry more than one tool_use block (the dispatch
        # loop iterates every block in one response), so len(last_tool_calls)
        # is a tool-CALL count, not a round count -- they can diverge. Exposed
        # explicitly here instead. Set on every answer() call that reaches the
        # round loop (regardless of whether a tool ever fired -- an ordinary
        # no-tool question still consumes exactly 1 round), so a real 1 is
        # never confused with the frozen-prompt path's real None (that path
        # has no round loop at all -- see evals/run_answer_eval.py's
        # _answer_from_frozen_prompt()).
        self.last_tool_rounds: int | None = None
        # stop_reason off the generation response that produced the returned
        # Answer (or off the last attempt's response on the fully-failed
        # empty-output path) -- makes rg3391-class max_tokens truncation
        # visible instead of silently scoring as an ordinary wrong answer.
        self.last_stop_reason: str | None = None
        # Token usage off that same response: {"input_tokens",
        # "output_tokens", "cache_read_input_tokens",
        # "cache_creation_input_tokens"} (same shape as evals/
        # opus_grader_calibration.py's usage dict), or None if the response
        # never carried a `.usage` (e.g. a bare fake in an older test stub).
        self.last_usage: dict | None = None
        self.last_fuzzy_fallbacks: list[dict] = []
        # Set by answer() on every call (docs/plan-scryfall-local-bulk.md
        # Sec 4): every local fuzzy-fallback event from this request's
        # get_card() calls -- a successful fallback match or a refused
        # ambiguous near-tie, each {ref, reason, matched_name, oracle_id,
        # score, candidates}. Same lifecycle/pattern as last_unresolved_refs.

    def answer(self, question: str, history: list[dict] | None = None) -> Answer:
        """`history` (optional): prior conversation turns, oldest first, each
        {"role": "user"|"assistant", "content": text}. history=None is the
        single-turn path and behaves exactly as before the parameter existed
        (same prompt string, same caches) -- the evals run single-turn, so
        their numbers are untouched by conversation support."""
        history = history or []
        self.last_rewritten = None
        self.last_uncited_success = False
        # Parse `[Card Name]` / `[oracle-id]` tokens BEFORE anything else
        # touches the question. `question` from here on is bracket-stripped
        # ("[Dovescape]" -> "Dovescape") -- what the rewriter sees, what the
        # generator sees as the question -- so the rewriter and the
        # no-brackets path are untouched: a question with no tokens comes
        # back unchanged and `cards` stays [].
        question, card_refs = parse_card_refs(question)
        # Cards referenced in EARLIER user turns stay in play: a follow-up
        # ("what if it's in the graveyard?") rarely repeats the [bracket], but
        # the card's data is still what grounds the answer. Union, oldest
        # first, deduped case-insensitively; the Scryfall cache makes the
        # repeat lookups free.
        seen: set[str] = set()
        all_refs: list[str] = []
        for turn in history:
            if turn.get("role") == "user":
                _, hist_refs = parse_card_refs(turn.get("content", ""))
                all_refs.extend(hist_refs)
        all_refs.extend(card_refs)
        all_refs = [r for r in all_refs if not (r.lower() in seen or seen.add(r.lower()))]
        # Unresolvable tokens (typo'd past fuzzy match, made-up name) are
        # silently dropped rather than erroring the whole answer -- the
        # rules-only answer still has a shot at being useful. Not specified
        # by the plan either way; this is the call made here. c012
        # observability (docs/plan-q029-empty-answer-guard.md Plan B): both
        # failure shapes -- a confirmed miss (get_card -> None) and a
        # transient fetch error (get_card raises) -- are now recorded on
        # last_unresolved_refs and logged, instead of vanishing (or, for a
        # raise, crashing the whole request) with zero trace. Broad
        # `except Exception` on purpose: it's the audit trail for any fetch
        # failure, not just the ones we've anticipated.
        resolved, unresolved = [], []
        for ref in all_refs:
            try:
                c = get_card(ref, no_refresh=self.card_no_refresh)
            except Exception as e:
                logger.warning("card ref failed to resolve (fetch error): %r: %r", ref, e)
                unresolved.append({"ref": ref, "reason": "error"})
                continue
            if c is None:
                logger.warning("card ref failed to resolve (not found): %r", ref)
                unresolved.append({"ref": ref, "reason": "not_found"})
                continue
            resolved.append(c)
        cards = resolved
        self.last_unresolved_refs = unresolved
        # Local-bulk fuzzy-fallback / ambiguity-guard debug surface (docs/
        # plan-scryfall-local-bulk.md Sec 4): get_card() logs a module-level
        # event on scryfall's own side-channel whenever it had to fall back
        # to a local fuzzy match (a successful match, or a refused ambiguous
        # near-tie) -- its signature stays `Card | None` so this is the only
        # way that information reaches a caller. Drained once per request,
        # right after every ref for this request has been resolved, mirroring
        # last_unresolved_refs above and the last_crossref/selected_ruling_ids
        # pattern elsewhere in this method.
        self.last_fuzzy_fallbacks = pop_fuzzy_fallbacks()

        # Condensed transcript for the rewriter: a follow-up like "what about
        # while it's phased out?" only rewrites into a useful standalone search
        # query if the rewriter can see what "it" was. Last 6 turns, each
        # clipped -- enough to resolve references without bloating the call.
        convo_ctx = None
        if history:
            lines = []
            for turn in history[-6:]:
                who = "User" if turn.get("role") == "user" else "Assistant"
                text = (turn.get("content") or "").strip()
                if len(text) > 500:
                    text = text[:500] + " …"
                lines.append(f"{who}: {text}")
            convo_ctx = "\n".join(lines)

        # Rewrite is computed here, BEFORE ruling selection, so a
        # ruling_query_mode="union" selection below can union the rewrite's
        # own phrasing(s) into what it scores rulings against (docs/plan-l1-
        # crossref-expansion.md Part B). This is a pure reorder from the
        # original post-ruling-selection position -- the retrieval search
        # itself still runs at the same point in the pipeline as before
        # (right after ruling selection, unchanged), so for the default
        # ruling_query_mode="raw" path this has no effect on retrieval
        # results or the assembled prompt (guarded by
        # tests/test_prompt_identity.py).
        rewritten = None
        if self.rewrite:
            rewritten = rewrite_query(question, REWRITE_MODEL, REWRITE_N, self.client,
                                      context=convo_ctx, version=self.rewrite_version)
            self.last_rewritten = rewritten

        self.last_ruling_selection = None
        if self.ruling_select:
            # Ruling mini-RAG: replace each card's full ruling list with only
            # the ones relevant to the (stripped, pre-rewrite) question. A card
            # with no relevant ruling contributes none -- rulings withheld, the
            # rules-RAG + oracle text stand alone.
            selection, picked = {}, []
            for card in cards:
                if self.ruling_query_mode == "union":
                    # Part B: union the raw question with the rewrite's own
                    # phrasing(s) so a ruling can clear the relevance floor
                    # via whichever angle actually matches it. Falls back to
                    # a one-query union (just the question) when rewrite is
                    # off / produced nothing -- still a valid
                    # select_rulings_union() call. Deduplicated (order-
                    # preserving) per select_rulings_union()'s own docstring
                    # ("queries should be passed already-deduplicated") -- a
                    # single-query rewrite (REWRITE_N=1) commonly equals the
                    # raw question verbatim or falls back to it on error, and
                    # a duplicate query would just waste one redundant embed
                    # call rather than change the result.
                    all_queries = [question] + (rewritten.queries if rewritten is not None else [])
                    union_queries = list(dict.fromkeys(all_queries))
                    sel = select_rulings_union(card, union_queries)
                else:
                    sel = select_rulings(card, question)
                selection[card.name] = [ruling_id(card, i) for i, _ in sel]
                # Label each ruling with its ORIGINAL Scryfall index so the
                # model can cite it precisely ("[Name ruling #4]") and the
                # cited label maps back to the gold oracle_id#index (L8).
                # build_prompt() also labels, idempotently -- this call is what
                # supplies the original indices, which it cannot recover from a
                # filtered list.
                picked.append(label_rulings(card, [i for i, _ in sel]))
            cards, self.last_ruling_selection = picked, selection
        else:
            # Dump-all A/B path gets the same labels, so the cite-by-label
            # convention holds in both configs.
            cards = [label_rulings(c) for c in cards]
        self.last_cards = cards

        if self.rewrite:
            if len(rewritten.queries) == 1:
                # Nothing to fuse with one rewrite -- search it directly.
                retrieved = self.store.search(rewritten.queries[0], self.k)
            else:
                rankings = [self.store.search(q, REWRITE_FUSION_DEPTH) for q in rewritten.queries]
                retrieved = rrf_fuse(rankings)[: self.k]
                # Deliberately NOT fusing the original question back in here
                # -- the plan's spike measured that hurting every arm it was
                # tried on. See evals/run_eval.py's `+orig` variant.
        else:
            retrieved = self.store.search(question, self.k)
        # Cross-ref expansion (L1): a pure post-ranking step -- runs AFTER
        # retrieval/rewrite/fusion have already produced the organic top-k,
        # so it can't move any rank the retrieval eval measures. No LLM call,
        # no recursion (one hop only), no prompt-shape change: appended
        # chunks are just more `[id] text` blocks after the organic ones.
        crossref_debug: dict = {}
        retrieved = expand_crossrefs(retrieved, self.chunk_map, debug=crossref_debug)
        self.last_crossref = crossref_debug
        self.last_retrieved = retrieved
        # Empty/invalid structured output happens INTERMITTENTLY on
        # claude-sonnet-5 (c018 came back empty on two eval runs, then answered
        # cleanly on retry -- diagnosed at ~600 thinking + ~1600 output tokens,
        # nowhere near the 16384 cap, so it is NOT budget/thinking exhaustion).
        # So RETRY once before degrading -- that is the fix for THIS failure,
        # and it is unrelated to the cap.
        #
        # AMENDED 2026-07-24: this comment used to end "so keep max_tokens at
        # 16384; raising the cap is not the fix and actively backfires". The
        # first half was over-generalised from the empty-output case above.
        # There is a SECOND, distinct failure that IS budget exhaustion: rg131
        # burned the full 16384 on thinking twice and returned the degrade
        # sentinel, and 8% of the bucket-A arm truncated. The cap is now 32768
        # (GEN_MAX_TOKENS) with an explicit request timeout to suppress the
        # SDK guard. Do NOT conflate the two failures -- retry fixes the
        # intermittent empty output, headroom fixes truncation, and neither
        # substitutes for the other.
        # Multi-turn (docs/plan-multiturn-stability.md): the conversation goes
        # into the final user message as a condensed TRANSCRIPT block -- the
        # same clipped form the rewriter consumes -- NOT as real prose
        # assistant messages. Injecting prose turns measurably destabilized
        # structured output (~50% degenerate answered=false draws on the
        # Grist/Animate Dead thread, 2026-07-22) -- plausibly because a
        # transcript of prose assistant replies contradicts the JSON reply
        # format, or because history citing rules absent from the current
        # context trips the grounding guard. With the transcript inlined, the
        # message list is single-turn-shaped in every case. Gated on `history`
        # so the single-turn path -- and therefore every eval number -- stays
        # byte-identical.
        system, user = build_prompt(
            question, retrieved, cards,
            convo_ctx=convo_ctx,
            rewrite_queries=(self.last_rewritten.queries
                             if self.show_rewrite and self.last_rewritten is not None
                             else None),
            # Slice 0 harness Task 2b: thread the instance's own selected
            # system version through instead of build_prompt()'s
            # module-SYSTEM default. Byte-identical to before for every
            # agent constructed with the default system_version=
            # PROMPT_VERSION, since SYSTEM_VERSIONS[PROMPT_VERSION] is
            # SYSTEM itself.
            system_override=SYSTEM_VERSIONS[self.system_version],
        )
        # calculate_cost tool gate (docs/plan-cost-calculator-tool.md Sec 3b):
        # only when the trigger fires does the call gain `tools=` and the
        # extra system sentence -- see _needs_cost_tool's docstring for why
        # this is gated rather than always-on. `call_system`/`extra_kwargs`
        # are exactly what changes; `system`/`user` from build_prompt above
        # are completely untouched either way, so build_prompt's own output
        # (and every existing test/fixture that checks it) is unaffected.
        use_cost_tool = _needs_cost_tool(question, cards)
        # resolve_layers tool gate (docs/plan-layer-system-tool.md Sec 3c):
        # same posture as use_cost_tool -- gated on its own calibrated
        # trigger, never always-on. Slice 0 harness (docs/spec-slice0-
        # harness.md Task 1): self.layers_tool is a master suppression
        # switch OUTSIDE _needs_layers_tool itself -- that trigger is
        # calibrated and untouched; the switch just decides whether its
        # firing is honored at all.
        use_layers_tool = self.layers_tool and _needs_layers_tool(question, cards)
        # use_any_tool generalises the three round-loop gates below so they
        # aren't hardcoded to calculate_cost (docs/plan-layer-system-tool.md
        # Sec 3d must-fixes 1-3). use_cost_tool/use_layers_tool are kept
        # separate from use_any_tool because each still (and only) controls
        # whether ITS OWN schema and trigger sentence get attached -- a
        # layers-only question must not inherit the cost tool's instruction
        # sentence, and vice versa (§3d: "TOOL_TRIGGER_SENTENCE becomes
        # per-tool"). `tools` is a built list rather than a hardcoded
        # single-element list, so either trigger (or both) can extend it
        # without the other's wiring changing.
        use_any_tool = use_cost_tool or use_layers_tool
        call_system = system
        extra_kwargs: dict = {}
        tools: list = []
        if use_cost_tool:
            call_system = call_system + "\n" + TOOL_TRIGGER_SENTENCE
            tools.append(CALCULATE_COST_TOOL)
        if use_layers_tool:
            call_system = call_system + "\n" + LAYERS_TRIGGER_SENTENCE
            tools.append(RESOLVE_LAYERS_TOOL)
        if tools:
            extra_kwargs["tools"] = tools
        base_msgs: list[dict] = [{"role": "user", "content": user}]
        self.last_tool_calls = None
        self.last_tool_rounds = None
        self.last_stop_reason = None
        self.last_usage = None
        parsed, response = None, None
        weak = None  # best parseable-but-degenerate draw, kept as a fallback
        for _attempt in range(2):
            attempt_msgs = list(base_msgs)
            attempt_tool_calls: list[dict] = []
            response = None
            for _round in range(TOOL_ROUND_CAP):
                # Cap-exhaustion fix (Phase 1 instrumented repro: 16 of 17
                # failing attempts were the model emitting tool_use on every
                # round, never truncation or payload size): forbid tools on
                # the LAST permitted round only, so the model must emit the
                # terminal structured Answer instead of yet another tool
                # call. `tools` stays attached -- only `tool_choice` narrows
                # what's legal this turn -- and this is a per-round copy, so
                # earlier rounds and the entire non-tool path keep issuing
                # the exact same call shape as before (extra_kwargs itself
                # is never mutated).
                is_last_round = _round == TOOL_ROUND_CAP - 1
                round_kwargs = extra_kwargs
                if use_any_tool and is_last_round:
                    round_kwargs = {**extra_kwargs, "tool_choice": {"type": "none"}}
                try:
                    response = self._gen_client.messages.parse(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=_cacheable_system(call_system, self.cache_prompt),
                        messages=attempt_msgs,
                        output_format=Answer,
                        # Empty dict when self.effort is None -- expands to
                        # nothing, so the default call shape is unchanged.
                        **self._effort_kwargs,
                        **round_kwargs,
                    )
                except ValidationError:
                    # messages.parse RAISES on empty content rather than
                    # returning parsed_output=None -- treat both the same:
                    # retry, then degrade. This attempt is over.
                    response = None
                    break
                # Only ever check stop_reason when tools were actually
                # attached this call -- the model can't return "tool_use"
                # otherwise, so the non-tool path never touches this
                # attribute at all (byte-identical old behavior; also means
                # a bare fake response stub with no .stop_reason, as several
                # existing tests use, keeps working unchanged).
                if use_any_tool and getattr(response, "stop_reason", None) == "tool_use":
                    # Tool round trip (spike-verified shape, docs/spike-
                    # tool-use-findings.md Sec 2): append the assistant's
                    # tool_use turn, execute every tool call locally, append
                    # the tool_result turn, and reissue the SAME call shape.
                    # Never reached when use_any_tool is False -- no tools
                    # are attached, so the model can't return "tool_use".
                    attempt_msgs = attempt_msgs + [
                        {"role": "assistant", "content": response.content}
                    ]
                    tool_results = []
                    for block in response.content:
                        if getattr(block, "type", None) == "tool_use":
                            # Name-routed dispatch (docs/plan-layer-system-
                            # tool.md Sec 3d must-fix 4): _dispatch_tool_call
                            # only calls _run_calculate_cost for
                            # block.name == "calculate_cost"; an unregistered
                            # name gets an explicit unknown-tool error
                            # instead of being fed to the wrong handler.
                            result = _dispatch_tool_call(block.name, block.input)
                            attempt_tool_calls.append(
                                {"name": block.name, "input": block.input, "result": result}
                            )
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            })
                    attempt_msgs = attempt_msgs + [{"role": "user", "content": tool_results}]
                    continue
                break
            else:
                # TOOL_ROUND_CAP rounds all came back tool_use -- a confused
                # model looping. Guard fires: this attempt is treated as
                # failed (same as a ValidationError) rather than looping
                # further or returning an unpopulated response.
                response = None

            if use_any_tool:
                self.last_tool_calls = attempt_tool_calls
            # Slice 0 harness telemetry (docs/spec-slice0-harness.md Task 3),
            # set every attempt (unlike last_tool_calls above, which is only
            # meaningful when a tool was actually attached). `_round` still
            # holds its last-assigned value here whether the inner loop
            # exited via `break` or ran the for/else cap-exhaustion path, so
            # `_round + 1` is the real number of round trips this attempt
            # made -- 1 for an ordinary no-tool question, up to
            # TOOL_ROUND_CAP for a chained or looping one.
            self.last_tool_rounds = _round + 1
            self.last_stop_reason = getattr(response, "stop_reason", None) if response is not None else None
            usage_obj = getattr(response, "usage", None) if response is not None else None
            if usage_obj is not None:
                self.last_usage = {
                    "input_tokens": getattr(usage_obj, "input_tokens", None),
                    "output_tokens": getattr(usage_obj, "output_tokens", None),
                    "cache_read_input_tokens": getattr(usage_obj, "cache_read_input_tokens", 0) or 0,
                    "cache_creation_input_tokens": getattr(usage_obj, "cache_creation_input_tokens", 0) or 0,
                }
            else:
                self.last_usage = None

            parsed = response.parsed_output if response is not None else None
            # Malformed check runs alongside _degenerate, on the SAME draw,
            # before anything else touches it -- specifically before the
            # Scryfall attribution is appended below (that only happens to
            # the FINAL returned parsed, never to an in-loop retry
            # candidate), so _malformed always sees the raw model text.
            # Scoped to answered=True (an answered=False draw already goes
            # through _degenerate's own blank/near-blank check above; a
            # non-blank answered=False decline is an honest decline, not
            # something this guard should touch).
            is_malformed_draw = (
                parsed is not None and parsed.answered and _malformed(parsed.text)
            )
            if parsed is not None and (_degenerate(parsed) or is_malformed_draw):
                # Parsed fine but it's either: a degenerate non-answer
                # (answered=false, no citations, ~empty text), or -- new --
                # answered=true with GARBLED text (chat-template leakage or a
                # bare fragment; see _malformed's docstring). Both are the
                # weak-draw class the old retry couldn't see because it only
                # caught parse FAILURES. Retry once, same budget as the
                # parse-failure retry; keep the longer draw in case both come
                # back bad. A malformed answered=true draw is NEVER reused as
                # `weak` below (that branch requires `not weak.answered`), so
                # garbage is never shipped even as a fallback -- same shape as
                # the q029 blank-answered-true case. An honest decline
                # explains what's missing (200+ chars in the eval history) so
                # it doesn't match either check and is never retried away.
                if weak is None or len(parsed.text) > len(weak.text):
                    weak = parsed
                parsed = None
            if parsed is not None:
                break
        if parsed is None and weak is not None and not weak.answered:
            # Only an honest answered=false decline is ever reused as a
            # fallback -- a still-blank answered=true `weak` (q029, L1 gate 4)
            # falls through to the honest non-answer Answer below instead of
            # ever being returned as if it were real content.
            parsed = weak
        if parsed is None:
            # Both attempts came back empty/invalid -- honest non-answer, not a
            # crash. Rare after the retry; a persistent failure is worth seeing.
            stop = response.stop_reason if response is not None else "error"
            return Answer(
                text="(no structured answer: the model returned empty output "
                f"twice, stop_reason={stop} -- try again)",
                tldr="Something went wrong generating this answer -- try again.",
                citations=[],
                answered=False,
                suggested_followups=[],
            )
        if parsed.answered and not parsed.citations:
            # Plan A amendment (docs/plan-q029-empty-answer-guard.md header
            # ruling 1): a non-blank answered=true draw that cites nothing is
            # NOT grounded in the rules -- flag it (log + Debug field), don't
            # retry it. Blank text already went through _degenerate()/the
            # retry loop above; this catches the separate, unretried shape:
            # real-looking prose with zero citations.
            logger.warning(
                "answered=true with no citations (ungrounded success): %r",
                parsed.text[:200],
            )
            self.last_uncited_success = True
        if cards:
            # Minimal approach consistent with the Answer contract (no new
            # field): append the Fan Content Policy attribution to the
            # prose whenever Scryfall card data was in the prompt at all,
            # rather than trying to detect post hoc whether the model
            # "relied on" it -- the citations field already covers which
            # specific rules/cards it leaned on.
            parsed.text = f"{parsed.text}\n\n{ATTRIBUTION}"
        return parsed
