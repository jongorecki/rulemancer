**DRAFT under Rule 0 — DESIGN ONLY. Jon's decisions on the open questions recorded below; not yet built.**

**Jon's rulings (2026-07-23):**
1. **Test set narrowed to gpt-5-mini vs sonnet only** — gemini (and the other cheap arms) are dropped from the decision loop. This MOOTS most of the plan's token-bloat risk section: that risk was about the *weakest* model (gemini) choking on added instructions; gpt-5-mini *gained* +3 from v3. The +12% token cost is a non-issue against a ~5-8x model-swap saving.
2. **Keep the mana block ALWAYS-ON** (not gated to cost questions). No conditional rendering; preserves byte-identical-prompt A/B testing. Cost of always-on is negligible per #1.
3. **Keep the mana worked example** (the ~210-token item) — retained; token cost accepted.
4. **Redundant two-place assumption emphasis: yes** (Jon leans yes; keep the small optional emphasis clause).
5. **Timing-assumption bullet (§1d): KEEP SEPARATE** (Jon ruled 2026-07-23) — do NOT merge it into the general assumption-disclosure bullet. Rationale (Jon): "timing is incredibly important in the game of Magic." §1d stays as its own dedicated bullet with its concrete timing example; 4c (general assumption disclosure) is added alongside it, not in place of it. Accept the minor overlap.
6. **Replace the mana block (§4a) with a FULL NOTATION LEGEND** (Jon ruled 2026-07-23) — the bot should understand ALL Scryfall oracle-text notation, not just mana. Design decisions:
   - **Location: the GENERATION system prompt only.** Static reference text, so it sits in the cacheable system prefix — with prompt caching it's written once and served at ~0.1x on repeat calls (this IS Jon's "cached version always used"; no separate cache or tool/retrieval mechanism needed — the legend is ~300-500 tok, far too small to justify a tool). It does NOT go in the rewriter or the frozen judge system prompts (separate strings), so it can't leak into retrieval or grading.
   - **Two tiers, honesty about validation:** CORE (mana {N}/{C}/colored/hybrid/Phyrexian/{X} + arithmetic, plus {T}/{Q} tap/untap) — these symbols appear in the eval corpus (verified: {T}, colored, generic, {X}, hybrid {W/B}/{W/U} all present in cached cards) so the A/B can validate them. REFERENCE (energy {E}, snow {S}, loyalty, and any other standard symbols) — do NOT appear in the current 19-question eval, so they ship as deploy-insurance for the full card pool (post local-bulk), explicitly labeled untested-by-current-eval.
   - **No-lecture guard (required):** an instruction that the legend is for INTERPRETING card text, and the model must not recite or explain notation to the user unless the user asks — prevents the over-triggering failure (Opus-4.x lesson: a glossary in the prompt makes models explain notation unprompted).
   - **Symbol definitions verified at BUILD time against Scryfall/the CR, never from model memory** — MTG symbol semantics ({W/P} Phyrexian, snow, energy, hybrid) are a "don't assert from memory" case; the implementer confirms each definition against a real source before writing it.
   - Token cost is a non-issue per ruling #1 (and caching makes the static legend nearly free after the first call).

**Measured token budget (2026-07-23, corrects the estimates below):** current v3 SYSTEM = **5,189 chars ≈ ~1,300 tokens** (the "~3.1k" figure elsewhere in this plan was an overestimate). v4 adds ~360 → **~1,660 tokens**. Marginal cost of the +360 input tokens ≈ **$0.0007/query on sonnet**, negligible. Real per-query cost (cond C, measured): gpt-5-mini ~$0.0059 vs sonnet ~$0.048 std / ~$0.032 intro = **~8x / ~5x** cheaper.

# Prompt-Tuning Plan v4: Mana Arithmetic + Multiplayer Refinement + Assumption Disclosure

Source evidence: `docs/grading-feedback-backlog.md` ("System-prompt improvement ideas," 21 notes), `docs/plan-prompt-tuning.md` (the v3 design, Jon-approved 2026-07-22, `PROMPT_VERSION = 3`), current `SYSTEM` string in `src/rulesagent/generate/answer.py` (read in full for this plan). External comparison: `ChrisMiho/TheJudge` (public repo, cloned read-only to a scratch dir for this plan; nothing copied verbatim — techniques only, re-expressed in our own words).

