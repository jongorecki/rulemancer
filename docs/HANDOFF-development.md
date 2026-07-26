# Handoff — retrieval is the bottleneck, and the gold is good enough to prove it

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-25/26 session, which measured for the first time whether the RulesGuru
answers can be derived from our gold at all, ran a properly controlled
sonnet-vs-opus comparison, and found that the previous handoff's headline
comparison was measured on two different question sets.**

Suite: **573 passed, exit 0.** Commits this session: `a1c1bb8`, `a280f56`,
`eb0d410`, `e116fc2`, `56990b3`, `0a36b83`.

---

## ⚠️ FIRST, UNLEARN THIS

**1. "opus-low 75.0% vs sonnet 63.0/66.7% on the same bucket" was not the same
bucket.** Sonnet's reps are `layers_slice0_base_layers_r1/r2.json`, **n=54**.
The opus run is `opus5_low_norewrite_costbase.json`, **n=68**. Scored on the
shared 54, opus-no-rewriter is **72.2%**, not 75.0%. The prior handoff asserted
"the same bucket" and that assertion was repeated for a full session before
anyone opened the files.

**2. Retrieval, not reasoning, is the bottleneck.** Earlier reasoning in this
session guessed the opposite from the layers/timestamp failure cluster. The
derivability run settles it: hand the model the gold rules and it answers 90%.
Production sits at ~75-82%. That gap is retrieval and it is worth 11-18 points.

**3. Mined gold is a draw, not a fact.** Two independent mining runs on the
*identical* 50 questions produce identical gold on **26%** of rows, mean overlap
**0.54**, with 6 of 50 sharing no rules at all. This is a property of the method
and applies to the original 150-row run too.

---

## THE TWO SWITCHES JON IS CONFIDENT IN — APPLY THESE

Both are one-line constant edits in `src/rulesagent/generate/answer.py`. Jon
ruled on both 2026-07-26; the evidence for each is below.

### 1. `GEN_MODEL = "claude-sonnet-5"` -> `"claude-opus-5"`, with `effort="low"`

Properly controlled head-to-head, **same 54 questions, rewrite v2, ruling raw,
system v3, same frozen judge — model and effort the only differences**:

```
sonnet-5  default effort   r1  66.7%   r2  63.0%    mean 64.8%
opus-5    effort low       r1  75.9%   r2  72.3% (partial, 47q)
delta                                              +11.1 pp
paired r1 vs r1: opus wins 9, loses 4, net +5 of 54
```

Both opus reps beat both sonnet reps. Adding the rewriter moved opus 72.2% ->
75.9%, confirming the old comparison had opus fighting with a hand tied. Cost
$0.0741 vs $0.096 = **23% cheaper today**, widening to ~48% when sonnet's intro
pricing ends **2026-08-31**.

Sonnet's own two reps disagree on 6 of 54 questions (11% within-arm noise), so
read +11.1pp as a solid win, not a blowout.

**Jon's framing, keep it in the writeup:** this is a *cost decision with
supporting quality evidence*, not a quality claim that happens to save money.

**Caveat that was still open when he decided:** the easy-question regression
check had not finished (see IN FLIGHT). A model that reasons better on hard
questions can be worse on simple ones by overthinking them, and bucket A is the
hardest slice we own, so nothing in the +11.1pp can reveal that.

**`GEN_MODEL` is all-or-nothing.** There is no canary path — flip the constant
and 100% of traffic moves. No 10% rollout, no automatic rollback.

### 2. `REWRITE_N = 1` -> `3` (multi-query)

Retrieval-only evidence, measured against v3 gold at production `TOP_K=15`:

```
groups@15    vector 11.4%  ->  rw1 (production) 16.5%  ->  mq n=3  20.3%
paired vs production: +10 / -4
cost: +$0.0005/question (0.69% of the answer cost); generation cost unchanged
```

+3.8pp over production, **below the 7pp bar fixed before that run**, so this is
Jon overriding a null result on cost-benefit grounds — the change is nearly free
and trivially revertible. Note n=1 is better at the very top (`groups`@5: 8.9%
vs 3.8%) and n=3 better deeper; at TOP_K=15 n=3 is ahead but only just.

**`REWRITE_N` is not reachable from the CLI.** `run_answer_eval.py` exposes
`--rewrite` and `--rewrite-version` (the *prompt* version, not the count);
`RulesAgent.answer()` reads the module constant directly at line ~1871. So there
is currently **no way to A/B this on answers** — only on retrieval recall. If you
want that, thread it as a constructor param + `--rewrite-n` defaulting to 1,
exactly the pattern `effort` and `cache_prompt` already use.

