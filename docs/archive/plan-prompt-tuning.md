**APPROVED by Jon 2026-07-22, with amendments (see §4): B/C/D condition split, double-run all arms, Part B union as condition D, §2c parked, c004-ruling baselines (46/44). Originally a Fable-authored DRAFT under Rule 0.**

# Prompt-Tuning Plan: Rulemancer Generator + Rewriter

Source evidence: `data/parsed/answer_verdicts (2).json` (56 hand-verdicts, ids `arm:questionId`), `evals/verdicts_deepseek-v3-2.json` (50 verdicts, deepseek-v3.2 baseline arm), `evals/questions.jsonl` (31 rules Qs), `evals/cards.jsonl` (19 card-interaction Qs). Current prompt-assembly code: `src/rulesagent/generate/answer.py` (`build_prompt`, `SYSTEM`, `PROMPT_VERSION = 2`, `Answer` schema in `src/rulesagent/contracts.py`), and `src/rulesagent/retrieve/rewrite.py` (`SYSTEM`, `PROMPT_VERSION = "v1"`).

Judge prompt (transitive grading pipeline) is **out of scope** — no changes proposed there.

---

## 1. System-prompt additions (generator, `answer.py`)

The current `SYSTEM` string is a paragraph plus 11 bullets (numbered `[1]`–`[11]` below for reference; numbers are my labels, not in the source). All insert points are relative to this numbering. Every addition below is a plain bullet in the same terse imperative style already used, so it reads as one voice, not a patchwork.

```
[intro paragraph] "You are a Magic: The Gathering rules expert. Answer the
  user's question using ONLY the numbered rules provided in the context
  below. Rules are labeled with their number in brackets, e.g. [104.3a]."
[1] "Cite the exact rule numbers you relied on in the citations field. ..."
[2] "If the provided rules don't contain enough to answer, set answered to
  false ..."
[3] "Define any key term the question hinges on ..."
[4] "Name the specific zones, steps, or objects involved ..."
[5] "If the provided rules cover multiplayer or Commander cases, address
  them too, not just the two-player case."
[6] "Keep the answer accurate and to the point; a player should be able to
  act on it."
[7] "You may also be given specific cards' oracle text and rulings,
  labeled "Card data" below the rules context. ..."
[8] "A provided ruling is itself authoritative, self-sufficient
  grounding. ..."
[9] "Card rulings in the context are labeled like "[Card Name ruling #4]". ..."
[10] "Fill the tldr field with one or two plain sentences ..."
[11] "Fill suggested_followups with two or three short natural next
  questions ..."
```

### 1a. New bullet — insert as the new first bullet, immediately before `[1]`

Targets **F1** (card-role confusion). Jon's explicit directive: always use full card names, every reference.

```
- Always refer to a card by its exact full name, every time you mention it
  in your reasoning and in the answer text -- never by a role word ("the
  attacker," "the blocker," "the creature," "it") once two or more named
  cards are in the question. If you find yourself about to write a role
  word for a card, stop and substitute its full name instead.
```

**Predicted flips:** `deepseek-v4-flash:c002`, `gemini-flash-lite:c002` (both wrong on Charging Rhino/Vampire Nighthawk — the note is a textbook example: "still assuming that charging rhino is the creature with deathtouch when its not"), `deepseek-v3.2:c002` (also wrong, same failure). No change predicted for `deepseek-v4-pro:c002`, `gpt-5-mini:c002`, `sonnet-v2:c002` — already correct.

### 1b. New bullet — insert immediately after `[3]` ("Define any key term...")

Targets **F2** (mana-symbol semantics).

```
- Mana symbols are not interchangeable. {N} (a plain number) means N
  generic mana, payable with any color or with colorless mana. {C} means
  colorless mana specifically -- it is NOT generic and NOT interchangeable
  with {N}. {G}/{U}/{B}/{R}/{W} mean mana of that one color specifically.
  When a cost-reduction or cost-increase effect says it reduces or
  increases "the mana cost" or "the generic mana" of a spell, only the
  generic portion changes -- any colored or colorless symbols in the cost
  are unaffected. When you state a resulting total cost, break it out by
  symbol rather than only giving a lump number.
```

