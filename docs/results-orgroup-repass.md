# Results — v3 conjunctive OR-group re-pass

**105 confirmed, not assumed.** `evals/questions_rulesguru150_v3.jsonl` (150
rows, `match: "groups"`) carries exactly **105 multi-member OR-groups**
(`gold_groups` sub-lists with 2+ ids), across **75 of the 150 questions**. That
count was independently derived from the file itself, not taken on faith from
`evals/gold_miner_prompt.md`'s "105" — it matches.

These groups predate rule 6 (the merge rule) in `evals/gold_miner_prompt.md`,
which didn't exist until v2 mining (2026-07-26). Rule 6's own test: *"if the
retriever found ONLY this member and none of the others, would that step of the
answer be established? If no for any member, split the group."* Every one of the
105 groups was re-run through that test against the actual CR text.

## Classification

| category | groups | rows affected |
|---|---:|---:|
| (a) legitimate OR — every member independently sufficient | **26** | 26 |
| (b) mis-encoded conjunction — a required step wrongly merged as an alternative | **54** | 43 |
| (c) mixed/unclear — needs Jon | **25** | 21 |
| **total** | **105** | 75 (60 unique, 15 rows are all-legitimate) |

(43 + 21 − 4 = 60: four rows — `rg127`, `rg1835`, `rg1933`, `rg6475` — have one
group in category (b) and a different group in category (c), so they appear on
both id lists below.)

### (a) legitimate OR — 26 groups, no action needed

`rg64`, `rg1753`×2, `rg2871` (609.3/101.3), `rg101` (202.3e/107.3a), `rg6578`,
`rg6907`, `rg935`, `rg862`, `rg6834`, `rg2543`×2, `rg1232` (709.4/709.4c),
`rg137`, `rg2163` (702.47a/612.10), `rg234`, `rg79`, `rg2599` (302.6/508.1a),
`rg1718`, `rg725` (603.3a/113.8), `rg517` (605.5a/605.1a), `rg466`×2, `rg1208`,
`rg5863`, `rg470` (800.1/100.1a).

These are almost all genuine duplicate or parallel statements of one fact from
two rule sections (e.g. a numbered SBA rule + its glossary entry, or a
general-keyword clause + a card-type-specific restatement of the same clause).

### (b) mis-encoded conjunction — 54 groups (43 rows)

`rg6328`, `rg6743`, `rg2871` (113.6g/101.2), `rg615`, `rg93`, `rg1835`
(608.2d/609.3/101.2), `rg6725`×2, `rg1784`, `rg3126`×2, `rg2242`, `rg6667`×2,
`rg7413`, `rg84`, `rg144`×2, `rg3868`×3, `rg963`, `rg1660`, `rg7092`, `rg1652`,
`rg606`×2, `rg2029`, `rg97`, `rg633`, `rg6475` (704.3/704.5g/117.5/117.2e),
`rg127` (613.8a/613.8b), `rg899`, `rg608`, `rg1095`×2, `rg4256`, `rg517`
(106.12/106.12b), `rg807`×2, `rg282`, `rg289`, `rg811`×2, `rg5768`×2, `rg1933`
(702.140e/730.2a), `rg72`, `rg5539`, `rg5785`, `rg238`, `rg1555`, `rg842`,
`rg625`.

### (c) needs Jon — 25 groups (21 rows)

`rg6583`, `rg3509`, `rg101` (202.3/202.3d), `rg7282`×2, `rg1835`
(107.3a/601.2b), `rg3327`, `rg1702`, `rg1232` (709.3/709.3a), `rg3518`, `rg2163`
(204.2/204.1), `rg6475`×2 (701.19a/614.8/701.19b, and 608.2c/608.1), `rg2599`
(727.1/726.4), `rg127` (613.1d/205.1a), `rg494`, `rg713`×2, `rg725`
(800.4g/608.2d), `rg6556`, `rg851`, `rg470` (727.1/726.1), `rg60`, `rg1933`×2
(730.2i/729.2a, and 303.4d/701.3b).

Most of the (c) calls split into two shapes, both worth Jon's eyes rather than
a mechanical split:

- **One member is alone-sufficient, the other is generic supporting text** —
  splitting would technically satisfy rule 6, but the "extra" member may just be
  weak padding rather than a real defect (e.g. `rg1702`'s 305.6, `rg60`'s
  702.26b).
- **One member looks like a flat wrong citation, not a conjunct or an
  alternative** — three separate questions (`rg2599`, `rg6556`, `rg470`) all
  pair a Karn Liberated restart-the-game question with a citation from CR
  section **726, the Initiative mechanic** (`726.4`, `726.2`, `726.1`
  respectively), which has nothing to do with restarting a game. That's a
  distinct, repeating defect worth flagging on its own — it looks like a
  systematic rule-number mixup in the corpus, not a one-off.

## Worked examples

**1. Clean mis-encoded conjunction — `rg93`** (level 0). Question: Sram's
Expertise lets Avery cast Collective Effort for free mid-resolution; can they
still pay escalate (an additional cost) by tapping the tokens it just made?
Original group: `["118.9d", "601.2b", "608.2g"]`. Checked against the CR:

- `608.2g` — "If an effect specifically instructs or allows a player to cast a
  spell during resolution, they do so by following the steps in rules
  601.2a–i..." — establishes that Sram's Expertise's mid-resolution cast still
  goes through the **normal casting process**, including cost payment.