---

## THE HEADLINE RESULT: DERIVABILITY

`docs/results-derivability.md`. Answers Jon's question: *"I want to make sure we
can derive the rulesguru answers from the gold rules and rulings."*

```
Arm B — gold rules only, no retrieval        135/150 = 90.0%   $8.47
  L0 100%   L1 100%   L2 93%   L3 80%   Corner Case 77%

Arm C — the 15 failures, re-run with gold + retrieved top-15   $1.37
  gold was INCOMPLETE (passed with retrieval)   4  (rg7215, rg549, rg851, rg811)
  beyond retrieval (failed both ways)          11

  135/150 = 90.0%   as it stands
  139/150 = 92.7%   ceiling with perfect retrieval
   11/150 =  7.3%   unreachable by ANY retrieval work
```

**92.7% is the most this eval can ever score.** The 11 unreachable questions are
reasoning failures or wrong RulesGuru answers — that second class is confirmed
(3 were found and corrected this session).

Two of the four incomplete rows had exactly ONE gold id. **Single-id rows are the
risk group** — cheap heuristic for finding more.

Arm C ran only where arm B failed, at 9% of the cost of re-running all 150.
Reuse that pattern.

---

## WHAT SHIPPED

**Prompt caching**, opt-in (`RulesAgent(cache_prompt=)`, `--cache-prompt`),
default off so requests stay byte-identical. Verified live, not asserted: first
call `cache_creation_input_tokens=2065`, next two `cache_read_input_tokens=2065`.
Saves $0.0093/question after the first (~$0.62 per 68-question arm). **Do not
judge it by the dollar total on a small sample** — output length is unpinned and
its variance is larger than the saving. The payoff case is ablation.

**Bug fixed: `--effort` was silently dropped on the frozen-prompt path.**
`_answer_from_frozen_prompt()` took neither effort nor caching, so any
`--prompts-cache` run generated at the API default no matter what `--effort`
said. A frozen "high effort" arm was really a default-effort arm with nothing
raising.

**Derivability harness** (`evals/build_gold_prompts.py`) — builds frozen prompts
from a chosen chunk set via `build_prompt()` + `--prompts-cache`, touching no
production code. Zero API cost to build; aborts rather than spend if an
embedding is missing.

**10 questions repointed** whose gold cited folded parent rules absent from the
chunk index (`702.16` is a heading; its text lives in children). Those were
permanent misses at any k; for rg434 and rg939 it was the ONLY gold id. **The
corpus now has 0 unretrievable gold ids.**

**3 RulesGuru answers corrected** where a WotC card ruling contradicts the
dataset (`docs/gold-corrections.md`). Established exception: **an official card
ruling outranks RulesGuru gold** — objectively checkable, unlike Jon-vs-judges.

**Miner prompt is now a versioned file** (`evals/gold_miner_prompt.md`) with the
merge rule added (v2). It previously existed only inside dispatch messages.

---

## THE OPEN DEFECT: CONJUNCTIVE OR-GROUPS

Adversarial review (2026-07-26) found the one thing every structural check
passed over. A `gold_group` means *"any one of these suffices."* Miners have been
putting **consecutive steps of a reasoning chain** in one group, so a retriever
that finds half a chain scores full credit — **recall inflation**.

Proven systematic, not incidental: the pair `616.1` + `616.1f` is split into two
required groups in rg263/264/436/440/749 and merged into one in rg124/564/647.
Same rules, same role, opposite treatment. 5 of 9 sampled multi-member groups
were wrongly merged.

```
exposure:  questions_rulesguru150_v3.jsonl   105 multi-member groups, 31 any-rows with 2+ ids
           gold_proposals_full_b01..b09      162 multi-member groups
```

Rule 6 in the v2 miner prompt states the test: *merge only if each member ALONE
fully licenses that step's claim.*

**Jon HELD the v3 re-pass.** Consequence, and it must travel with the numbers:
the recall figures in `docs/results-retrieval-diversity.md` are **optimistic in
absolute terms**. Relative comparisons between arms are unaffected — every arm
was scored against the same gold. `groups`@15 is really worse than 10-11%.

It does **not** affect the derivability result: arm B hands the model every gold
id regardless of grouping.

---

## IN FLIGHT WHEN THIS WAS WRITTEN

**State as of 2026-07-26 08:48.** Generation of the easy-set regression check is
nearly done; judging of the finished arms was started and deferred to the next
session by Jon.