Judge prompt is out of scope, same as v3.

---

## 0. TheJudge comparison (Part 1 — full-prompt review, not just mana)

Cloned `https://github.com/ChrisMiho/TheJudge` and read its backend prompt-assembly code end to end: `apps/backend/src/prompt/{promptAssembly,promptFormatting,mtgReference,preparation,phaseGuidance}.ts`, `gameRules.ts`, `cardRulings.ts`, `types/index.ts`. TheJudge is a **stateful play-assistant** (it's handed live game state — stack contents, zones, turn phase, combat step — and explains what's happening next), not a stateless rules-reference Q&A bot like ours. That shapes the whole comparison: several of its strengths are about describing game state, not about rules reasoning, and don't transfer directly.

Going dimension by dimension, per Jon's ask:

### Grounding / honesty
TheJudge's preamble: *"Use only the provided context to explain likely interactions and resolution order."* / *"Do not claim hidden state, private-zone information, or unseen effects."* Its instructions add: *"Do not invent hidden state, targets, or board conditions."* This is the same groundedness principle our SYSTEM already leads with ("Answer the user's question using ONLY the numbered rules provided"), just phrased for a different domain (hidden game state vs. rules coverage). **No gap — we already have the equivalent, arguably a stricter version** (ours also forces `answered=false` + a stated reason when ungrounded; TheJudge has no such fallback mechanism at all — it just answers with whatever it has). Nothing to adopt here.

One TheJudge line we DON'T have any equivalent of: *"Do not present output as an official tournament ruling."* — an explicit authority/liability disclaimer. **Considered, not recommended for adoption**: our whole value proposition is citing actual CR rule numbers and real Oracle rulings as grounding — a blanket "this isn't official" disclaimer would undercut the thing we're actually good at, and no grading note ever asked for it. Noting it for completeness since Jon asked for full coverage, not proposing it.

### Citation handling / formatting
**TheJudge has no structured citation mechanism at all.** No citations field, no forced rule-number-in-citations discipline, no schema — `AskAiResponse` is just `{ answer: string, context?, diagnostics?, enrichmentDebug? }`, free text. **We are meaningfully ahead here already** (structured `Answer.citations`, the "every cited rule number must appear in citations" rule, ruling-label citation convention). Nothing to borrow; worth stating plainly since it's a real point of comparison Jon asked about.

### Answer structure / ordering (direct answer first, tl;dr, etc.)
TheJudge's `AskAiResponse` has no `tldr`, no structured "answer this reading first" instruction, no equivalent of our §1f. Its only ordering-adjacent instruction is the blunt verbosity line below. **We're ahead here too** — nothing to adopt; our v3 §1f (direct-answer-first, dual-reading handling) and `tldr`/`suggested_followups` fields have no TheJudge counterpart to compare against.

### Ambiguity, assumptions, clarifying questions
Covered by one line each, in two separate places: *"State assumptions when context is incomplete"* (preamble) and *"State uncertainty when context is incomplete"* (instructions) — a deliberate **repeat-the-instruction-twice** pattern, not a mechanism (no clarifying-question flow, no schema field for it — same non-goal we already have). **Technique worth adopting**: the redundant-emphasis phrasing itself (see §3 below) — restating a high-priority behavior briefly in two places in the prompt rather than stating it once and hoping it sticks in a long bullet list.

### Multiplayer / edge-case handling
TheJudge tracks `playerCount` as raw numeric game state (rendered as `playerCount: N` in the context block) but has **zero instructional text about multiplayer-specific rules differences** anywhere in the prompt-assembly code. **We're already ahead** — v3 §1c (and this plan's §2 item 4b) is more multiplayer-aware than anything TheJudge does. Nothing to borrow.

### Tone / voice, verbosity control, output-length discipline
TheJudge's instructions include *"Explain reasoning clearly and concisely."* — a blunt verbosity-control bullet. **We already have the direct equivalent** (v3's "Keep the answer accurate and to the point; a player should be able to act on it."). No gap.