**Predicted flips:** `gemini-flash-lite:c014` (wrong — claimed a {1} reduction cut {G} mana), `gpt-5-mini:c014` (partial — conflated the {1} generic reduction with a color-split ambiguity that doesn't exist), `deepseek-v3.2:c014` (partial — said the total was "3 of any color" when it's `{1}{G}{G}`). No verdict on record for `sonnet-v2:c014` or `deepseek-v4-flash:c014` — untested arms for this question, flag as unknown.

### 1c. Replace `[5]`

Targets **F4** (multiplayer defaults).

```
OLD: "- If the provided rules cover multiplayer or Commander cases,
  address them too, not just the two-player case."

NEW: "- Unless the question specifies exactly two players, don't assume a
  two-player game. If the provided context includes any rule about
  multiplayer play (choosing a defending player, "each opponent," turn
  order among more than two players, etc.), say how the answer differs, if
  at all, between two players and more than two. If the context contains
  ONLY two-player-framed rules, say plainly that your answer is for the
  two-player case and that a multiplayer table may follow different rules
  -- do not invent multiplayer rules that weren't provided."
```

**Predicted flips:** `deepseek-v4-pro:q014`, `gemini-flash-lite:q014`, `gpt-5-mini:q014` — all graded partial with near-identical notes ("507.1 and 802.2 should also be surfaced," "needs to be added to all of the multiplayer combat gold rules"). **Important hedge:** the gold context for q014 (`506.1`, `117.3a`) does not currently include 507.1/802.2 — if those chunks aren't in the retrieved context, this bullet can only make the arm **honestly scope its answer to two-player and say so**, not conjure the missing rule. That's still a real improvement (an honest partial beats a silent one), but it is not guaranteed to move partial → correct on its own; it's a necessary-but-maybe-not-sufficient fix. See §2b for the rewriter-side complement.

### 1d. New bullet — insert immediately after `[6]` ("Keep the answer accurate and to the point...")

Targets **F5** (unstated timing/ordering assumptions).

```
- If the order or timing of events in the question is ambiguous (for
  example, exactly when damage was marked relative to a spell being cast
  or resolving), say plainly which timing you're assuming, then add one
  short sentence on how the answer would change under a different timing.
  Never resolve an ambiguous timing question as if only one order were
  possible without saying so.
```

**Predicted flips:** ~~`deepseek-v4-pro:c004` and `sonnet-v2:c004`~~ **OFF THE BOARD (2026-07-22): Jon's c004 ruling flipped both to correct-with-note before this A/B ran (see DECISIONS.md), so neither can flip on count.** This bullet is now justified on disclosure quality (making arms *state* the timing assumption Jon's note flagged) and the lower-confidence `deepseek-v3.2:c004` — graded flat-out wrong with a substantively different SBA-timing conclusion, not just an undisclosed assumption, so this bullet may only make the wrongness more legible, not correct it outright. If v3 answers disclose the assumption where v2 answers silently assumed, that's the win to look for in the diffs even with zero count movement.

### 1e. New bullet — insert immediately after `[7]` (the "Card data... Treat that as additional ground truth" bullet)

Targets **F7** (card-text-overrides-rules).

```
- A card's own printed rules text always wins over a general rule it
  contradicts. If a card's text says something that conflicts with how a
  general rule would otherwise apply, follow the card's text and say so
  explicitly (name the specific text and note that card text overrides the
  general rule) rather than applying the general rule as if the card were
  silent.
```