- `118.9d` — "If an alternative cost is being paid to cast a spell, any
  additional costs... are applied to that alternative cost." — establishes that
  additional costs (escalate) **still apply on top of** an alternative cost
  (Sram's free cast).
- `601.2b` — generic cost-announcement procedure, referenced by both of the
  above but not itself the source of either fact.

Test each alone: retrieving only `608.2g` tells you the casting process is
normal, but not that additional costs survive an alternative cost. Retrieving
only `118.9d` tells you additional costs survive alternative costs, but not
that this mid-resolution cast even follows the normal process. Neither
individually answers the question — they're two different links in one chain.
**Proposed fix:** three singleton required groups, not one 3-member OR.

**2. Legitimate OR, confirmed rather than assumed — `rg517`, group
`["605.5a", "605.1a"]`** (level 3). Question: does Deathrite Shaman's first
ability count as "tapping it for mana" for Mana Reflection's doubling? Checked
Deathrite Shaman's actual oracle text via `rulesagent.tools.scryfall.get_card`
(zero API cost, local cache) rather than assuming: `"{T}: Exile target land
card from a graveyard. Add one mana of any color."` — it has a target.
`605.5a` ("An ability with a target is not a mana ability...") states that
directly. `605.1a` (the exhaustive mana-ability test: no target, could add mana,
not a loyalty ability) reaches the identical conclusion from the ability's own
defining criteria. Either rule alone fully answers "is this a mana ability?" —
correctly encoded as an OR.

**3. Not a conjunction, but not a clean OR either — `rg60`, group
`["702.26k", "702.26b"]`** (Corner Case level). Question: a phased-out Angel of
Sanctions' owner loses the game — does the exiled card it's holding come back?
`702.26k` states the exact scenario verbatim: *"Phased-out permanents owned by a
player who leaves the game also leave the game. This doesn't cause zone-change
abilities to trigger."* That's already the whole answer. `702.26b` (general
"phased-out permanents are treated as nonexistent") is true background but adds
nothing the specific rule doesn't already cover on its own — it's not a
required second step, so it doesn't fit "mis-encoded conjunction" the way rule
6 defines it. It's flagged **needs-Jon** rather than forced into a split,
because the fix here ("drop the padding") is a different judgment call than the
fix for a true chain ("split into required steps").

## A pattern found by accident, not by design

Three unrelated questions about Karn Liberated's game-restart ability
(`rg2599`, `rg6556`, `rg470`) each pair a `727.x` restart-mechanics citation
with a citation from CR section **726 — the Initiative mechanic** (a completely
different, unrelated system from *Adventures in the Forgotten Realms*/*Baldur's
Gate*). None of the three restart questions involve initiative. This wasn't
something the task was looking for — it surfaced because the same odd pairing
showed up three separate times. Recorded here rather than silently absorbed
into "needs Jon," since it looks like a real, repeatable defect in how those
three rows were mined, not a judgment call.

## Files

- Full per-group grounding is preserved in
  `evals/orgroup_repass_proposed_corrections.jsonl` (79 records: 54
  `mis-encoded-conjunction` with a `proposed_split`, 25 `needs-jon` with a
  `note`). Every record carries the question `id`, its `level`, and the
  original flat `original_group` from `questions_rulesguru150_v3.jsonl` so it
  can be matched back without re-deriving anything.
- This document: `docs/results-orgroup-repass.md`.
- **Nothing in `evals/questions_rulesguru150_v3.jsonl` was modified.** The
  corrections file is a proposal only; Jon rules on it before any gold changes.

## Impact if Jon approves

- **60 of 150 questions** (40%) in the v3 set would have their `gold_groups`
  restructured — 43 by a mechanical split (mis-encoded), up to 17 more
  (`needs-jon` rows not already in the 43) pending Jon's call on the specific
  fix. The flat `gold` union is unaffected either way (same ids, same
  invariant) — only the AND/OR structure changes.
- `gold_groups` feeds `gold_groups()` / `hit_at()` in `evals/run_eval.py`,
  consumed by `evals/run_retrieval_diversity.py`. That means **any retrieval
  recall/hit metric computed against this question set** — most concretely
  `docs/results-retrieval-diversity.md` (run 2026-07-25 against this exact
  file) — was scored against a partly-too-easy target: a mis-encoded OR credits
  a retriever for finding *any one* of several rules that were actually all
  required, which inflates recall on those 43 (up to 60) rows. The flat-`gold`
  scoring path (`evals/build_gold_prompts.py`, the derivability arms) is
  unaffected, since it doesn't consume `match`/`gold_groups` semantics
  (`run_eval.py:186`).
- No change to `answer_gold` anywhere — this is retrieval-gold structure only,
  per the scope boundary in `docs/spec-cr-gold-mining.md` § 2.

## API spend

**None.** All 105 groups were graded by reading `data/raw/MagicCompRules
20260619.txt` directly (`grep`) and, where a group's classification hinged on
exact card wording, `rulesagent.tools.scryfall.get_card` (local cache, ~0.25s
per lookup, no network/LLM cost) — used for `rg7282` (Surge of Salvation),
`rg84` (Curse Artifact), and `rg517` (Deathrite Shaman). No Anthropic API calls,
no subagents spawned; this ran as the lead session's own labor per the task's
"$0 in credits" instruction.