Where TheJudge is genuinely more disciplined is **engineered content budgeting**, not prompt wording: `normalization.ts` defines a whole family of character caps (`MAX_CONVERSATION_HISTORY_CHARS`, `MAX_RULING_COMMENT_CHARS`, `MAX_RULINGS_PER_CARD`, `MAX_RULINGS_SECTION_CHARS`, `MAX_TARGET_LABEL_CHARS`, `MAX_CONTEXT_NOTES_CHARS`), and `cardRulings.ts`'s `resolveRulingsForPrompt` does graceful overflow handling — when a card's rulings would blow the section budget, it still squeezes in a truncated partial ruling rather than dropping the card's data entirely. This is a **context-assembly / code technique, not a system-prompt wording technique** — genuinely clever, worth flagging (see §3), but out of scope for a SYSTEM-string-only plan since it lives in `_format_context`/`_format_cards`-equivalent code, not in `SYSTEM` itself.

### Card-text-vs-rules precedence
TheJudge has **no instruction at all** about oracle text overriding a general rule it contradicts. **We're already ahead** (v3 §1e). Nothing to borrow.

### Zones / timing / priority handling
This is where TheJudge is most distinctive, but least transferable: `phaseGuidance.ts` renders a different, targeted paragraph of procedural guidance (who has priority, what can legally happen next, when SBAs get checked) depending on the live `turnPhase`/`combatStep` in the request — e.g. a whole separate string for "declare blockers step" vs. "cleanup step." This requires tracking live game state we don't have (we're a static rules-reference bot, not a stack-resolution assistant) — **not directly portable**, but it IS the concrete precedent behind the "conditionally render a targeted instruction block instead of a static one" technique proposed for the mana-math block (§4). Separately, `mtgReference.ts`'s static, always-included legend on the 7-layer continuous-effects system (a complex, easy-to-get-wrong rules concept, explained once with a numbered list, budgeted under 2,500 characters) is a **direct structural precedent for exactly what §2's 4a mana-arithmetic block is trying to do** — a comparable production MTG assistant already pays a flat token cost for a static worked reference on a hard rules concept, and treats that cost as worth it. Cited explicitly in §2's 4a rationale.

### Anything clever we don't do at all
Two things, both non-prompt-wording:
1. **Graceful section-budget truncation** (above) — a context-assembly technique.
2. **Runtime prompt-size diagnostics**: `promptDiagnostics.ts` computes and returns character counts per prompt section (rulings section chars, game-rules section chars, supplemental-rules chars, conversation-history chars) alongside every generated answer — an observability practice for catching bloat in production, not just in eval runs. Directly relevant to this plan's own "token bloat is the key risk" concern (§5) — see §3 for the recommendation.

### Rough token-size comparison (unchanged from the mana-focused pass)
TheJudge's static instructional text (`SYSTEM_ROLE_PREAMBLE_LINES` ~500 chars + `INSTRUCTIONS` ~200 chars + `MTG_PROMPT_REFERENCE` ~1,700 chars) is roughly **2,400 characters / ~550-650 tokens** (word-count estimate, not a real tokenizer run) — well under our v3 SYSTEM's ~3.1k tokens. `phaseGuidance.ts` adds more, but only one phase's slice renders per call. TheJudge's prompt is leaner mainly because it's describing structured game state rather than attempting general rules-arithmetic instruction — a different problem shape, not evidence a leaner prompt would suffice for ours.

**Bottom line on mana specifically: nothing to copy.** Grepped the whole repo for mana-cost/generic-mana/colorless/mana-symbol language and literal `{N}`/`{G}`-notation outside test fixtures — no instructional text on mana math anywhere. Per-card `manaCost`/`manaValue` are passed as raw fields with zero interpretive guidance. Jon's hunch that "the repo I shared from ChrisMiho should have a great system prompt hiding somewhere" for mana math doesn't pan out; flagging that plainly rather than inventing a source that isn't there.

---

## 1. Problem statement

Two things the v3 rollup surfaced that v4 must address without repeating v3's approach:

1. **Mana math is still broken across every arm.** The c014 cluster (Trinisphere-style cost floor + generic-only reduction) failed on `deepseek-v3-2_B_r1`, `deepseek-v4-flash_D_r2`, and `gemini-flash-lite_B_r1` even after v3's §1b mana bullet shipped — the backlog's own framing is blunt: *"it doesn't actually know how to calculate mana values and what mana values mean in this notation... we probably need to add to our system prompt something to teach it how the notation works, and how to do math with mana."* v3's §1b bullet (definitions only — no arithmetic worked example) was necessary but not sufficient.
2. **v3 already spent its bloat budget once, and it showed.** v3 added ~520 tokens (+20%, 2.6k → ~3.1k) and its own risk table flagged `1c` (multiplayer) as *"the highest-risk item in the core bundle"* for tempting a model toward ungrounded claims, plus a specific concern that `gemini-flash-lite` — "the weakest at holding multi-instruction prompts together" — was most exposed to the token-increase itself as a regression vector, independent of any single bullet's content.

v4 must fix (1) without repeating v3's insufficient definitions-only treatment, while treating (2) as a live constraint, not a footnote.

---

## 2. Proposed v4 additions — driven by Jon's graded notes (priority order, per the task brief)

All insert points below are relative to the **v3** `SYSTEM` string as it exists today in `answer.py` (labels `1a`-`1f` per that file's own comments). v4 adds new content labeled `4a`-`4e`; where a v4 item revises an existing v3 bullet in place, that's stated explicitly rather than adding a duplicate.

### 4a. Mana notation + arithmetic — REPLACES v3 §1b in place (same insert point: immediately after "Define any key term...")

This is the #1 required fix. Proposed replacement text (draft, not final wording):

```
- Mana notation: {N} where N is a plain number means N generic mana,
  payable with any color or with colorless mana. {C} means colorless mana
  specifically -- it is NOT generic and is never satisfied by colored mana.
  {W}/{U}/{B}/{R}/{G} each mean one mana of that single color. {X} is a
  variable fixed when the spell or ability is cast or activated -- resolve
  X to its actual value before doing any of the arithmetic below. A cost
  written as {2}{U}{U} is 2 generic + 2 blue = 4 total mana, never "4 mana
  of any color."
- Cost math: a cost-REDUCTION effect ("this costs {1} less") only lowers
  the generic portion and never goes below {0} generic -- it cannot touch
  colored or {C} symbols. A cost-INCREASE effect that sets a floor on the
  total cost (read the card's own wording for exactly how it's phrased --
  don't assume a specific card's wording without seeing it) applies to the
  TOTAL mana paid, not just the generic part. When more than one
  cost-changing effect applies, apply them one at a time in the order
  described by the rules provided, and always restate the final total cost
  broken out by symbol, not just a lump number. Worked example: a spell
  that costs {1}{G}{G} (3 total: 1 generic + 2 green) with a "spells cost
  {1} less" effect becomes {G}{G} (2 total -- the 1 generic mana is gone,
  the 2 green mana is untouched); if a total-cost floor of 3 also applies,
  the total goes back up to 3 (typically {1}{G}{G} again, since the floor
  cares about the total mana count, not which symbols make it up).
```

**Precedent**: TheJudge's `MTG_PROMPT_REFERENCE` does exactly this pattern — a static, always-included, budgeted worked explanation of a complex rules concept (the 7-layer continuous-effects system) — for a different hard concept. That's real evidence a comparable production assistant treats this shape of cost (a flat static reference block) as worth paying. It does not, however, do this for mana math specifically — see §0.

**Honest tradeoff:** this is roughly **2.5-3x the token length of v3's §1b** precisely because it adds the thing v3's version didn't have — a worked example and explicit step-by-step arithmetic, not just definitions. That's the deliberate fix; it is not free. §5 below proposes gating this specific block so it doesn't tax every call.

### 4b. Multiplayer refinement — REVISES v3 §1c in place (same insert point, same bullet)

Jon's grading gave near-verbatim wording to use directly, plus specific q014 refinements (defending-player plurality, don't over-claim beyond what's provided). Proposed revised text:

```
- If the outcome would be different assuming a multiplayer game compared
  to a two-player game, state each outcome separately and say which is
  which. If the outcome is the same regardless of player count, say that
  plainly instead of silently defaulting to a two-player framing. When
  referring to who defends or is affected, say "defending player(s)"
  (plural-aware) rather than assuming there is exactly one, since some
  multiplayer variants can have more than one. If the provided context
  only contains two-player-framed rules, say your answer is for the
  two-player case and that a multiplayer table may follow different rules
  -- do not invent multiplayer rules that weren't provided.
```

This keeps v3's core "don't invent ungrounded multiplayer rules" guardrail (the thing its own risk table worried about) while adopting Jon's exact "state each outcome separately... if they are the same, state that instead" framing and the "defending player(s)" plurality fix from the q014 notes. **Not** adding a literal 507.1/802.2 citation into the prompt — v3 §5 already rejected hardcoding specific CR numbers as overfitting to one gold set, and that reasoning still holds; the plurality/wording fix generalizes, a hardcoded rule number wouldn't.

### 4c. Assumption disclosure, generalized — REVISES v3 §1d in place (same insert point, after "Keep the answer accurate and to the point...")

v3's §1d only covered *timing* assumptions. Generalizing it to any unstated fact (mana values, zones, player count, timing) does the work items 1d and the new "state assumptions explicitly" requirement both want, in one bullet instead of two — saves tokens versus adding a second, narrower bullet:

```
- When the answer depends on a fact the question doesn't state (an
  unknown mana value, an unspecified zone, an ambiguous order or timing,
  an uncertain player count, etc.), say plainly what you assumed instead
  of silently picking one option. If a different assumption would change
  the answer, add one short sentence on how. This is disclosure, not a
  request for more information -- answer with your best assumption
  stated, don't ask the question back to the user.
```

Bridges toward the "clarify-then-escalate" idea raised in several grading notes (c004, q016, c011, c012) without adding a schema field or an extra round trip — exactly the scope boundary v3 §5 already drew ("explicitly a separate, later piece of work"). `gpt-5-mini_C_r2:c011` is the model example to hold this bullet against: Jon's note there — *"this is the most correct answer so far, and clearly outlines the assumptions it makes... this could be something we integrate into our system prompts"* — is a direct, on-the-record request for this exact behavior.

### 4d. Answer the intended question, not just the literal one — NEW bullet, insert immediately before v3 §1f (the direct-answer-first bullet)

Targets c019 and q008. Proposed text:

```
- Answer the practical question a player is actually asking, not only the
  narrowest literal reading of the words. If the situation clearly
  involves resolving multiple copies or instances of an effect and the
  literal wording could be read as asking about just one, answer the
  practical version (e.g. the total after everything resolves) first, and
  only note the narrower literal reading afterward if it's genuinely
  ambiguous which one was meant.
```

Placed right before the existing direct-answer-first bullet (§1f) so the two work as a pair: first figure out which question is actually being asked, then open with a direct answer to that question.

### 4e. Reinforce direct-answer-first — AMENDS v3 §1f in place, same bullet, added clause

The gemini "state wrong answer, then correct it" pattern (c002-style) is still showing up per the backlog notes on gemini's c002 draws. Append one explicit clause to the existing §1f bullet rather than adding a new one:

```
[... existing §1f text unchanged, then append:] Never write a claim in the
text field that you're about to contradict a sentence later -- work out
the right answer before writing, then write only that; if you catch a
false start, discard it rather than "correcting" it in place.
```

---

## 3. TheJudge-derived candidate additions (separate track — techniques, re-expressed, not from Jon's graded notes)

These come from the full-prompt comparison in §0, not from a specific grading note. Each is marked with what it does, whether we already do it, its token cost, and whether it's worth adopting.

| Technique (re-expressed in our words) | What it does | Do we already do it? | Token cost if adopted | Worth it? |
|---|---|---|---|---|
| **3a. Conditional/targeted instruction rendering** (from `phaseGuidance.ts`'s per-phase text) | Render a targeted instruction block only when it's actually relevant to the current question, instead of a static block on every call | No — our SYSTEM is monolithic today | **Saves** tokens on non-applicable questions (roughly -210 tokens on the ~31 rules-only questions if applied to 4a) | **Yes** — already folded into §5's gating proposal for 4a; this is the citation for why that's a sound pattern, not a speculative one |
| **3b. Redundant-emphasis phrasing for high-priority behaviors** (TheJudge states "state assumptions/uncertainty" twice, in two different sections) | Repeats a critical instruction briefly in two places (once in the opening framing, once in the detailed bullet) instead of stating it once | Partially — we state assumption-disclosure once, in 4c, at length | A short intro-paragraph clause, ~15-20 tokens (e.g. appending "state assumptions when the context doesn't cover something" to the existing intro paragraph, in addition to keeping 4c's full bullet) | **Marginal, optional** — cheap enough to include as a low-cost reinforcement, but not required; flagged as an open question (§9) rather than a firm recommendation, since it's unproven whether repetition helps an LLM follow an instruction versus just costing extra tokens for no behavior change |
| **3c. Graceful section-budget truncation** (`cardRulings.ts`'s `resolveRulingsForPrompt`: squeezes in a truncated partial ruling rather than dropping a card's data entirely when a section budget is exceeded) | Engineering technique for context assembly — caps a section's total character budget while gracefully degrading (partial data) instead of hard-dropping | Not confirmed — our card/ruling formatting (`_format_cards`, mini-RAG ruling selection) does relevance-based selection but no explicit character-budget-with-graceful-truncation logic | N/A — this is a **code change to context assembly**, not a SYSTEM-string change | **Out of scope for this plan** (SYSTEM-string only); worth a separate, small follow-up ticket against `_format_cards`/`_format_context` if long card-data blocks ever get large enough to matter |
| **3d. Runtime prompt-size diagnostics** (`promptDiagnostics.ts` reports per-section character counts alongside every answer) | Observability: measure and log the size of each prompt section on every real generation call, not just in eval runs | No — we track token budgets only via this plan's estimates and the eval harness, not per-call in production | Zero prompt tokens (it's a logging/diagnostics addition, not prompt content) | **Yes, recommended** — directly complements this plan's own "token bloat is the key risk" concern (§5); logging system-prompt + context character counts per call would let bloat regressions (e.g. if 4a's mana block or a future addition creeps) get caught from real traffic, not just the next eval run. Not a prompt-wording change — a small addition to `answer.py`/logging, flagged here for awareness, not sized or scoped as part of this plan |
| **3e. "Not an official ruling" disclaimer** | Explicit authority-scoping disclaimer | No | ~15 tokens | **Not recommended** — see §0; undercuts our actual value proposition (citing real CR text/rulings) and no grading note asked for it |

**Net effect on the token budget**: only 3a and 3b touch prompt tokens. 3a is folded into §5 already (a token *saving* on non-card questions once gated). 3b is a small, optional +15-20 tokens, called out as an open question rather than folded into the default plan.

---

## 4. Token-budget table

| Item | Action | v3 tokens (approx) | v4 tokens (approx) | Delta |
|---|---:|---:|---:|---:|
| 4a mana notation+arithmetic | replaces §1b | ~120 | ~330 | +210 |
| 4b multiplayer | revises §1c | ~65 (net of v2 bullet, per v3 table) | ~110 | +45 |
| 4c assumption disclosure | revises §1d (broadens scope, same slot) | ~95 | ~95 | 0 (same bullet, reworded, not longer) |
| 4d answer-intended-question | new bullet | — | ~75 | +75 |
| 4e direct-answer-first reinforcement | amends §1f | (included in v3's ~120 for 1f) | +30 | +30 |
| 3b (optional) redundant-emphasis intro clause | amends intro paragraph | — | ~15-20 | +15-20 (optional, not in the default total below) |
| **Total delta vs. v3 (4a-4e only, default)** | | | | **~+360** |

**v3 baseline: ~3.1k tokens. v4 (all Jon-driven items, ungated): ~3.1k + ~360 ≈ 3.46k tokens, roughly +12% on top of v3's already-flagged +20% over v2** — i.e., v4 alone is a smaller percentage jump than v3 was, but it's stacked on v3's increase, so the two-generation compounded growth is v2's ~2.6k → v4's ~3.46k, **+33% total** across both rounds. That compounding is the number Jon should see, not just the v3→v4 delta in isolation.

If §5's gating idea is adopted for 4a (mana block rendered only on cost-bearing questions), the **average** per-call cost across the full 50-question eval set drops close to v3's baseline (roughly +150 tokens net, since only ~19 of 50 questions are card-interaction questions) even though card-interaction questions specifically pay the full +360.

---

## 5. THE KEY RISK — stacking bloat on an already-flagged-risky arm

v3's own risk table named `1c` (multiplayer) as **the highest-risk item in the core bundle** for tempting a model into ungrounded claims, and separately flagged that `gemini-flash-lite` is "the weakest at holding multi-instruction prompts together" — meaning the token increase itself, independent of any single bullet's wording, was already a live regression vector on that arm. v4 adds ~360 more tokens (or a compounded +33% versus the pre-v3 baseline) directly on top of that. This is not a hypothetical: v3's go/no-go criteria already built in a groundedness-spike check specifically because of this risk, and that check should be watched even harder for v4.

**Proposed mitigations, in priority order:**

1. **Test v4 the same disciplined way v3 was tested** — re-run all arms, judge-compare against **v3 as the new baseline** (not v2), double-run for stability per v3's own §4 methodology, and have Jon hand-grade only stable diffs. Do not shortcut this because v4 is "smaller" than v3 — the compounded token count says otherwise.
2. **Make the mana-math block (4a) conditional**, rendered only when the question or the retrieved/attached card data actually involves a mana cost (e.g., `cards` is non-empty and at least one card has a non-trivial `mana_cost`, or the question text matches a cost/mana keyword heuristic). TheJudge's phase-scoped guidance injection (§0/§3a) is real precedent that a comparable production system already does this kind of conditional-block pattern successfully. This caps the token hit to the ~19 card-interaction questions instead of taxing all 50, and specifically protects `gemini-flash-lite` on the 31 rules-only questions that never needed mana arithmetic in the first place.
3. **Watch `gemini-flash-lite` first and separately** in the v4 A/B — it's the arm v3's own analysis flagged as most bloat-sensitive, so it should be the canary, not an average-in.
4. **Keep the same no-go trigger v3 used**: any net correct-count drop on the incumbent (`claude-sonnet-5`) on stable flips is a no-go, full stop, regardless of what v4 gains elsewhere.

---

## 6. TDD / eval note

- Bump `PROMPT_VERSION`: 3 → 4 in `answer.py`, per the file's own stamped-version convention (docstring comment lines 38-43 currently list v1/v2/v3 — v4's entry would document 4a-4e here the same way).
- Regenerate `tests/fixtures/prompt_identity.json` against the new v4 SYSTEM string, same as v3's step, so the OpenRouter A/B harness's byte-identical-prompt guarantee stays true for the new baseline.
- **If the conditional gating in §5 item 2 is adopted, this breaks the simple byte-identical assumption** the existing harness relies on — the prompt would no longer be a single fixed string but one of (at least) two variants depending on whether card/cost data is present. This needs an explicit decision from Jon (see open questions) before implementation: either (a) the fixture and harness are extended to cover both variants deterministically, gated on the same input condition every arm sees identically, or (b) gating is deferred to a later, separately-versioned change and v4 ships the mana block ungated for this A/B, accepting the full token cost across all 50 questions to keep the harness simple. Recommend (b) for the first v4 test pass — it's the smaller change to the test harness — with gating proposed as a v4.1 follow-up once the ungated numbers are in hand.
- Same eval sources as v3 (`evals/questions.jsonl`, `evals/cards.jsonl`, hand-verdicts), no new eval questions required — c014, c002, c011, c012, q008, q014, q019, q026 are the specific items to re-check in the diff review.

---

## 7. Considered and rejected

- **Copying TheJudge's section-labeled prompt structure wholesale** (SYSTEM ROLE PREAMBLE / INSTRUCTIONS / MTG REFERENCE style headers). Rejected: no evidence it fixes anything we're missing (TheJudge doesn't solve mana math either, has no citation schema, no tldr — see §0), it's a bigger structural rewrite of a prompt that v3's own plan already argued against rewriting wholesale (loses whatever's implicitly working, harder to attribute regressions), and our existing terse-bullet style already reads as one voice.
- **A code-level mana-cost parser/calculator called before generation**, instead of teaching the model the arithmetic in-prompt. Rejected for this pass: it's a code change (parsing `{N}{G}...` strings, applying reduction/floor effects programmatically), not a prompt change, and is explicitly a different, larger-scoped project — worth a separate plan if the in-prompt fix proves insufficient after this A/B, but not something to fold into a system-prompt plan.
- **A second, dedicated LLM call to pre-compute mana math** (mirroring the rewriter pattern) **before the main generation call.** Rejected/parked: real latency and cost (another full API call on every card-interaction question), a materially different-shaped change than a wording edit, and unproven need until the in-prompt worked-example approach (§2's 4a) has actually been measured and found insufficient.
- **Hardcoding 507.1/802.2 rule numbers into the multiplayer bullet.** Rejected, consistent with v3 §5's identical rejection for the same reason: overfits to this eval's gold set, is brittle across CR renumbering, and does nothing if those chunks aren't retrieved (a retrieval-side gap, out of scope for a prompt plan).
- **Adopting TheJudge's locally-scoped, data-adjacent authority disclaimers** (restating precedence rules right next to the rulings/rules data blocks, not just once in the system prompt — §0). Rejected for v4 specifically: it changes context/data formatting (`_format_context`/`_format_cards`), not the SYSTEM string, and this plan is scoped to system-prompt changes only — noted as a future idea, not proposed now.
- **Adopting a "not an official ruling" disclaimer** (§3e). Rejected: undercuts our core value proposition of citing real CR text/rulings; no grading note asked for it.

---

## 8. Non-goals

- No `Answer` schema change (no scratch/reasoning field, no clarification field) — same hard constraint v3 operated under.
- No per-model system prompts — the whole point of the eval methodology is identical prompts across arms.
- No retrieval or `TOP_K` changes.
- No `rewrite.py` changes in this plan (v3's §2a/§2b rewriter-side mana/multiplayer phrasing already shipped as part of v3's `"v2"` rewriter bump; this plan doesn't propose further rewriter edits).
- No context-assembly / code changes (§3c graceful truncation, §3d runtime diagnostics, §0's locally-scoped disclaimers) — flagged as separate future ideas, not part of this SYSTEM-string-only plan.

---

## 9. Open questions for Jon

1. **Worked example in 4a**: keep the inline worked example (the single biggest token add in this plan, ~210 tokens net) or trust the legend + arithmetic rules alone and see if that's enough on its own first? The example is the part most likely to actually fix c014-class failures, but it's also the most expensive single addition here.
2. **Conditional gating for 4a**: is breaking the byte-identical-prompt assumption (needing the harness to handle two prompt variants) acceptable to unblock the gating win in §5, or should v4's first test pass ship ungated (full token cost on all 50 questions) and defer gating to a v4.1 follow-up? §6 recommends deferring, but this is Jon's call given it directly affects how the A/B is measured.
3. **Go/no-go threshold**: keep v3's exact criteria (no net sonnet regression, groundedness-spike cap at 1-2 questions), or tighten it given v4 is stacking on top of v3's already-spent budget — e.g., should a `gemini-flash-lite` regression by itself (even if other arms improve) be a separate no-go trigger this time, given it's the specifically-flagged canary arm?
4. **4c's scope**: is generalizing the timing-only bullet (v3 §1d) into an all-purpose "state any unstated assumption" bullet the right call, or does Jon want timing kept as its own explicit case (i.e., two bullets, at a token cost) because timing assumptions showed up as a distinct, recurring failure (c004) worth naming on its own?
5. **3b's redundant-emphasis clause**: worth the small +15-20 tokens to restate assumption-disclosure briefly in the intro paragraph as well as in the full 4c bullet, or is one clear statement (4c) enough and a second mention just adds cost without a known behavior benefit?