**Predicted flips:** `deepseek-v4-flash:c016` (wrong on Skullbriar — Jon's note: "we need to make sure we get the rule that states something like 'text on the card overrides rules' for this one"). High confidence — this is a direct, literal match to the stated fix.

### 1f. New bullet — insert immediately after `[9]` (the ruling-label bullet) and before `[10]` (tldr)

Targets **F3** (intent misses) and **F6** (answer clarity) together — merged into one bullet since they're the same underlying "don't bury the direct answer" behavior, and merging saves ~60 tokens versus two bullets.

```
- Open the text field with a direct, unmistakable answer to the question
  -- the first sentence or two should say plainly what happens, not lead
  with caveats or setup. Put reasoning, assumptions, and secondary
  discussion after that direct answer, never before it. If the question
  can reasonably be read two ways (for example, "who gets priority" could
  mean right after a spell is cast or right after it resolves), answer the
  reading actually asked first and explicitly, then briefly cover the
  other reading if it's a likely point of confusion -- don't let a second
  reading delay or bury the direct answer to the first.
```

**Predicted flips:** no hard wrong→correct flip predicted (the arms already graded on the referenced questions were already correct) — this is a **quality-preserving / regression-preventing** bullet, not a wrong-answer fix:
- `deepseek-v4-flash:q026` — already correct, but Jon's note flags exactly the failure mode this bullet targets: "the clarification at the end... gets in the way of the actual question being answered a bit." Predicted: stays correct, becomes cleaner.
- `gpt-5-mini:q026` — this bullet effectively **codifies the behavior Jon already singled out as the best answer** ("hands down the best answer... very clear on both... questions"). It should make that behavior the norm across arms rather than the exception.
- `deepseek-v3.2:q008` — wrong, and the note ("focusing on the resolves part too much... the question is really...") is partly an intent-reading miss. Moderate confidence this bullet helps by forcing the model to state which reading it's answering; low confidence it fixes the underlying reasoning gap on its own, since q008's miss looks more like a genuine interaction-rules gap than a phrasing/ordering one.

### Token cost (generator system prompt)

| Addition | Approx. added tokens |
|---|---:|
| 1a (full names) | ~55 |
| 1b (mana symbols) | ~120 |
| 1c (multiplayer, net of replaced bullet) | ~65 |
| 1d (timing assumption) | ~95 |
| 1e (card-text-overrides) | ~65 |
| 1f (direct-answer-first + dual-reading) | ~120 |
| **Total** | **~520 (~2.6k → ~3.1k, +20%)** |

That's a real increase, not a rounding error — flagged plainly in §4's go/no-go and §5's rejected alternatives (a full-prompt rewrite was considered and rejected partly *because* of this budget concern).

---

## 2. Rewriter-prompt changes (`rewrite.py`)

Current `SYSTEM` (verbatim, lines 52–71) ends in a `Requirements:` list of 4 bullets. `PROMPT_VERSION = "v1"` gates the on-disk rewrite cache (`data/cache.db`, `rewrite` table) — **any change to `SYSTEM` must bump this string** (proposed: `"v2"`) or stale rewrites made under the old wording will keep being served forever from cache.

### 2a. New bullet — insert after "Never include rule numbers..." and before "Each rewrite is a self-contained question..."

Targets **F2**, per Jon's explicit suggestion that the rewriter expand mana symbols to words.

```
- If the question contains a mana symbol in curly braces (like {1}, {G},
  {C}, {X}), spell it out in the rules' own words in your rewrite instead
  of using the symbol: {1} -> "one generic mana", {G} -> "one green mana"
  (same pattern for {U}/{B}/{R}/{W}), {C} -> "one colorless mana", {X} ->
  "X mana" or "an amount of mana equal to X". Do not use the symbol itself
  in the rewrite -- the corpus is prose, not symbol notation, and a
  literal brace character rarely matches.
```

**Honest hedge:** none of the 106 graded answers reviewed shows a *retrieval* failure attributable to literal `{...}` notation in the user's question (none of the 31+19 questions actually contain brace notation — they're all natural language). c014's failure (the graded F2 example) was diagnosed by ablation as **reasoning-side**, not retrieval-side (the sanity check held: removing the cited CR rules didn't break the answer). So this bullet is **preventive, not a confirmed fix** — included because Jon asked for it and because it costs little, but it should not be marketed as "the c014 fix." §1b (generator side) is the actual c014 lever.

### 2b. New bullet — insert after 2a, before the clarification bullet

Targets **F4**, as a rewriter-side complement to §1c (since REWRITE_N=1 in production, this must be phrasing *within* the single rewrite, not "produce another rewrite").

```
- If the question doesn't say how many players are in the game, include
  multiplayer-relevant phrasing in the rewrite too (for example, mention
  "the defending player" or "when there is more than one opponent")
  alongside the ordinary two-player phrasing, so multiplayer-specific
  rules can be found without dropping the two-player rules.
```

