**DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.**

# Plan — cost / mana-value calculator tool

Written 2026-07-23, after the v5 selective-injection grid confirmed what v4's
full legend already suggested: c014 does not move no matter how the mana
*notation* is delivered. Two prompt programmes have now spent their budget on
this question. This plan proposes stepping outside the prompt entirely.

Grounding read: `DECISIONS.md` (2026-07-25 entries, "prompt v4 is NO-GO" and
the c002/c020 exclusion), `docs/plan-v5-symbol-injection.md` (§1, the
pre-commitment that fired), `docs/report-v5-grid.md` (the run that fired it),
`src/rulesagent/generate/answer.py` (`SYSTEM_V4NL` :413-535, `SYMBOL_DEFS`
:581-649, `build_prompt` :749-822, `RulesAgent.answer` :1009-1253,
`_format_cards` :862-897), `src/rulesagent/tools/scryfall.py`,
`src/rulesagent/tools/ruling_retrieval.py`, `src/rulesagent/contracts.py`
(`Card`, `CardFace`, `Answer`), `evals/cards.jsonl` (c014),
`evals/rulesguru.jsonl`, `data/raw/MagicCompRules 20260619.txt` (CR 118,
202.3, 601.2).

## 1. The problem, evidenced

Two full prompt programmes have now targeted the same miss:

- **v4** (`docs/plan-prompt-v4.md`, reverted 2026-07-25) added a complete
  mana-notation legend to `SYSTEM` — CORE + REFERENCE tier, every symbol from
  `{N}` to `{CHAOS}`, ~+1,215 tokens on every query with no prompt caching on
  either path (`DECISIONS.md` confirms `grep -rn "cache_control\|ephemeral"
  src/` returns nothing). Result on sonnet: 46/50 → 46/50, "zero
  judge-detectable divergence across all 50 questions and both runs"
  (`DECISIONS.md` 2026-07-25). c014 did not move.
- **v5** (`docs/plan-v5-symbol-injection.md`, built and run 2026-07-23)
  replaced the static legend with selective per-symbol injection — only the
  symbols actually present in the cards/question, decomposed into
  `SYMBOL_DEFS` (`answer.py`:581-649) and assembled by
  `_symbol_reference_block` (`answer.py`:707-727). Cell D (the v5 candidate)
  cost +603/+509 tokens over v3 and produced **zero scoring flips on either
  arm** (`docs/report-v5-grid.md`, "Cost beside accuracy" table). Its own
  §"What the table says" is explicit: *"c014 never moved, again... The
  bottleneck is multi-step reasoning about cost modification, not
  notation — and no amount of symbol documentation addresses that."*

`docs/plan-v5-symbol-injection.md` §1 pre-committed to this outcome before
the run: *"If v5 also misses c014, that is confirmatory and the symbol work
is finished either way."* v5 missed it. **That pre-commitment has fired.**

The diagnosis, from `DECISIONS.md`'s 2026-07-25 no-go entry, stated plainly:
v4 *"got the model to state the cost breakdown correctly and still conclude
wrong, which points at multi-step reasoning about cost modification rather
than notation."* The model can already recite what `{1}{G}{G}` decomposes
into. What it cannot reliably do is carry that decomposition through more
than one modification and a comparison across values of `{X}` without
dropping or misapplying a step. That is exact arithmetic with a
rules-defined order of operations — the worst possible task for
token-by-token generation and the best possible task for a function call.

**The concrete case.** `evals/cards.jsonl` c014, in full:

> An opponent controls an untapped [Trinisphere], and I have a permanent that
> makes my green spells cost {1} less. I want to cast [Awaken the Woods] for
> value. If I cast it with X=0, what does it cost and what do I get, and what
> X should I actually choose?

Its own `note` field records the load-bearing fact and — importantly — where
it actually lives: *"Load-bearing: CR cost-calculation order (601.2f,
increases then reductions) + Trinisphere ruling 0 (its floor is applied
LAST, after reductions — overrides the naive rule reading)... Rules-gold BY
ABLATION: EMPTY — the sanity check (remove ALL cited rules) HELD, so the CR
rules are REDUNDANT here."* This is worth sitting with before proposing a
fix: **the ordering that actually decides c014 is not settled by CR text
alone; it comes from a card-specific ruling.** §2 draws the scope line this
forces.

