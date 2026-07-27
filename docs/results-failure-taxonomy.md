# Results: Failure Taxonomy (what kind of question does Rulemancer get wrong)

**Cost: $0.** No API calls, no model calls, no eval runs. Pure analysis of verdict/answer files already on disk, done with `jq`/Python against the files in place — nothing large was loaded into the analyst's context.

The project has measured *how much* Rulemancer gets right for months (accuracy, CIs, judge error rate, gold audits). It has never asked *what kind* of question breaks it. This is that first pass, meant as input to "what should we actually fix," not a new accuracy headline.

## Method

### Step 1 — evidence selection

`evals/_metrics_history.json` (built 2026-07-26, the project's own accuracy dashboard) records a `current_config` block (`GEN_MODEL: claude-opus-5`, `GEN_EFFORT: low`, system version 3, current retrieval settings) and a `summary.facts` block whose headline accuracy (82.8%, N=311) is built from exactly three `kind: "pipeline"` arms that match that config on model, effort, and system version, and whose question counts sum to that N:

| Arm | File | n | judge model | judge digest |
|---|---|---:|---|---|
| `l0_opuslow` | `evals/verdicts_l0_opuslow.json` | 207 | openai/gpt-5-mini | b54fbdb95565abf8 |
| `h2h_opuslow_easy_r1` | `evals/verdicts_h2h_opuslow_easy_r1.json` | 50 | openai/gpt-5-mini | b54fbdb95565abf8 |
| `h2h_opuslow_hard_r1` | `evals/verdicts_h2h_opuslow_hard_r1.json` | 54 | openai/gpt-5-mini | b54fbdb95565abf8 |

207 + 50 + 54 = 311, matching `summary.facts.n_run` exactly. This is the same slice the dashboard uses for the current headline accuracy number, so it is the best available representation of "what does the shipped config actually get wrong."

**Two other arms share the exact same underlying answers** (`h2h_opuslow_easy_r2`, `h2h_opuslow_hard_r2` — second judging passes over the identical 50/54 generated answers) and were **excluded from the counted totals** to avoid double-counting rows, but used below to quantify judge noise (see Caveats).

**`opus5_low_bucketA` / `opus5_low_bucketA_human` / `ab_pilot_LX_on` / `ab_pilot_LX_off`** (n=68, same qset `c78c738d`) were excluded — they are a separate layers-crossref ablation slice, not part of the dashboard's counted current-config sample, and including them would double an already-distinct question set.

Excluded up front, per the dashboard's own warning that 5 verdict files record no judge model at all: `rulesguru_sonnet`, `rulesguru_gpt-5-mini`, `ab_pilot_R`/`ab_pilot_K`/`ab_pilot_Z` and `h2h_gpt5mini` all show `judge_model: null` or `model: null` in the metrics history and were not touched. Also excluded as off-target for "current production": `derivability_*` and `norules_control*` (oracle arms — retrieval deliberately removed, measuring something else), and `layers_slice0_*` (a different generation model, claude-sonnet-5).

Every failed row was joined back to `evals/rulesguru_full_v2.jsonl` (1,409 rows) on `id` for `gold`, `level`, `cards`, `tags`, `complexity`, and `question`. Join coverage was 311/311 (no misses).

### Step 2/3 — category rates vs base rate

N = 311, failures = 23, **overall (base) failure rate = 7.4%**.

A category is called out below only if failure rate ≥ 1.5× base rate **and** n ≥ 10.

| Category | n | fails | rate | × base rate |
|---|---:|---:|---:|---:|
| Difficulty **level 3** | 14 | 6 | 42.9% | 5.80× |
| Complexity **"Intermediate"** (RulesGuru's own label) | 18 | 6 | 33.3% | 4.51× |
| Difficulty **Corner Case** | 3 | 1 | 33.3% | 4.51× — **n<10, do not trust** |
| Tag **Layers** | 49 | 10 | 20.4% | 2.76× |
| Tag **Type-changing effects** | 34 | 8 | 23.5% | 3.18× |
| Tag **Dependency** | 15 | 4 | 26.7% | 3.61× |
| Tag **State-based actions** | 11 | 3 | 27.3% | 3.69× |
| Tag **Lands** | 20 | 4 | 20.0% | 2.70× |
| Difficulty **level 2** | 49 | 6 | 12.2% | 1.66× — below the 1.5×/n≥10 bar only marginally; listed for context |
| 4+ cards in the question | 31 | 4 | 12.9% | 1.74× — n just over 10, weak signal, direction plausible (more cards, more interaction surface) but small |

Categories tested that came back **flat or below base rate** (not interesting): number of cards involved (2 vs 3 cards: 6.6% vs 8.9%, no real gradient), `empty_gold` questions (4.2%, actually *lower* than base — meaning RulesGuru's "no single cite" questions are not where the bot struggles), question length (long questions 300+ chars: n=7, too small to read), match_mode (all rows use `"any"`, no variance), and no multi-face/split cards appear anywhere in this 311-row sample (`//` name check returned zero), so that axis is untestable here.

### Confound to flag before trusting the tag table

**The three tag/level findings above are largely the same finding wearing different labels.** `h2h_opuslow_hard_r1` (the "hard" arm) was deliberately curated as a layers/type-changing stress test: 49 of its 54 questions carry the `Layers` tag, and **zero** `Layers`-tagged questions exist anywhere in the other two arms (`l0_opuslow`, `h2h_opuslow_easy_r1`). So "Layers questions fail 2.76× base rate" cannot be separated from "the hard arm fails a lot and the hard arm is entirely about layers" — this is a stratified sample, not a random one, and the tag correlation is confounded with arm selection by design. Same logic for `Type-changing effects`, `Dependency`, `State-based actions`, `Lands` — they cluster in the hard arm because RulesGuru's own tag scheme calls layer-interaction questions that.

What *is* independently informative, because it isn't confined to one arm: **`level`** and RulesGuru's own **`complexity`** field, which both appear across all three arms and both show a clean, monotonic gradient (level 0: 2.9% → level 1: 10.5% → level 2: 12.2% → level 3: 42.9%; Simple: 5.8% → Intermediate: 33.3%). Within the hard arm alone, card count (2 vs 3 vs 4+) does not add much further gradient beyond the arm's already-elevated baseline (25% / 22% / 40%, the last on n=5).

**Bottom line on signal:** the honest claim is "difficulty level and RulesGuru's own complexity label predict failure cleanly, and the content that RulesGuru's authors classify as high-difficulty is disproportionately layer-application and type-changing-effect questions" — not an independently-discovered "layers is a weak spot" finding, though it likely amounts to the same practical conclusion.

## Step 4 — how it actually fails (qualitative, 10 examples)

Reading the actual failed answers (not just the judge's one-line verdict) surfaces a few distinct failure modes:

1. **Wrong layer/timestamp application (the single biggest bucket).** `rg633`: candidate says Badlands taps for white because Magus of the Moon and Conversion "cancel out"; correct answer is that both are layer-4 type-changing effects applied in timestamp order, making it a Mountain that taps for red. `rg130`/`rg131` (same underlying interaction, two prompts): candidate concludes Sapseep Forest becomes a plain, noncreature Mountain; the reference says both permanents remain 1/1 green Saproling Mountain land creatures — the candidate dropped a characteristic instead of stacking the two type-changing effects correctly.

2. **State-based-action / "loses abilities" confusion on Sagas and merged permanents.** `rg4023` (and its near-duplicate `rg6634`): candidate concludes Urza's Saga is sacrificed once it loses its land-typing chapter abilities; correct ruling is it stays on the battlefield with its lore counters, just without the chapter triggers — the model over-applies "loses abilities" into "gets sacrificed." `rg1900`: candidate keeps Trumpeting Gnarr's abilities (and fires its mutate trigger) on a merged permanent that the reference says comes out as a blank face-down 2/2.

3. **Trigger-ordering / timing misses.** `rg1049`: candidate concludes a creature dies from a delayed trigger that, per the reference, isn't even created until the enabling ability finishes resolving — a "when does this trigger get created" timing miss, not a layers issue. `rg1802`: candidate assumes a soulbond trigger will exist to be ordered, missing that soulbond doesn't trigger at all if no eligible partner exists at the time. `rg6456`: candidate concludes a sacrifice can't happen; reference shows the controller can choose trigger order to make it legal — an "assumed no agency over ordering" miss, the mirror image of `rg1802`.

4. **Restriction-scope errors.** `rg6743`: candidate allows a loyalty ability activation that Teferi, Time Raveler should prevent, because the answer conflated "can't cast spells" with "can't activate abilities" — misreading what the restriction actually covers.

5. **Declined to answer.** `rg6547`: the model refused to rule at all ("this isn't a Magic: The Gathering rules question... nothing in the provided rules context covers Deadpool or Spider-Man"), when the reference expected a ruling (a tie, both creatures dying) treating the flavor names as placeholders for the actual permanents in play. This is a distinct failure mode from a wrong ruling — it's an over-cautious refusal that the judge scored as different from a correct, confident answer.

6. **Layer-stacking omissions on multi-effect enchant/aura chains.** `rg1756`: candidate says the permanent ends up green and ability-less; reference says one effect gets removed from the layer stack (a source leaving play) so the permanent regains its original abilities and color — a "forgot to re-evaluate the layer stack after a source left" miss, structurally the same class as #1 but one step more complex (interaction with an object leaving the battlefield mid-analysis rather than static overlap).

None of the 8-10 read here look like judge unfairness — in each case the quoted reference reasoning is more rule-literal and traceable to a specific CR cite than the candidate's, not just "different phrasing."

## What this suggests fixing (separated from the measurements above — this is judgment, not data)

- The clean level/complexity gradient (2.9% → 42.9%) says the pipeline is already fine on lookup-shaped questions and specifically weak on **multi-step continuous-effect stacking**: layers, timestamp ordering, and "does this object still have ability X after a type-changing chain" questions. That's a coherent, fixable content gap, not scattered noise.
- The state-based-action-after-type-change pattern (`rg4023`/`rg6634`, "loses abilities implies gets sacrificed") looks like a specific, nameable misconception worth a targeted rules excerpt or few-shot correction rather than a general accuracy push — it recurs identically across near-duplicate questions.
- The refusal case (`rg6547`) suggests a prompt-level issue distinct from rules competence: the model treats flavor-text character names as a signal to disengage rather than mapping them onto the game objects described in context. Worth checking how common this is beyond n=1 before investing in a fix.
- Because the tag-level findings are confounded with the hard arm's deliberate curation (see above), the next useful measurement is a **layers-tagged sample drawn from the full corpus at every difficulty level**, not just the pre-selected hard slice — that would separate "layers is intrinsically hard" from "the hard arm is intrinsically about layers."

## Caveats (read before trusting any number above)

- **Judge noise is comparable in size to several of the category signals.** Re-judging the identical 50 easy-arm answers a second time (`h2h_opuslow_easy_r2`, same judge model and prompt digest) flipped the verdict on 5 of 50 rows (10%); re-judging the identical 54 hard-arm answers flipped 4 of 54 (7.4%). A category effect smaller than roughly 1 in 10 rows could be judge inconsistency rather than a real content pattern. None of the 23 failures counted here are themselves flagged in the dashboard's `judge_error_results.json` false-positive audit, but that audit only sampled 90 of 1,409 rows overall, so it does not specifically clear this slice.
- **This is 311 of 1,409 corpus questions (22%)**, and the sample composition is not uniform-random — it is three separately-curated arms (a general level-0 slice, an "easy" slice, and a deliberately hard/layers-heavy slice). The failure taxonomy describes what fails *within this sample*, weighted by how the arms happen to be built, not a random cross-section of the full corpus.
- **The tag-vs-arm confound (spelled out above) is real and not fully resolvable with the data on disk.** Anyone quoting "Layers questions fail 2.76x" without the caveat that 100% of Layers questions in this sample come from one deliberately-hard arm is overstating an independent finding.
- Read count on failures: 23 total, 10 read qualitatively here (43%) — a reasonable but not exhaustive sample of the failure set; the remaining 13 were categorized only by the judge's one-line `reason` field, not the full answer text.
- No judge-fairness problems were spotted in the 10 read, but 10 is a small fraction of even this one slice, and "no problems in 10" is weak evidence about the judge overall — the dashboard's own tracked false-positive rate is 4.4% (CI 1.7%-10.9%, n=90), consistent with what's shown here but not confirming it.