**Predicted effect:** this is the piece that could actually close the gap §1c can't close alone — if this bullet gets the rewriter to phrase the search query so it retrieves 507.1/802.2-class chunks for q014, then §1c's generation-side instruction has real material to work with, and the partial→correct flip predicted in §1c becomes plausible rather than aspirational. Recommend re-checking q014's *retrieved chunk list* specifically (not just the final answer) in the A/B to see whether this bullet changed what got retrieved.

### 2c. Design option (Jon's proposal, mid-task): rewriter-stage oracle-text pass-through

**Proposal as stated:** append referenced cards' oracle text to the rewriter's input before rewriting, with a structural (not instructional) guarantee that the rewriter cannot re-emit that text into what the generator treats as ground truth.

**Validating the controller's framing against the code:**

1. **Structural pass-through — confirmed sound.** The rewriter's output schema (`_Rewrites`: `queries: list[str]`, `clarification: str | None`) has no field for card text, so there is no path for oracle text to leak into the generator's ground-truth "Card data" block through the rewriter's structured output — that block is built by `_format_cards()` in `answer.py` directly from the `Card` objects fetched via `get_card()`, entirely independent of anything the rewriter returns. No LLM sits in that path today, and this design doesn't add one. The guarantee holds **by construction**, not by trusting the model to behave.

2. **Pipeline ordering — already satisfied, no reorder needed.** The controller's framing assumed card-ref detection + Scryfall fetch would need to move ahead of the rewrite step. Checking `RulesAgent.answer()` (`answer.py` lines 295–365): `parse_card_refs` → `get_card` (via the `all_refs` loop) → `ruling_select` all run **before** the `if self.rewrite:` block that calls `rewrite_query()`. `cards` is already fully resolved, oracle text and all, by the time a rewriter call would happen. This is good news — implementing this design is a smaller lift than the framing implied; it's "thread an already-computed value into one more function call," not "reorder the pipeline."

3. **Cache-key consequence — a real, necessary change.** `rewrite_query()`'s cache key today is `json.dumps([model, PROMPT_VERSION, n, question])` — keyed on question text only. If oracle text enters the rewriter's input, the key **must** also incorporate a fingerprint of the card data (e.g. `sorted([(c.name, hashlib.sha256(c.oracle_text.encode()).hexdigest()[:12]) for c in cards])`), or a card that gets errata'd (Scryfall oracle text changes) will silently keep serving a rewrite computed against the old wording — a correctness bug that's invisible until someone notices a stale ruling. This is a design *requirement* for whoever implements this, not optional hardening.

4. **Expected wins, by class:**
   - **c002-class (F1, card-role grounding):** seeing which card's oracle text actually says "deathtouch" vs. "trample" lets the rewriter (and therefore retrieval) get the attribution right *before* generation ever sees the question — a second, earlier layer against the same failure §1a targets at generation time. Deliberately redundant with §1a, not wasted: two independent layers catching the same failure mode is a reasonable hedge given how consistently F1 shows up (3 of 6 arms wrong on c002 alone).
   - **c014-class (F2, mana semantics):** seeing the *actual* `{1}{G}{G}` cost and Trinisphere's floor-of-3 oracle text lets the rewriter phrase a query against the real cost structure instead of guessing — a card-specific, stronger version of §2a's generic symbol-expansion, but only for card-interaction questions (19 of 50).
   - **c010/c019-class (ruling retrieval robustness):** both already graded correct across arms reviewed, so this isn't fixing an observed failure — it's a hedge against future/unseen card-interaction questions where retrieval currently guesses at vocabulary the card's own text would have handed it directly.
   - **c012 — does NOT fix it, and shouldn't be sold as if it might.** See the root-cause note in §7 below: c012's symptom is oracle text missing from the *generation* prompt for a secondary referenced card, not a rewriter-input problem. This design changes what the rewriter sees; it does not touch `_format_cards()` or the generation-prompt card block at all. Keep these two problems visibly separate so a future reader doesn't credit this design with a fix it can't deliver.