## 2. Scope, drawn tightly

**Computes:**

- Total cost from a base mana cost plus a list of cost-modifying effects
  (reductions, increases, and cost floors/minimums), each supplied with an
  explicit kind and amount — per CR 601.2f (quoted in full below).
- Mana value of a mana cost string, including `{X}` (0 off the stack, its
  chosen value on the stack), hybrid symbols (largest-component rule), and
  Phyrexian symbols (contributes 1) — per CR 202.3, 202.3e-g (quoted below).
- The above evaluated across a supplied range of `{X}` values, so a
  "what X should I choose" question (exactly c014's shape) gets an exact
  table instead of the model doing that comparison in its head.
- Basic bookkeeping the CR text makes explicit: a reduction can lower the
  generic component to `{0}` and no further (601.2f: *"It can't be reduced
  to less than {0}"*); colored and `{C}` symbols are untouched by a
  cost-reduction effect that reduces "the mana cost" or "the generic mana"
  (this is the v3/v4 mana-symbol bullet's own claim, already in `SYSTEM` —
  the calculator doesn't introduce this rule, it just applies it exactly
  instead of in prose).

**Refuses to compute — explicitly, not silently:**

- **Which effects apply, and what kind they are.** This is the load-bearing
  scope decision, forced directly by the c014 finding above: the tool never
  reads oracle text, rulings, or CR chunks and never decides for itself that
  "Trinisphere's ability is a floor, applied after reductions." That
  identification is exactly the judgment call the rules-RAG pipeline exists
  to make, and c014's own gold-by-ablation note shows it can turn on a
  single card's ruling rather than a general rule. The tool receives the
  *already-classified* modifier list as a plain argument. If the model
  misclassifies a modifier, the tool will compute an internally consistent
  and confidently wrong number — see §5.
- **Non-mana costs.** Life payments, sacrifices, discards, tapping, and any
  other cost component under CR 118.3 (`data/raw/MagicCompRules
  20260619.txt`:972-976) are out of scope for v1. The tool only touches the
  mana component of a cost.
- **Alternative costs and the announcement-order rules in CR 601.2b**
  (`data/raw/MagicCompRules 20260619.txt`:2459 — hybrid/Phyrexian payment
  choice, buyback/kicker, `{X}` announcement). The tool computes a total
  once a base cost and modifier list are given to it; it does not decide
  which alternative cost was chosen or resolve payment-choice announcements.
- **Anything without a numeric mana cost to start from** (an ability with no
  mana component, a cost expressed only as an action). Returns a structured
  refusal (§5), never a guessed number.
- **Un-set/silver-border symbols** (half-mana, infinity) — consistent with
  the existing project behavior: `_classify_symbol` (`answer.py`:662-666)
  already documents these as "not a symbol this dict defines... silently
  dropped, never guessed at," and `docs/plan-v5-symbol-injection.md` §8
  records this as "Jon's Un-set ruling."

A tool that silently guesses on an input it can't model is worse than prose
that hedges. The refuse-list above is deliberately longer than the
compute-list.

## 3. The interface

### 3a. What's actually in the codebase today — and what it isn't

`src/rulesagent/tools/` currently holds two modules —
`scryfall.py` (`get_card`, `parse_card_refs`) and `ruling_retrieval.py`
(`select_rulings`, `select_rulings_union`) — but neither is a *model-facing*
tool. Both are plain Python functions the orchestrator (`RulesAgent.answer()`,
`answer.py`:1009) calls **before** the LLM is invoked, to assemble the prompt.
Nothing in this codebase currently declares an Anthropic `tools=[...]`
parameter or runs a tool-use round trip. The single generation call is:

```
answer.py:1189-1195
response = self.client.messages.parse(
    model=self.model,
    max_tokens=16384,
    system=system,
    messages=msgs,
    output_format=Answer,
)
```

`.messages.parse(..., output_format=Answer)` is the SDK's structured-output
convenience wrapper — one call in, one parsed `Answer` out. `msgs` is built
once at `answer.py`:1184 (`[{"role": "user", "content": user}]`) and never
grows. So "the calculator" the task asks for is not a same-shaped extension
of `tools/` as it exists today — it would be the **first real agentic
tool-use integration in this codebase**, and needs its own seam, not a third
file dropped into `tools/` and called the way `get_card` is.

### 3b. Proposed seam — a genuine tool-use round trip

1. Declare one Anthropic tool, `calculate_cost`, roughly:

   ```
   {
     "name": "calculate_cost",
     "description": "Given a spell or ability's base mana cost and a list of
       cost-modifying effects you have already identified from the rules and
       card text (each labeled reduction, increase, or floor_total, with an
       amount and a short cite), computes the exact resulting cost per CR
       601.2f -- optionally across a range of {X} values. This tool does NOT
       decide which effects apply or what kind they are -- identify that
       from the provided rules/card data first, then call this only for the
       arithmetic. Never state a combined or compared cost without calling
       this tool when more than one cost-modifying effect is in play.",
     "input_schema": {
       "base_cost": {"generic": int, "colored": {"W":int,"U":int,"B":int,
                      "R":int,"G":int,"C":int}, "x_coefficient": int},
       "x_values": [int, ...] | null,
       "modifiers": [
         {"kind": "reduction"|"increase"|"floor_total", "amount": int,
          "cite": str}
       ]
     }
   }
   ```

   Output: per requested `x` (or a single result when `x_values` is null),
   the resulting cost broken out by symbol, the resulting mana value, and a
   plain-text `steps` trace (one line per modifier applied, in order) — the
   trace exists so the model's prose can *cite* the tool's own reasoning
   instead of re-deriving it, and so a reviewer can see the arithmetic that
   produced a given answer without re-running it.

2. Insert a round trip around the existing call. `msgs` (`answer.py`:1184)
   grows: call with `tools=[calculate_cost]`; if `stop_reason == "tool_use"`,
   execute the (pure, deterministic, no I/O) function locally, append the
   `tool_use` block and a `tool_result` message, and call again — capped at
   a small fixed number of rounds (2, matching the existing empty-draw retry
   budget at `answer.py`:1187) so a confused model can't loop. The final
   call in the chain is the one that must yield the structured `Answer` —
   whether that's the same `.messages.parse(output_format=Answer)` call with
   `tools` also attached, or a last call that drops `tools` and adds
   `output_format`, is **not settled here** — flagged as an open item below.

3. Tell the model when to reach for it. `build_prompt` (`answer.py`:749)
   already has a working precedent for "when": the symbol-injection seam at
   `answer.py`:792-796 conditionally appends a block only when relevant
   symbols are present. The calculator's trigger is a `SYSTEM` instruction,
   not conditional injection — something like: *"When a question requires
   combining more than one cost-changing effect, or comparing a cost across
   different values of {X}, call `calculate_cost` with the modifiers you've
   identified rather than doing that arithmetic yourself."* This sits
   alongside the existing "Cost math" bullet (`SYSTEM_V4`/`SYSTEM_V4NL`,
   `answer.py`:267-281 / :444-458) rather than replacing it — the prose
   bullet still tells the model the *rule*; the new sentence tells it to
   *delegate the computation*.

### 3c. Why this is presented as one integrated design, not two options

An earlier draft of this plan considered a lighter alternative — precompute
the total cost in Python and inject it into the prompt the way
`_symbol_reference_block` injects definitions, no tool-use round trip at
all. That doesn't work for c014-shaped questions: precomputation requires
already knowing the modifier list and its classification, which is the part
this plan just scoped *out* of the tool (§2) because it's a rules-judgment
call, not a data-availability gap. The one case that genuinely is fully
determined without any model judgment — a card's own mana value, with no
modifiers in play — is **already given to the model today**, directly:
`_format_cards` (`answer.py`:862-897) emits `MV {c.mana_value:g}` on every
card's header line (`answer.py`:873), sourced from Scryfall's `cmc` field
(`tools/scryfall.py`:159, `Card.mana_value`). There is no gap to close
there. The actual gap — combining modifiers and comparing across `{X}` — can
only be closed by giving the model something to call *after* it has done
the identification, which means real tool-use. §3b is the only design
considered further.

### 3d. What's explicitly not solved here (open items)

- ~~Whether `.messages.parse(..., output_format=Answer)` supports `tools=`~~
  **RESOLVED by spike 2026-07-23 (`docs/spike-tool-use-findings.md`, commit
  `7a7e94b`).** No conflict: `messages.parse(tools=..., output_format=Answer)`
  is a legal call. `output_format` constrains only whichever turn *ends* the
  conversation; on a turn where the model calls a tool, `stop_reason` is
  `tool_use` and `parsed_output` is `None`. **The integration is simpler than
  this plan assumed** — there is NO "final tools-off call" branch to build.
  Reissue the *same* `parse(tools=..., output_format=Answer)` call each loop
  round; it returns a populated `Answer` automatically once the model stops
  calling tools. Verified end-to-end for single and chained tool calls on
  `claude-sonnet-5`. Round trips = tool calls + 1. Keep a round cap as a guard.
- How the tool round trip nests inside the existing empty/degenerate-draw
  retry loop (`answer.py`:1187-1214), which currently assumes a single call
  per attempt.
- `evals/run_openrouter_arm.py` / `openrouter_backend.py` (gpt-5-mini and
  the other A/B arms) use OpenRouter's `response_format` strict-schema path
  (`openrouter_backend.py`:46-64) with **no tool-use support today**. If
  Jon wants the gpt-5-mini arm measured too, that's a second, structurally
  similar integration on a different backend — out of scope for v1 (§7).

## 4. Where the inputs come from

- **Base cost, per-face**: already fetched. `tools/scryfall.py`'s
  `_card_from_json` builds one `CardFace` per printed face with its own
  `mana_cost` (`scryfall.py`:108-122, `_face_from_json`) — this is the exact
  fix already shipped for the *other* c014-adjacent bug: `DECISIONS.md`
  records the pre-enrichment baseline miss where "the model guessed Awaken
  the Woods = `{X}{G}{G}{G}`... because the cost was never in the prompt,"
  fixed by enrichment carrying the real per-face cost. The calculator's
  `base_cost` argument is a parse of a string the pipeline already puts in
  front of the model on every card question.
- **Mana value**: already computed and already shown to the model (`MV
  {c.mana_value:g}`, `answer.py`:873, sourced from Scryfall's `cmc`,
  `scryfall.py`:159) — no new fetch needed even for the mana-value half of
  this tool.
- **`{X}` coefficient**: derived from the same cost string, not a new data
  source.
- **Modifiers (reductions/increases/floors) and their kind**: this is the
  one input the pipeline does *not* hand over as structured data today, and
  per §2 it never will — it lives in prose (another card's oracle text, a
  retrieved CR chunk, a card ruling) that the model has already read by the
  time it would call the tool. The model supplies it as the `modifiers`
  argument, sourced from context that's already in the prompt. **No new
  data pipeline is required** — the tool changes how the model *uses*
  information already assembled, not what information is assembled.
- **User-stated hypotheticals not attached to any `[bracket]` card** — c014
  itself is this case ("a permanent that makes my green spells cost {1}
  less" names no real card). The pipeline handles this today exactly as it
  handles any unstructured fact in the question: the model reads it from
  the question text. The tool doesn't change that either; DECISIONS.md
  already confirms the model correctly extracts this fact in prose today
  ("got the model to state the cost breakdown correctly") — the gap is
  purely downstream of extraction.

## 5. The honest failure mode

A calculator that's wrong is worse than prose that's wrong, because a
computed number carries an authority prose doesn't — a reader (or a judge,
or Jon) is far less likely to double-check "the tool said 3" than "I think
it's probably 3." Four concrete ways this bites, and the guard against each:

1. **Modifier misclassification** — the Trinisphere shape exactly. The
   model calls the tool with a `floor_total` mislabeled as a `reduction`
   (or vice versa) and gets a confidently wrong, internally consistent
   number. **Guard:** the tool's `steps` trace must be surfaced in the
   answer's citations/reasoning, not just its final number, so a
   misclassification is visible in the trace rather than laundered into an
   unexplained total. This does not prevent the error; it makes it
   auditable, which is the same posture the rest of the pipeline already
   takes (§5.4).
2. **Bad base-cost input** — wrong face, mistyped symbol count, an X
   coefficient read as 2 when the cost has one `{X}`. **Guard:** the tool
   validates its own input syntactically (a malformed cost string is a
   structured error, not a best-effort parse) but cannot validate that the
   cost matches the actual card — that check belongs to a regression test
   comparing tool calls against `Card.mana_cost` at eval time, not to the
   tool itself.
3. **Prose drifts from the tool's own output** — the model calls the tool,
   gets a correct number back, and then writes a different number in
   `Answer.text` anyway (a known LLM failure mode independent of this
   project). **Guard:** add an eval-time check — not a runtime one — that
   the numeric total stated in `Answer.text` matches the last
   `calculate_cost` result for that turn, flagged the same way
   `_degenerate()` (`answer.py`:825-837) and the uncited-success guard
   (`answer.py`:1233-1244) flag other draw shapes today, i.e. logged and
   surfaced in telemetry, never silently retried.
4. **Silent tool calls** — today, `RulesAgent` exposes `last_rewritten`,
   `last_ruling_selection`, `last_crossref`, `last_cards`,
   `last_unresolved_refs` (`answer.py`:951-1007) so every non-obvious
   pipeline decision is auditable after the fact. A `last_tool_calls: list
   | None` field, recording every `calculate_cost` invocation and result on
   the call, should follow the same pattern — so "did it use the
   calculator, and what did it compute" is answerable from telemetry
   without re-running the question.
5. **Malformed/unpayable input** (negative amount, absurd `{X}` range) —
   must fail loud: a structured tool error the model is instructed to
   surface as `answered: false` with what's missing, mirroring how
   `get_card` returns `None` on a 404 rather than raising
   (`scryfall.py`:166-181) and how unresolved card refs are recorded rather
   than silently dropped (`answer.py`:1038-1063). Never compute a
   best-effort number from bad input.

## 6. Verification — c014 is one question, not a test set

Say this plainly, because it would be easy to skip: **c014 flipping (or not)
after this ships proves nothing on its own.** n=1 against a stable-flip
discipline that already required 2 agreeing runs for a *prompt* change
(`docs/plan-v5-symbol-injection.md` §3) is not a basis for a go/no-go on a
structural change this much bigger. A test set needs building.

**`evals/rulesguru.jsonl`, checked directly (150 rows total):**

- `gold` (human-written gold rule ids) is non-empty on **134 of 150** rows —
  confirms the task's premise.
- Filtering to rows whose `tags` contains `Costs`, `Alternative Costs`, or
  `Additional Costs`: **22 rows**, of which **18 carry non-empty gold**
  (the other 4 — `rg6328`, `rg1344`, `rg3452`, `rg4028` — have empty gold and
  would need Jon's own gold-writing before use, same as any other
  ungoldeded rulesguru row).
- Narrowing further to rows that *also* carry `Mana`, `Numbers and symbols`,
  or `Mana value` — the closest analog to c014's shape, cost arithmetic
  specifically involving mana notation rather than e.g. a life-payment or
  sacrifice cost: **8 rows** (`rg3509`, `rg2242`, `rg5006`, `rg3518`,
  `rg1652`, `rg202`, `rg204`, `rg659`). All 8 carry non-empty gold.

That gives two candidate test sets: a broader 18-row cost set and a
narrower 8-row mana-cost-math set. **Recommend starting with the 8-row set**
as the closer analog to what this feature targets, with the 18-row set as a
secondary check that the tool doesn't regress cost questions that don't
involve mana notation (life payments read from `gold`'s CR citations would
show up there) — flagging plainly that 8 is a small sample and this is
Jon's call, not a settled recommendation.

**Beyond rulesguru**, the existing card-eval questions with a mana-math
component (`evals/cards.jsonl` c002/c004/c011/c012/c014/c015 — the same six
`docs/plan-v5-symbol-injection.md` §2 already scoped for symbol injection)
give a paired, already-graded baseline: run tool-on vs tool-off, same
2-run stable-flip discipline the v4/v5 A/Bs already used, frozen judge
routing verdicts Jon has already given wherever they transfer cleanly
(`docs/report-v5-grid.md`'s own pattern). **Cost must sit beside accuracy in
that report**, per the same standard `docs/plan-v5-symbol-injection.md`
§5a's cost table and `docs/report-v5-grid.md`'s "cost beside accuracy"
table already set — a tool round trip is not free: it's an extra model
call (extra system+context tokens sent again on the follow-up turn, plus
the tool schema itself in every call's request), and that number needs
measuring, not assuming away.

## 7. Non-goals

- No multi-tool agentic loop — one tool (`calculate_cost`), one narrow job.
- No support for non-mana cost components (life, sacrifice, discard,
  tapping) in v1 — CR 118.3 territory, explicitly out of scope (§2).
- No change to the frozen judge, and no rewriting or retiring of any
  existing eval question or verdict.
- No OpenRouter/gpt-5-mini tool-use support in v1 (§3d) — the Anthropic
  production path only, unless a v1 result makes the case for extending it.
- No claim, anywhere in this plan or its implementation, of a rule this
  plan didn't find and quote from the repo's own CR text or from an eval
  question's already-recorded note. Where a rule wasn't found (a general CR
  mechanism for card-specific cost floors, distinct from Trinisphere's own
  ruling — see §1's closing paragraph and the `grep` for "costs at least" /
  "can't be reduced" / "floor" across the CR text, which returned nothing
  beyond 601.2f's own `{0}` floor), this plan says so rather than asserting
  a rule number that wasn't verified.

## 8. What would change Jon's mind

- **Base-rate evidence that this class of question is rare.** If the
  cost-tagged rulesguru slice (§6) and real traffic both show genuinely
  multi-modifier, compare-across-`{X}` questions are uncommon, the added
  round-trip latency/token cost on every query that trips the trigger bullet
  (§3b.3) may not be worth it for a handful of questions a year — the same
  ROI question the v4/v5 token-cost tables were built to make visible.
- **Evidence the bottleneck was misdiagnosed.** If the tool ships and c014
  (and the 8-row mana-cost-math set) *still* miss because the model keeps
  misclassifying modifiers going into the tool call rather than mishandling
  the arithmetic once inside it, that would show the actual bottleneck is
  rules-judgment (which effect is which), not arithmetic — closing this
  line of work the same way v4 and v5 closed the notation-delivery
  question, and pointing instead at retrieval/rulings quality for
  card-specific floors like Trinisphere's.

## 9. Demo/articulation note

The strongest thing to say about this feature isn't "I built a calculator" —
it's that two prompt programmes independently confirmed the same failure
before anything was built: the model could correctly *state* a cost
breakdown in prose and still land on the wrong number, which is a tell that
the bottleneck is arithmetic reasoning, not missing knowledge, so the fix is
to stop asking a language model to do algebra token-by-token and give it a
function instead. Being able to point at the two failed attempts — the full
legend, then selective injection — and the specific sentence in
`DECISIONS.md` that diagnosed why, is a stronger interview answer than a
working demo alone, because it shows the diagnosis came before the fix.

## 10. Open items (compiled from above)

1. ~~`.messages.parse()` + `tools=` compatibility~~ **RESOLVED** — no conflict,
   one reusable looped call shape, no tools-off branch needed (§3d, spike
   `7a7e94b`). gpt-5-mini via OpenRouter also verified viable, same 2-round
   shape — which also softens open item #3 below from "unknown" to "viable,
   mechanics not yet designed".
2. Tool-round-trip nesting inside the existing empty/degenerate-draw retry
   loop at `answer.py`:1187-1214 — not designed here (§3d).
3. OpenRouter/gpt-5-mini tool-use support — deferred, not designed (§3d, §7).
4. Whether the validation set is the 8-row or 18-row rulesguru slice — a
   call for Jon, not settled (§6).
5. A general CR mechanism for card-specific cost floors distinct from
   Trinisphere's own ruling was searched for and not found in the repo's CR
   text — flagged, not asserted either way (§1, §7).