```
evals/answers/h2h_opuslow_hard_r2.json      54/54  DONE (the truncated rep is complete)
evals/answers/h2h_opuslow_easy_r1.json      50/50  DONE
evals/answers/h2h_opuslow_easy_r2.json      50/50  DONE
evals/answers/h2h_sonnet_easy_r1.json       running (~43 s/question)
evals/answers/h2h_sonnet_easy_r2.json       queued
```

Judging of the three DONE arms was launched (job `b8vli4mc2`) and should have
produced `evals/verdicts_h2h_opuslow_easy_r{1,2}.json` and
`evals/verdicts_h2h_opuslow_hard_r2.json`. **Check those exist before re-running
the judge** — if they do, only the two sonnet arms still need judging:

```
uv run python evals/judge_rulesguru.py \
  --answers evals/answers/h2h_sonnet_easy_r{1,2}.json \
  --questions evals/_easy50.jsonl \
  --out evals/verdicts_h2h_sonnet_easy_r{1,2}.json
```

gpt-5-mini via OpenRouter — a different provider, unaffected by Anthropic limits.
The easy set is 50 questions, 31 at level 1 and 19 at level 2, disjoint from
bucket A and the v3 150, mean reference answer 271 chars vs bucket A's 388.

**Also worth recording from these runs: opus-low is ~2.5x faster.** The three
opus arms took ~14 minutes per 50 questions; sonnet at default effort is tracking
~36. That is a latency win on top of the cost win, and nothing has counted it
yet.

**Read the comparison as:** opus easy vs sonnet easy, two reps each. No
regression confirms the switch. A regression does not reverse it — Jon decided on
cost — but tells you to watch simple questions and points at a fix such as
splitting effort by question difficulty. Remember sonnet's within-arm noise on
the hard set was 6 of 54 questions (11%), so a gap smaller than that is not a
finding.

### ⚠️ CHECK ROW COUNTS BEFORE INTERPRETING ANYTHING

The sonnet arms were still generating when the previous session ended, unattended.
**Nothing flags a run that stopped early** — a sonnet arm that quietly died at 30
of 50 questions produces a valid-looking JSON file and reads as a legitimate
result. This already happened once this session: an account usage cap killed
`h2h_opuslow_hard_r2` at 47/54 mid-run, and the file looked fine.

Before judging or interpreting, confirm every file is full length:

```
h2h_opuslow_hard_r2.json      54 rows
h2h_opuslow_easy_r{1,2}.json  50 rows each
h2h_sonnet_easy_r{1,2}.json   50 rows each   <- these two are the risk
```

If a file is short, or `h2h_sonnet_easy_r2.json` never appeared at all, the
process died rather than finished. The fix is simply to re-issue that one run —
`run_answer_eval.py` resumes from the existing `--out` file rather than starting
over, so only the missing questions cost anything. The exact commands are in
git: `git log -1 --format=%H` on the session that created these, or reconstruct
from the `condition` field recorded in each row.

Two sessions can safely run against this repo at once — the processes are
ordinary OS processes writing incrementally, and editing `answer.py` cannot
affect a run already in flight since Python reads the module at import. The one
real collision risk is a second session **re-running or re-judging these same
files while they are still being written**, so leave them alone until the row
counts above check out.

**How to read it:** no regression confirms the switch; a regression does not
reverse it (Jon decided on cost) but tells you to watch simple questions and
points at a fix such as splitting effort by difficulty.

**Mining is PAUSED at 450/1,259 rows** (b01-b09 + b09_rerun). All verified: 0
inventory violations, 0 union mismatches, 5 untraced (emitted with `gold: []` and
a rationale, correctly). 63% recovery of existing gold, matching the original
run's 67%.

---

## WAITING ON JON

1. **Double-mine for stability?** Given 0.54 run-to-run overlap, mining each
   batch twice and taking the union would make gold stable and fits the existing
   "never drop an alternative" rule. Doubles subscription cost (~5.8M more tokens).
2. **Re-pass v3's 105 groups?** Would move published recall numbers downward.
3. **Resume mining as-is?** 809 rows remain, ~2.4M subscription tokens.
4. **The placement pass.** ~800 existing gold ids the miners didn't rediscover
   need homes. **Jon ruled: never promote** — every unrecovered id becomes an
   alternative in the group covering its step, or is kept as not-load-bearing;
   anything an agent thinks deserves its own required group is **flagged, not
   applied**. Rationale: the old flat `any` label already declared that id
   sufficient alone, so promoting it to required contradicts its own label. If
   the original 2/96 ratio holds that's ~15 flagged cases for Jon. **Record this
   in DECISIONS.md when the pass is built.**

---

## QUEUE, ROUGHLY PRIORITISED