5. **Token and risk tradeoff.** Haiku is cheap ($1/$5 per MTok), but oracle text is real added tokens: roughly 50–150 tokens per card (name + mana cost + type + oracle text), so a 3-card question like c012 adds ~150–450 tokens to a rewriter call currently sized at `max_tokens=2048` for a bare question. Two mitigations, both load-bearing:
   - **Gate on `cards` being non-empty.** Rules-only questions (31 of 50) get zero added input tokens and zero behavior change — this is what makes the change asymmetric-risk-free for the majority of the eval set, by construction, not by hoping the model ignores an empty block.
   - **New role-boundary instruction, required alongside the pass-through:** *"You are given card text only to phrase better search queries -- do not use it to answer the question, judge legality, or resolve the interaction; that is the generator's job, not yours."* Without this, richer input (full oracle text, not just a bare question) plausibly pulls Haiku out of its narrow translation role and toward attempting the actual ruling in `clarification` or a query — a schema-adjacent behavior drift that's specific to this design and doesn't apply to §2a/§2b's plain wording tweaks.

**Recommendation:** treat this as a **separate, larger prompt version** (`rewrite.py` `PROMPT_VERSION = "v3"`, not folded into the `"v2"` bump for §2a/§2b), gated behind its own flag (e.g. `card_context_in_rewriter: bool`, mirroring the existing `ruling_select`/`show_rewrite` pattern in `RulesAgent.__init__`), and A/B'd independently so its effect isn't conflated with the mana/multiplayer wording changes. It's a genuinely different kind of change — new code path, new cache-key shape, a new failure mode (role drift) — not a same-shape wording edit, and it deserves to be judged on its own numbers.

---

## 3. Risk analysis

| Change | What could regress | Models most at risk | Detection in the 300-answer grid (6 arms × 50 Qs) |
|---|---|---|---|
| 1a full names | Verbose over-repetition of long card names; unlikely to flip correct→wrong | None specifically — low risk across the board | Compare answer length / readability on already-correct card-interaction answers (c001–c019) across all 6 arms; watch for a text field that reads as a name-repetition drill |
| 1b mana symbols | Weak models misapply the generic/colored distinction and introduce a *new* wrong claim on a question that didn't need this reasoning at all | `gemini-flash-lite` (already weakest at multi-step reasoning), untested arms on c014 (`sonnet-v2`, `deepseek-v4-flash`) | Any card-interaction question involving a cost modifier (c014 and any future ones) graded wrong post-v3 where it was correct pre-v3; check specifically for a NEW mana-arithmetic claim that wasn't in the v2 answer |
| 1c multiplayer default | **Highest-risk item in the core bundle.** Directly tensions with the system prompt's foundational groundedness rule ("ONLY the numbered rules provided") — an instruction to "say how the answer differs... between two players and more than two" can tempt a model to state multiplayer facts from training data when the context doesn't actually contain multiplayer rules, even though the bullet explicitly forbids it | All arms, including `sonnet-v2` (the incumbent, which has never needed to reason about ungrounded content before) | Any combat/priority/timing question (q005, q006, q014, q015, q021, q026–028) where `answered: true` but a cited rule number does NOT appear in the provided context's rule-number set — this is the automated groundedness check the answer-eval harness should already run; a spike in it post-v3 is the signal |
| 1d timing assumption | Adds hedging/disclaimer language to already-clean answers on questions with no real timing ambiguity, hurting F6 clarity in the opposite direction | Any arm on non-ambiguous questions (most of the 31 rules-only Qs) | Read-back on 5–10 already-correct rules-only answers for new hedge language that adds nothing (an over-triggering false positive) |
| 1e card-text-overrides | Spurious invocation of "card text overrides the rule" to justify an answer where no real conflict exists | Weaker arms reaching for a plausible-sounding justification (`gemini-flash-lite`, `deepseek-v4-flash`) | Any citation to "card text overrides" language in the text field where the cited card's oracle text, on inspection, doesn't actually conflict with anything |
| 1f direct-answer-first / dual-reading | Redundant restatement between `tldr` and the opening of `text` (both now front-load the answer) — a quality nit, not a correctness risk | All arms, mildly | Read-back for `tldr` and the first sentence of `text` being near-duplicates on 5–10 answers |
| 2a rewriter mana-symbol wording | Haiku mis-expands a symbol (e.g., conflating `{C}` and generic) inside the rewrite, which then *worsens* retrieval for that question versus not rewriting it at all | The rewriter model itself (`claude-haiku-4-5`) on any mana-cost-bearing question | Diff the retrieved chunk ranking for mana-cost questions (q004, c014, and any others) between v1 and v2 rewrites — a rank regression on the correct chunk is the signal |
| 2b rewriter multiplayer phrasing | Same class of risk as 1c but one level removed — a mis-phrased "multiplayer-relevant" rewrite could drift the search query away from the two-player rules that still answer most of these questions | `claude-haiku-4-5` | Diff retrieved chunks for q005/q006/q014/q015/q021/q026-028 between v1 and v2 rewrites; watch for the two-player-relevant chunk (e.g. 117.3c for q026-028) dropping out of top-k |
| 2c oracle-text pass-through (design option) | **Role drift**: Haiku, given richer input, starts trying to resolve the interaction inside `clarification` or biases `queries` toward a specific verdict instead of neutral search phrasing; also the single biggest token-cost and cache-correctness risk (stale rewrite on errata) if the fingerprinted cache key isn't implemented correctly | `claude-haiku-4-5`, and indirectly every generator arm that then searches on a biased query | Compare `clarification` field contents pre/post on card-interaction questions for verdict-like language ("this means X happens") rather than a search angle; separately, a card whose Scryfall oracle text changes between two eval runs serving an identical rewrite is the cache-key-bug signal |