- Apply the two switches above.
- Collect and judge the in-flight runs.
- **Security, added by Jon 2026-07-26.** `docs/plan-deploy.md` §2 already
  specifies per-IP rate limiting, a kill switch, and a budget breaker, and
  records that **none of it exists yet** — the plan's own gate says do not share
  a public URL until §2 is verified live. Prompt injection: the untrusted surface
  is card oracle text and rulings from Scryfall flowing straight into the prompt,
  not just the user's question. Authentication: `TODO-SSO.md` (OIDC then SAML
  against Okta and Entra) doubles as job-hunt evidence; the deploy plan
  deliberately decouples it from going public.
- **Adversarial review of the bot itself** — this session reviewed the *method*,
  never the product.
- `scripts/check_cr_update.py` — approved spec, still unbuilt, zero API,
  self-testing (same CR in both slots -> 100% unchanged, 0 remaps, 0 flags).
- Ruling gold. `EvalQuestion` has no field for it, yet all three corrected
  answers this session hinge on a card ruling. `ruling_id()` is already
  content-fingerprinted and is the right key — **never index-based**: labels are
  0-based (`ruling #4` is the fifth) and a Scryfall reorder once mismatched 92%
  of cached ruling embeddings. Mine it by ablation on questions that pass arm B.
- Model bakeoff (deepseek-v4-flash, gpt-5-mini Flex, sonnet-5 @ low, opus-5 @
  low). **Grok excluded on Jon's moral grounds — do not reintroduce it.**
- Legality-gate prompt arm — size it first from the 34 confirmed-wrong misses;
  must not land during the bakeoff.
- The 70-row gold-error audit pool, unreviewed (judgment work, not a filter).
- `rg4420`'s gold should become `606.5` now that the rule is in the index.
- Header sweep covered only the 150; 456 questions across the 1,409 cite a
  parent-with-children.

---

## HOW JON WORKS (unchanged, load-bearing)

- **Explain things properly.** Jon's note, 2026-07-26: *"you get a little over my
  head on things you're not explaining... you just need to explain things a
  little better so I can understand and be a partner here instead of an
  observer."* Define jargon at first use, lead with what a thing means before
  what it is, and show a concrete example rather than an abstract description.
- **Rule 0: plan before code.** Every `plan-*.md` / `spec-*.md` is design-only
  until Jon rules.
- **USE SUBAGENTS.** Opus on the subscription for mining/analysis, Sonnet for
  scoped implementation against a written spec. *If your harness forbids the
  Agent tool, say so immediately.*
- **THE BILLING BOUNDARY.** Claude Code and its subagents run on Jon's Max
  subscription. Python in this repo that constructs an Anthropic client bills
  **API credits** — a separate pool. Mining is subagent work; eval runs are API
  credits. An account-level usage cap was hit this session and Jon lifted it.
- **Verify agents' claims yourself.** Every batch was independently re-checked.
  It caught the b07 schema hole and the review's one wrong claim (empty gold
  scores as a miss and is already excluded from the denominator, not a free pass).
- **But verify the right thing.** Nine batches passed every structural check while
  the groups meant the wrong thing. Structural verification is not quality
  verification, and reporting one as the other is how this session nearly shipped
  a systematic flaw.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR,
  Scryfall via `rulesagent.tools.scryfall.get_card`, or a live check. Model facts
  via the claude-api skill.
- **Verify by rendering** for UI. Serve over `http.server`; **Jon runs the app on
  port 8000 — never bind or kill it.**
- Commit per slice on master, heredoc messages, `Co-Authored-By: Claude Opus 5`.
  `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is `uv run pytest`.
- **Never pipe a long run through `| tail` or `Select-Object -First`** — it closes
  the pipe and reports a false non-zero exit. Bit twice this session.
- **PowerShell `*>` buffers until the process exits**, so a running job's log is
  0 bytes and looks identical to a dead one. Check the output artifact, not the
  log.

---

## THE LESSON TO CARRY

Last session: *a value that looks like an identity but is really a position.*
This session, three variants of **a claim inherited and repeated without being
checked**:

- **"The same bucket."** Asserted by the prior handoff, repeated all session,
  false — 54 questions vs 68.
- **The miner prompt.** Reworded mid-run because it looked like prose. It is a
  parameter. (The drift it appeared to cause was disproved — worth 1pp, not 8 —
  but the fix, version-controlling it, was right anyway.)
- **"Zero violations."** True, and narrower than it sounded: the union check only
  ran on rows marked `groups`, so 27 rows missing the field entirely passed nine
  clean reports.

The pattern: **numbers arrive with claims attached about how they were produced,
and those claims are exactly as checkable as the numbers.** Open the file.