---

## 4. A/B measurement plan — AMENDED 2026-07-22 per Jon's rulings (this section supersedes the original single-run design)

**Jon's rulings on record (2026-07-22):** adopt the 6+2 bullets; split the A/B for attribution; double-run every arm; A/B the Part B ruling-query union as its own condition instead of blind-shipping it; §2c stays parked (own flag/version when picked up); RulesGuru-150 extension happens after this A/B. Also: c004 was flipped to correct-with-note before this A/B (see DECISIONS.md), so baselines below are the post-ruling numbers.

1. **Version bumps.** `answer.py` `PROMPT_VERSION`: 2 → 3 (system-prompt changes, §1). `rewrite.py` `PROMPT_VERSION`: `"v1"` → `"v2"` (§2a + §2b). §2c is parked and keeps its reserved `"v3"` + own flag for whenever it's picked up.
2. **Regenerate the prompt-identity fixture** (`tests/fixtures/prompt_identity.json`, per `build_prompt`'s docstring) against the new v3 system prompt, so the byte-identical-prompt guarantee the OpenRouter A/B harness depends on stays true for the new baseline.
3. **Four conditions, attribution ladder** (each step changes exactly one lever vs the step before):
   - **A — baseline (free):** gen-v2 + rewrite-v1 + no union = the verdicts already on file. Not re-run.
   - **B — generator wording only:** gen-v3 + rewrite-v1 + no union. B−A isolates the six §1 bullets.
   - **C — plus rewriter wording:** gen-v3 + rewrite-v2 + no union. C−B isolates the two §2 bullets (check q014's retrieved-chunk list here, per §2b).
   - **D — plus Part B union:** gen-v3 + rewrite-v2 + ruling-query union ON. D−C isolates Part B's end-to-end answer effect (its retrieval-level 16/25→20/25, 0-regression result is already on file; this measures whether that reaches final answers). If D ≥ C, Part B ships with v3.
4. **Run every condition twice per arm, all 6 arms** (B, C, D × 2 runs × 6 arms = 36 fifty-question runs; tokens are cents for the cheap arms, low single-digit dollars for sonnet). First step before any run: check what the harness actually pins (temperature/seed/retries) and record it — determinism status goes in the run log either way; the double-run stands regardless (Jon's call, belt-and-suspenders at ±1 margins).
5. **Judge-compare each run against A** with the existing transitive-grading pipeline (frozen judge, unchanged). A flip counts as **stable** only if both runs of that condition agree on it; unstable flips are logged but excluded from go/no-go arithmetic and from Jon's queue.
6. **Jon hand-grades only stable diffs**, assembled question-grouped via the existing combined-diff tooling (`evals/build_combined_diff.py`). Expected volume: tens of pairs, not hundreds.
7. **Go/no-go criterion (updated for the c004 ruling):**
   - **No-go** if `claude-sonnet-5` (the pinned incumbent) drops *any* net correct answers versus its post-ruling baseline (**46/50**), on stable flips — the whole point is helping the cheap models without degrading the one that already works.
   - **No-go** if the groundedness-check spike described in §3's row for 1c appears on more than 1–2 questions across all arms (a citation not backed by the provided context) — that would mean the multiplayer-default bullet is doing real damage to the core honesty guarantee.
   - **Go** if at least 3 of the 5 non-incumbent arms show a net increase in correct-count of ≥1, **and** at least half of the specific predicted flips in §1/§2 land as predicted (e.g. c002 flips on ≥2 of the 3 predicted arms, c016 flips on `deepseek-v4-flash`).
   - **Conditional go** if correct-counts are flat but the diffs show the qualitative wins predicted in §1f (q026-style answers becoming the norm) and §1c/§1d (honest scoping/assumption-flagging replacing silent partials) — worth adopting for answer quality even without a correct-count bump, but flag this explicitly to Jon rather than silently calling it a win on the numbers alone.

---

## 5. Considered and rejected

- **Full system-prompt rewrite instead of surgical bullets.** Rejected: the current prompt already earns 45/50 on the incumbent; a full rewrite risks losing whatever's implicitly working in the existing wording, costs far more tokens to review and re-tune, and gives no way to attribute a regression to a specific change. Surgical bullets keep the working baseline intact and make each change independently reviewable and revertible.
- **Hardcoding specific CR rule numbers (507.1, 802.2) into the system prompt.** Rejected: overfits to this eval's specific gold set, does nothing if those chunks aren't retrieved in the first place (a retrieval-side gap, out of scope here), and is brittle across CR renumbering. The generic "don't assume two players" framing (§1c/§2b) generalizes; naming rule numbers doesn't.
- **Adding a scratch/reasoning field to the schema so the model can "think before answering."** Rejected outright by the hard constraint (schema must not change shape), but also rejected on the merits: cheap models already barely hold the current structured output together (gemini needed retries per the task brief), and a bigger schema surface is exactly the wrong direction for that constraint.
- **A dedicated clarify-question mechanism** (several notes — q004, q016, c004 — gesture at "maybe we should ask a clarifying question"). Rejected for this pass: no schema field exists for it, adding one violates the shape constraint, and F5's own framing calls this "a bridge to a future clarify-question feature" — i.e., explicitly a separate, later piece of work, not something to improvise into the text field now.
- **Fixing multiplayer/ruling-recall gaps (c011, c015, q014-partial) by touching retrieval** (raising `TOP_K`, adding a union-retrieval pass). Rejected: retrieval code is explicitly out of scope for this plan (a separate, already-measured code slice per the task brief); the prompt-side fixes here (§1c, §2b) are the honest ceiling of what prompt tuning alone can do about F4.
- **Per-arm (per-model) custom system prompts.** Rejected: the entire point of this eval design is "identical retrieval and byte-identical prompts, so cross-arm differences are pure generation" — per-arm prompts would destroy that methodology and roughly double the maintenance and review surface for every future prompt change.
- **Raising `REWRITE_N` from 1 to 2+ to add a dedicated multiplayer-angle rewrite.** Rejected for this pass: changes fusion depth, latency, and cost (a second LLM call plus RRF fusion) — a materially bigger lever than a wording change to the single rewrite, and conflates two different levers in one A/B. §2b gets the multiplayer phrasing into the existing single rewrite instead; revisit `REWRITE_N` separately if §2b proves insufficient.
- **Bundling §2c (oracle-text pass-through) into the same `"v2"` rewriter bump as §2a/§2b.** Rejected: §2c is a structurally different change (new code path, new cache-key shape, a new failure mode) and deserves its own version and its own A/B numbers rather than having its effect (and any regression) conflated with two one-line wording edits.

---

## 6. Predicted outcome table (per arm, honestly hedged)

**Baselines updated 2026-07-22 for the c004 ruling** (sonnet 45→46, v4-pro 43→44; the c004 flips previously predicted for §1d are off the board — already correct).

| Arm | v2 baseline | Predicted v3 correct-count | Rationale |
|---|---:|---|---|
| `claude-sonnet-5` (incumbent) | 46/50 | Flat | Already strong; none of the graded sonnet failures match F1/F2/F7 cleanly, and its best-case §1d flip (c004) was granted by the ruling instead. Upside is disclosure quality, not count. Main watch item is the 1c risk (§3) — a regression here would be the go/no-go trigger, not a quiet tradeoff. |
| `deepseek-v3.2` | 43/50 | +1 to +3 | Graded wrong/partial on exactly the failure modes targeted: c002 (F1), c014 (F2, though partial→correct is more likely than wrong→correct given how substantive the miscalculation was), c004 (F5, lower confidence — the miss reads as a reasoning error, not just an undisclosed assumption; still live for this arm, whose c004 stayed wrong under the ruling). q008 (F3) is the least certain — moderate confidence at best. |
| `deepseek-v4-pro` | 44/50 | +1 | q014 (F4) is graded partial with a note that matches §1c almost word-for-word — one of the most confident flips remaining. Its c004 was granted by the ruling, so §1d upside here is disclosure quality only. |
| `deepseek-v4-flash` | 42/50 | +1 to +2 | c002 (F1, high confidence) and c016 (F7, high confidence — Jon's note names the exact fix) are both textbook matches. q026's clarity note (F6) should also visibly improve even though it was already correct. |
| `gpt-5-mini` | 42/50 | 0 to +1 | Least headroom — this arm is already Jon's exemplar for handling dual readings well (q026) and for honest low-confidence framing elsewhere. c014 (F2, partial) is the one plausible flip. |
| `gemini-flash-lite` | 38/50 | +1 to +3, least certain of any arm | Most failure modes present (c002/F1, c014/F2) but also the weakest at holding multi-instruction prompts together — the ~20% token increase (§1's token table) is a real regression risk specifically for this arm, independent of whether any individual bullet is "correct." Net direction is positive but the variance on this arm is the highest in the table. |

If §2c (oracle-text pass-through) is adopted and tested as its own arm-variant: expect no correct-count movement on the 31 rules-only questions (unaffected by construction) and a speculative, unconfirmed lift on card-interaction questions generally (c002/F1, c014/F2 as a second grounding layer) — but explicitly **not** on c012, which has a different root cause (§7).

---

## 7. c012 diagnostic note (code-slice, not prompt-addressable)

Per the coordinator's follow-up: c012's question correctly brackets all three referenced cards (`[Emrakul, the Promised End]`, `[Lithoform Engine]`, `[Voltaic Key]`) — ref-detection is not the failure. Jon's grading note is specific: Lithoform Engine's oracle text was missing from what the generator saw.

Tracing the current code (`src/rulesagent/generate/answer.py`):
- `parse_card_refs` (line 295) extracts all bracketed tokens via `CARD_TOKEN_RE.findall`, which has no cap.
- The dedup loop (lines 301–308) is a simple case-insensitive first-occurrence dedup over `all_refs` — for c012 this correctly collapses the repeated `[Emrakul, the Promised End]` token down to one entry while leaving Lithoform Engine and Voltaic Key untouched. No cap, no drop.
- `cards = [c for ref in all_refs if (c := get_card(ref, ...)) is not None]` (line 309) resolves every ref independently — no slicing, no first-N cap.
- `_format_cards()` (lines 174–209) iterates `for c in cards` with no truncation and calls `_face_block(f)` per card, which renders `f.oracle_text` whenever it's non-empty.

**Finding: no cap or first-card-only path exists in the current multi-card prompt-assembly code.** The "secondary cards get dropped" hypothesis does not reproduce by reading `build_prompt`/`_format_cards`/the ref-resolution loop as they exist today. If the symptom is real and current (not an artifact of an older code path this eval transcript predates), the more likely loci are upstream of prompt assembly: `get_card()`'s Scryfall fuzzy-match (`src/rulesagent/tools/scryfall.py`, `get_card`, lines 166+) returning a wrong or empty-text entry for "Lithoform Engine" specifically, or a stale/schema-mismatched cache entry for that one card. Recommend re-running c012 with tracing on `cards` right before `_format_cards()` is called, to see directly whether Lithoform Engine's `Card` object has empty `oracle_text` at that point (an upstream fetch bug) or non-empty text that `_format_cards` is somehow not rendering (which would contradict this reading of the code and need a second look). Either way — this is a code-tracing task for a fresh session with the actual eval transcript in hand, not something this prompt-tuning plan can resolve or fix.
