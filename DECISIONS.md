# Decisions

Every non-obvious choice, logged as it's made. 5-10 lines each: what,
alternatives rejected, why, what would change your mind. This is interview
prep — write it in the moment, not reconstructed later.

Template:

```
## YYYY-MM-DD — <short title>

**What:** <the choice>
**Alternatives considered:** <what else was on the table>
**Why:** <the reasoning>
**What would change my mind:** <the condition that would flip this later>
```

---

## 2026-07-21 — Project scaffold, no OpenCode yet

**What:** Starting the build with Claude Code only. Repo skeleton matches the
build plan's target layout, in this existing `mtg-rules-bot` folder rather
than a newly-created `mtg-rules-agent` one.
**Alternatives considered:** Setting up OpenCode + OpenRouter first, per the
original plan's "install OpenCode, configure both keys" step.
**Why:** Jon wants to defer OpenRouter/model-rotation setup until later and
start writing code now. Model rotation for review is a stretch goal, not a
day-1 blocker.
**What would change my mind:** Once OpenCode/OpenRouter is set up, revisit the
"whoever writes doesn't review" rule — Claude Code has been both author and
only reviewer so far, which the plan explicitly warns against.

---

## 2026-07-21 — contracts.py field decisions

**What:** Six decisions locking down `contracts.py`:
1. Glossary gets its own `GlossaryEntry` class (`term`, `definitions`), not
   folded into `Rule`.
2. `Rule.text` excludes trailing `Example:` blocks — those live in
   `Rule.examples` instead.
3. `Rule.parent_chain` is a full audit trail for every rule, not just
   lettered subrules (e.g. plain rule "104.3" still records `["104"]`).
4. `Rule.section` is just the section name string (e.g. "Game Concepts"),
   no separate number field or lookup table.
5. `Rule.kind` is `Literal["rule", "subrule"]` only — "glossary" was cut
   since those rows are `GlossaryEntry` now, never `Rule`.
6. Cross-references ("see rule 201.3") stay as plain text wherever they
   appear — not resolved into links, not pulled into their own field.

**Alternatives considered:** Squashing glossary into `Rule` with `number`
repurposed to hold the term name; a fourth `kind` value for section
headers; a separate section-number field.

**Why:** Splitting glossary out lets it be labeled and displayed as a
different kind of result from a rule, even though a definition's "See rule
113" line still ties it back to one (that tie stays as plain text — nothing
structural needed to preserve it). The rest are all "don't build machinery
before something needs it" calls — no fields, tables, or extra `kind`
values for features that don't exist yet.

**What would change my mind:** If a real feature needs to query "everything
in section 7" or "jump straight to the rule a glossary term cites," that's
the point to add a section-number field or a structured cross-reference
field — not before.

---

## 2026-07-21 — Parser: finding the real body past the Contents page

**What:** The Contents page near the top of the CR file repeats the exact
same heading text ("1. Game Concepts," "Glossary," "Credits") that the real
sections use later. Searching for those headings from the top of the file
would stop at the Contents page's copy, not the real one. Fix: find the
first line that matches a full rule pattern (e.g. "100.1.") — that pattern
never appears on the Contents page, only in the real body — then walk
*backward* from there to the nearest section heading. That's guaranteed to
be the real "1. Game Concepts," since it's the one immediately before
actual rule text starts. "Glossary" and "Credits" are then searched for
starting from that point onward, past the Contents page entirely.

**Alternatives considered:** Hardcoding a line number or byte offset where
the real body starts. Counting a fixed number of "Contents"-like lines to
skip.

**Why:** Hardcoding a line number breaks the moment Wizards ships a new
revision with different pagination. Searching forward for a heading text
match breaks on the very first run, because the Contents page hits first.
Anchoring on "first thing that looks like an actual rule, then look
backward" survives revisions because rule numbering (100.1, 100.2, ...)
is structurally stable in a way page layout isn't.

**What would change my mind:** If a future CR revision ever puts a full
rule-shaped line inside the Contents page itself, this breaks — no
evidence that's ever happened, but it's the one assumption this approach
rests on.

**Measured (2026-07-21):** 3,151 rules parsed, 735 glossary entries, 44% of
rules under 30 words, 213 rules with at least one example. The 44% number
is what the chunking decision (Day 2) gets made from.

---

## 2026-07-21 — Chunking: label-like rules don't get their own chunk

**What:** The 44% "under 30 words" bucket isn't one kind of thing. Some are
short, complete, standalone sentences (e.g. `104.3f: "If a player would
both win and lose the game simultaneously, that player loses the game."`).
Others are bare labels with no independent meaning at all (e.g. `205.3:
"Subtypes"`, `701.49: "Venture into the Dungeon"`) that only make sense
together with the lettered subrules underneath them. Decision: a rule is
"label-like" if (a) it has subrules under it, (b) it's 6 words or fewer,
and (c) after stripping a trailing closing curly-quote or paren, it
doesn't end in `.`, `:`, or `?`. Label-like rules don't get their own
chunk — their (short) text becomes prepended parent-context on each of
their children's chunks instead. Every other rule gets its own chunk: its
own text, its immediate parent's text prepended, and any attached
`Example:` text appended.

**Alternatives considered:**
- Word count alone (<=4 words): zero false positives, but missed two real
  5-word labels ("Roll to Visit Your Attractions," "More Than Meets the
  Eye").
- Punctuation-ending alone (no word-count bound): fixed those two, but
  wrongly flagged two long, legitimate rules (602.1, 603.1) that happen to
  end with bracketed template notation instead of plain prose.
- Punctuation check counting "!" as a sentence-ender: wrongly excluded two
  more real labels ("For Mirrodin!", "Start Your Engines!") — flavor-named
  keywords that end in "!" without being sentences.
- Merging a whole rule family (base + all lettered subrules) into one
  chunk, always: rejected — families like 104.3 have 11 subrules, and
  cramming all of them into one chunk risks the embedding blurring across
  11 different situations, plus it loses per-subrule citation precision
  everywhere, not just for the ~270 pathological cases.

**Why:** Each single-signal version looked "robust" until checked against
the full 3,151-rule corpus, where it turned out to have a different blind
spot. The combined check — word count as a scope limiter, sentence-ending
punctuation as the actual decision within that scope, "!" excluded because
it's decorative here, not grammatical — was checked against every rule in
the file with zero known exceptions in either direction. Simpler versions
each had exactly 2 known misses; this one currently has none.

**What would change my mind:** If a future CR revision introduces a label
longer than 6 words, or a short legitimate rule that happens to end
without terminal punctuation, this heuristic will misclassify it. That's
an acceptable, documented gap for now — the fix is to read it off an
actual eval failure once the eval harness exists (days 3-5), not to keep
hardening this check against hypothetical future formatting no evidence
supports yet.

---

## 2026-07-21 — Child detection: parent_chain membership, not string prefix

**What:** Deciding whether rule A is a child of rule B (used for label
detection's "has children" test). Implemented as: B is a child of A if A
is in B's `parent_chain`. NOT as: B's number starts with A's number.

**Alternatives considered:** Naive string-prefix match
(`b.number.startswith(a.number)`), which is what the orchestrator's spec
originally called for.

**Why:** String-prefix has a false positive: `"118.10".startswith("118.1")`
is True, which would wrongly classify sibling rule 118.10 as a child of
118.1. `parent_chain` encodes the actual dotted hierarchy the parser
derived, so it's immune. This collision is NOT hypothetical — it fires on
52 rules in the current ruleset (every X.1 that has an X.10-or-higher
sibling: 106.1, 107.1, 111.1, 113.1, 118.1, etc.; rule 118 alone runs to
118.14). It happens not to change the final label count (269 either way)
only because none of those 52 affected rules are label-shaped — they're
all full sentences, so a phantom "has children" flag can't flip them into
labels. That's luck of this ruleset's content, not a property to rely on;
parent_chain is correct regardless. (Correction: an earlier draft of this
entry claimed no such collision existed in the current data — Jon caught
that by noticing rule 118 runs to 118.14, and the 52-rule count was then
measured.) Caught in two stages by human+model review, not by the
orchestrator's original spec — a live example of "whoever writes doesn't
review."

**What would change my mind:** Nothing foreseeable — parent_chain is
strictly more correct here at no extra cost, since the parser already
computes it.

**Measured (2026-07-21):** 3,151 rules + 735 glossary in -> 3,617 chunks
out (2,882 rule + 735 glossary); 269 rules dropped as label-like.

---

## 2026-07-21 — Golden test coverage expanded to all 9 sections + 700s verified

**What:** Added test_golden_sections.py: one structural test per section
2-9 (section name, kind, parent_chain, example count), a test that all
nine section names are present, and two exact-behavior tests for the
section-7 label mechanic (keyword "Cast" 701.5 produces no chunk; its
child 701.5a leads with "Cast" prepended). Suite: 25 -> 36 tests.

**Alternatives considered:** Exact full-text assertions on all breadth
cases (heavier, and the value there is "section is handled," which
structure proves); leaving coverage clustered in section 1 (the original
state — no evidence sections 2-9 were exercised at all).

**Why:** Breadth via structural assertions is robust and cheap; exact-text
is spent where subtle breakage actually bites (the label mechanic).
Parse golden tests assert "matches what's literally in the file" —
transcription, verifiable by re-reading the file — which is distinct from
"what counts as a correct ANSWER" (the eval question set, still
do-not-delegate, comes later).

**Verified (section 7, the label detector's stress test):** 1,518 rules in
section 7, 261 classified as labels (261 of the 269 total) — all clean
keyword names, e.g. Activate/Attach/Behold/Cast. Checked both failure
directions across the whole corpus: zero childless short keyword names
leaking through as false non-labels, and zero missed labels in the 7-9
word range (our <=6-word bound cuts off nothing real — longest actual
labels are 5 words). The label detector is sound on the section that
exercises it hardest.

**What would change my mind:** A future CR revision adding a keyword name
longer than 6 words would slip past the bound; caught then off an eval
failure, not hardened for speculatively now.

---

## 2026-07-21 — Eval sets stay separate per corpus

**What:** Eval questions are scoped to the retrieval system they measure.
The current set is Comprehensive-Rules-only: gold answers are rule/glossary
chunk ids, recall@k measures rules retrieval. Card- and ruling-based
questions (answerable only from Scryfall data) get their OWN separate eval
set later, with gold ids pointing at cards/rulings.

**Alternatives considered:** One combined question file spanning rules +
cards + rulings.

**Why:** A card question has no gold RULE chunk, so putting it in the rules
eval set makes it an automatic miss that drags recall@k down for a reason
unrelated to rules retrieval — it corrupts the metric. Aligning each eval
set to its own corpus/index keeps every number honest and attributable.

**What would change my mind:** If we ever build a single unified index over
rules + cards + rulings, the eval set would merge with it — but that's not
the current architecture and isn't planned for days 1-9.

---

## 2026-07-21 — Embedding provider: Voyage AI (Phase B)

**What:** When we add vector retrieval (Phase B), use Voyage AI —
`voyage-4` (or voyage-4-large) for embeddings, `rerank-2.5` for the later
rerank phase. Not actioned yet; requires a Voyage API key at Phase B.

**Alternatives considered:** OpenAI (text-embedding-3-large), Cohere
(embed-v4 + Rerank), Google Gemini, Jina, self-hosted Nomic/Qwen3. Full
comparison with sources in docs/embedding-providers.md.

**Why:** Only option pairing top-tier domain/jargon retrieval quality with
a bundled reranker under one account/SDK; 200M-token free tier makes our
~3,600-chunk corpus effectively free, so we optimize purely for quality
without onboarding a second vendor for reranking. Cohere is the fallback if
reranking outweighs embedding quality.

**What would change my mind:** If Voyage quality disappoints on our actual
retrieval failures, or if self-hosting an open-weight model (Qwen3-Embedding
now tops MTEB) becomes worthwhile. Gotcha: target voyage-4, NOT voyage-3
(v3 lost the free tier Jan 2026).

---

## 2026-07-21 — Eval harness (Phase A): match field + curated 32-question set

**What:** Built the eval harness measuring retrieval recall@k over BM25.
Added a `match` field to EvalQuestion distinguishing two kinds of multi-rule
question:
- `match="any"` (default): gold ids are ALTERNATIVES — any one in top k is a
  hit (restatements, or either rule independently answers).
- `match="all"`: gold ids are ALL REQUIRED — a true interaction, hit only if
  every gold id is in top k (the honest bar for "generator has everything").
Eight questions tagged `all`: q002, q003, q004, q014, q016, q020, q021, q029.

**Gold audit (Jon's call — do-not-delegate grading criteria):** every
`any`-tagged multi-gold question was checked so each surfaced rule truly
answers it alone. Fixes: q006 dropped 506.4 (lists general removal triggers,
never mentions end-of-combat timing); q009 dropped 613.1f (only 702.1
answers — a keyword IS an ability); q020 and q021 promoted to `all` (both
genuinely need every piece). q029 promoted to `all` too — Jon overrode the
orchestrator here: "when are lore counters put on sagas?" asks for the
complete set of times (on entry via 714.3a AND each precombat main via
714.3c), so a partial answer naming one time is incomplete. The "each time
is independently a valid 'when'" framing was wrong — it's an enumeration
question, like q021.

**Why:** at-least-one recall overstates success on true interactions —
finding half of trample+deathtouch isn't answering it. Distinguishing
alternative-answer from conjunctive-answer questions makes every number
honest, and interactions are exactly where vector/hybrid should later show
the biggest gains.

**Measured — BM25 baseline (THE number we move from):** recall@1=22%,
recall@5=38%, recall@10=50%, over 3,617 chunks / 32 questions. Failures
cluster into named patterns (lexical gap, glossary distractor, short-primary-
def-beaten-by-children, priority-term-saturation) — see LOG.md.

**What would change my mind:** As real usage surfaces question types the set
underweights, expand it. The 32 are a starting set, not final.

---

## 2026-07-21 — Voyage account created (Phase B ready)

**What:** Jon set up a Voyage AI account (2026-07-21), so the embedding key
is ready when Phase B (vector retrieval) begins. No code change yet — Phase A
is BM25-only. Provider rationale in docs/embedding-providers.md.

---

## 2026-07-21 — Full audit of every "any" question (strict completeness bar)

**What:** Applied the standard "each surfaced rule must COMPLETELY answer the
question alone, no extra info" to all 24 `any`-tagged questions. 17 passed
unchanged. Six were revised:
- q010: dropped 514.1 (only describes the cleanup discard; doesn't state you
  may draw past max). Gold now just 402.2.
- q012: dropped the "Dies" glossary entry, which restricts dying to
  creatures/planeswalkers and CONTRADICTS rule 700.4 ("dies means is put into
  a graveyard from the battlefield," no type restriction). Jon's call: trust
  the rule over the glossary (rules are more current). Answer: yes, a
  non-creature artifact dies. Gold now 700.4.
- q015: promoted to `all`. 605.3b and 605.4a each cover ONE mana-ability
  subtype (activated / triggered) explicitly; neither states the general case,
  so both are required to fully answer "can I respond to a mana ability?"
- q008: reworded to correct terminology ("can I sacrifice an evoked creature
  before that creature's evoke triggered ability resolves?") and promoted to
  `all` with gold [702.74a, 603.3]. 702.74a establishes the evoke sacrifice is
  a triggered ability; 603.3 establishes triggered abilities go on the stack
  and you get priority to respond. The reword is correctness, NOT writing-to-
  pass (gold stays honest, and it will likely still fail BM25 -- legit
  interaction headroom).
- q023 ("are subgames legal?"): CUT. Ambiguous ("legal" = rules-construct vs
  tournament-legal, and Shahrazad is actually banned), neither chunk cleanly
  answers, and subgames essentially never come up. 32 -> 31 questions.
- q019: kept `any` unchanged -- "destroyed as a state-based action" is a
  complete answer; surfacing the related timing rule (704.3) is a later
  concern, not retrieval recall.

**Why:** the q029 override exposed that `any` was being applied too loosely.
This pass makes every gold set honest: `any` means each id truly stands alone,
`all` means each id is genuinely required.

**Forward notes captured for the generation/agent phase (days 6-9):**
- Query-rewriting/clarification layer: rewrite messy user phrasings into proper
  rules terminology (and optionally clarify with the user) BEFORE retrieval --
  e.g. "sacrificed to the evoke trigger" -> "before the evoke triggered ability
  resolves." Standard RAG pattern; the right home for that translation.
- Multi-hop / cross-reference retrieval: for answers like q019 that say "see
  rule 704," have the agent optionally pull the referenced rule for a richer
  answer. A generation-phase enhancement, not a retrieval-recall metric.

**Measured — curated BM25 baseline:** recall@1=16%, recall@5=32%,
recall@10=45% over 31 questions. 10 questions now `all`-tagged.

---

## 2026-07-21 — Phase B: vector retrieval, voyage-4-large wins the A/B

**What:** Added Voyage embedding retrieval (asymmetric: input_type=document
for corpus, query for queries), a NumPy+pickle brute-force vector store, and
a side-by-side eval of BM25 vs voyage-4 vs voyage-4-large. Adopting
**voyage-4-large** as the default embedding model.

**Measured (31 questions, recall@5):** BM25 32% -> voyage-4 55% ->
voyage-4-large 65%. voyage-4-large beats voyage-4 by ~10 pts at every k
(recall@1 32 vs 23, recall@10 81 vs 74). Since the corpus is tiny and free-
tier covers it, there's no cost reason to prefer the smaller model.

**Reading the per-question deltas (the point of the eval):**
- Lexical-gap questions flipped miss->hit exactly as predicted, e.g. q007
  "Do you cast lands?" (rule says lands are "played," not "cast" -- BM25
  blind, embeddings bridge it). Also q005, q013, q025, q030, q031, q020, q015.
- q001 "phasing back in trigger ETB?" is the case FOR hybrid: BM25 hits, both
  vector models miss. The rare word "phasing" is a strong lexical signal
  embeddings smear away. Phase C combines the two rather than replacing.
- Still hard: `all`-tagged interactions (q004, q008, q014, q016, q021),
  priority term-saturation (q026/q027 -> 117.3c), and layers (q017). Targets
  for hybrid (C) and rerank (D).

**Latency note:** ~152 ms/query is almost entirely the Voyage API round-trip
to embed the query. The brute-force cosine search over 3,617 vectors is
sub-millisecond -- the "no vector DB" choice holds emphatically; the only
latency is network, removable by caching query embeddings.

**What would change my mind:** If hybrid + rerank close the gap and a cheaper/
smaller model matches voyage-4-large on our questions, downgrade for latency/
cost. Not now.

---

## 2026-07-21 — Phase C: hybrid does NOT help; keep pure vector

**What:** Built hybrid retrieval (RRF and weighted-score fusion) over BM25 +
voyage-4-large and A/B'd both. Result: neither beats pure vector at recall@5,
so hybrid is NOT adopted. Pure voyage-4-large stays the retriever, and feeds
Phase D reranking as a depth-50 candidate pool.

**Measured (recall@5 / @20 / @50):**
- BM25: 32 / 61 / 71
- voyage-4-large: 65 / 81 / 90
- hybrid-RRF: 48 / 74 / 87
- hybrid-weighted@0.5: 55 / 87 / 87
- weighted alpha sweep @5: a=0.3 -> 48%, 0.5 -> 55%, 0.7 -> 65% (converges to
  pure vector as vector weight rises).

**Why hybrid loses here:** BM25 (32%) is far weaker than vector (65%) on this
corpus, so equal-footing fusion demotes vector's reliable hits below k=5. RRF
suffers most -- it uses rank only, treating a rank-1 vector hit (reliable) the
same as a rank-1 BM25 hit (often noise). The alpha sweep confirms it: the more
you weight vector, the better, converging on pure vector. Hybrid-weighted does
edge vector at the k=20 POOL (87 vs 81) by rescuing a few BM25-only chunks
(e.g. q001 phasing), but at k=50 pure vector's pool is best (90 vs 87), so it's
the better first stage for reranking anyway.

**Why keep the code:** the finding ("adding a component made it worse, here's
why, measured") is the point -- and hybrid may matter on a future corpus where
keyword and vector are more evenly matched.

**What would change my mind:** A corpus/domain where BM25 and vector are closer
in strength (hybrid's win case), or a smarter fusion that only lets the weaker
retriever rescue when the stronger one fails.

---

## 2026-07-21 — Eval reproducibility: freeze query embeddings

**What:** Voyage returns slightly different query embeddings on repeated calls,
so a question sitting at the rank-5/6 boundary flipped voyage-4-large recall@5
between 65% and 61% across identical runs. Fix: embed each question once, cache
to disk (data/parsed/query_emb_<model>.pkl, gitignored), and reuse. Added
VectorStore.search_vec(qvec) so the eval passes cached vectors.

**Why:** Eval reproducibility is the whole point of a pinned eval -- a metric
that wobbles run-to-run can't attribute a regression. After the fix, two
consecutive runs are byte-identical across every column, which ALSO confirmed
Voyage's reranker is deterministic given a stable pool.

**What would change my mind:** Nothing -- frozen query embeddings are strictly
better (deterministic + faster + no per-run query cost). Rebuild the cache if
the question set changes (new questions are embedded and appended automatically).

---

## 2026-07-21 — Phase D: reranking is a situational polish, not a free win

**What:** A/B'd Voyage rerank-2.5 vs rerank-2.5-lite, reranking the pure-vector
top-50 pool (Phase C decision). rerank-2.5 gives the best recall@5 but is NOT
adopted as an unconditional stage -- whether to rerank depends on how many
chunks the generator gets.

**Measured (recall@1 / @5 / @10):**
- voyage-4-large: 32 / 65 / 81
- rerank-2.5: 26 / 68 / 71
- rerank-2.5-lite: 23 / 65 / 77

**Why not an unconditional yes:** rerank-2.5 improves recall@5 by only +3 (65
-> 68) while HURTING recall@1 (-6) and recall@10 (-10) -- it reorders the pool
and pushes some good chunks past rank 10. rerank-2.5-lite gives no @5 gain.
So: if the generator is fed ~5 chunks, rerank-2.5 wins narrowly; if fed ~10
(cheap and normal), pure vector's 81% recall@10 clearly beats reranked's 71%.
The big lever was always embeddings (32 -> 65 recall@5); rerank is polish.

**Decision for the generation phase:** default to pure voyage-4-large feeding
the generator ~10 chunks (81% recall). Revisit rerank-2.5 only if we constrain
the context to a handful of chunks.

**What would change my mind:** If generation quality proves sensitive to the
top-1/top-3 ordering (not just presence in top-10), reranking's precision at
the very top may matter more than the recall@10 it costs.

---

## 2026-07-21 — Generation (Days 6-9): design

**What:** Built the cited-answer generator. Retrieves pure-vector top-10
(Phase C decision), hands the chunks to Claude, returns a structured Answer
{text, citations, answered}. Model pinned to claude-sonnet-5.

**Key choices:**
- Model = claude-sonnet-5, pinned (reproducible answer evals; the guidance
  defaults to Opus 4.8, but Sonnet is the better cost/quality fit for
  repeated eval runs, and it's a one-line swap to A/B). Jon's "stick to
  Claude" call.
- Structured output (Answer): citations and the answered flag are separate
  fields so the answer-accuracy eval can check grounding and the
  low-confidence path independently of the prose.
- Low-confidence path = the `answered` flag: the system prompt tells the
  model to set answered=false and say what's missing rather than filling
  gaps with outside knowledge. That's the groundedness guard.
- Retriever = pure vector top-10, not rerank (Phase D: rerank helps @5 but
  hurts @10; feeding ~10 chunks, pure vector's 81% recall wins).

**Grading (Jon's call):** reference answers + LLM-judge. Jon writes short
reference answers for the 31 questions; an LLM-judge scores generated-vs-
reference; Jon spot-checks. Not built yet -- needs the references + key.

**Scryfall:** the narrow card-lookup tool (name -> oracle text) is in scope
for this phase AFTER the core rules loop works -- it introduces LLM
tool-routing (card question vs rules question). The bulk-data corpus stays
deferred (docs/scryfall-notes.md).

**What would change my mind:** If answer accuracy is poor, revisit feeding
reranked top-5 instead of vector top-10, or raise k.

**Status:** answer.py built but UNTESTED -- needs ANTHROPIC_API_KEY to run.

---

## 2026-07-21 — Grading method: judge outputs against rule text, not references

**What:** Changed the answer-accuracy grading from "Jon writes reference
answers, LLM-judge compares" to "generate answers, Jon judges each against
the retrieved rule TEXT." Correctness criterion = faithfulness: does the
answer accurately represent the cited rules, and cite the right ones?

**Why:** Jon can't explain some topics (e.g. layers) from memory, so writing
reference answers for those isn't feasible. But judging is recognition, not
generation -- and judging *against the rule text we already have* (613.1a-g
for layers) needs reading, not MTG expertise. So every question becomes
gradeable by Jon, and we grade the property that actually matters for RAG:
groundedness / faithfulness (core AI-103 material). Jon still owns "what
counts as correct" -- he judges, an LLM-judge only pre-scores to save time.

**Tradeoff accepted:** judging outputs (vs pre-committed references) loses
the anti-anchoring guard of committing to ground truth before seeing the
model's answer. Mitigated by the check-against-rule-text step: a
confident-wrong answer won't match its cited rules. For questions Jon knows
cold, he can still pre-commit an answer to stay strict.

**Impact:** Jon's remaining input drops to just the ANTHROPIC_API_KEY --
no reference-writing. Reference answers become optional, per-question.

---

## 2026-07-21 — Answer accuracy: 93.5%, zero hallucinations

**What:** Jon graded all 31 generated answers against their cited rule text
(faithfulness). Result: 29 correct, 1 partial, 1 wrong = 93.5% (95.2% with
partial credit). Verdicts + notes persisted in evals/answer_verdicts.json.

**The key finding -- safe failure mode:** across 31 questions the bot never
confidently stated a false rule. Both non-correct answers were SAFE failures:
q016 was an honest decline (answered=false), q014 was incompleteness. The
groundedness guard (the `answered` flag) worked -- no hallucinated wrong
answers.

**Root-cause of the two misses -- retrieval, not generation:**
- q016 ("respond to a cost being paid?"): the generator's top-10 was
  entirely cost-mechanics rules (118.x). NEITHER answering rule (117.3c
  priority, 601.2h casting-is-atomic) made the top-10, so it declined for
  lack of the answer. This is the SAME q016 that was a miss in the retrieval
  eval -- a clean causal chain: retrieval miss -> wrong rules fed to
  generator -> honest decline -> graded wrong. The two evals measure the
  same failure from opposite ends.
- q014 (defending player): retrieval got 506.1 + multiplayer 802.5 into the
  pool, but the answer only covered two-player. Generation/completeness.

**Actionable from Jon's notes (deferred, not done):**
- Prompt-tune: define key terms (q001 phasing) and name the zones involved
  (q020 command zone vs exile) -- correct answers that could be clearer.
- q014: cover multiplayer defending players; ensure 802.x ranks in.
- q016: the low-confidence guard is double-edged -- it prevents hallucination
  but declines answerable questions when retrieval misses the key rule. Fix
  is retrieval (get 117.3c/601.2h to rank), not loosening the guard.
- q029: consider adding 714.3b (read-ahead Saga variant) to gold -- optional.

**LLM-judge status:** Jon graded manually (recognition was feasible for all
but layers, checked against rule text). The planned LLM-judge is now a
regression tool -- re-grade after changes without Jon re-reading everything
-- not needed for this pass.

---

## 2026-07-21 — Finding fixes (#2): prompt + k, q016 deferred to #3

**What:** Addressed the answer-eval findings with GENERAL improvements (not
question-specific tuning): system prompt now asks to define key terms, name
the specific zones/steps/objects, and cover multiplayer/Commander cases;
generator k raised 10 -> 15 (a near-miss multiplayer rule sat at rank 13).

**Landed:** q001 now defines phasing; q014 now covers multiplayer defending
players; q020 now distinguishes command zone from exile. All three match
Jon's grading notes.

**q016 deferred to #3 (query rewriting), with evidence:** the two answering
rules rank 109 (601.2h) and 189 (117.3c) for that query -- no reasonable k
reaches them. The reworded answer now self-diagnoses ("I'd need rule 117 and
601/602"), confirming the gap is retrieval, fixable only by rewriting the
query into proper rules terms before retrieval. Not overfit-patched.

**Caveat:** the prompt change reworded ALL 31 answers, so a clean "only N
changed" diff isn't possible. Re-grade pending -- prior verdicts pre-load,
substance unchanged except the improved flagged ones; watch for regressions.

**714.3b:** to add to q029 gold (Jon's call) -- pending.

---

## 2026-07-21 — #3a spike: rewriting fixes one of q016's two rules, not both

**What:** Before building the query-rewriting layer, ran a two-API-call spike
to falsify it: rewrite q016 ("can I respond to a cost being paid?"), embed the
rewrites, and check where its two gold rules land. Split verdict.

**Measured (rank out of 3,617 chunks):**
- 601.2h: 108 -> **2** (sonnet-5, 3-rewrite set). Fixed decisively.
- 117.3c: 198 -> 69 at best (haiku-4-5); most rewrites made it WORSE (300,
  291, 219). Not fixed, and not fixable this way.

**Why 117.3c is unreachable by rewriting:** its chunk text is "Which player
has priority is determined by the following rules: If a player has priority
when they cast a spell, activate an ability, or take a special action, that
player receives priority afterward." It never mentions costs, responding, or
timing windows -- it's about who RETAINS priority. It answers q016 only via a
deductive hop (combine with 601.2h's "casting is atomic" => there's no window
during payment). Embeddings match meaning, not inference. Evidence the
retriever is fine: 116.3 ("If a player takes a special action, that player
receives priority afterward") -- near-identical wording -- ranks 9. And rank 1
was 118.2 ("if a cost includes a mana payment, the player paying the cost has
a chance to activate mana abilities"), which may answer the question better
than either gold id does.

**Decision (Jon):** build the layer on the 601.2h result; re-audit q016's gold
separately. Deliberately separating "is rewriting good?" from "is this label
right?" -- one questionable gold shouldn't veto a layer with a 50x measured
rank improvement, and equally a working layer shouldn't be used to justify
quietly relabelling gold. q016 is demoted from primary success criterion
(a label under review can't referee anything); the primary bar is now
aggregate recall@5 vs the 65% baseline with zero per-question regressions.

**What would change my mind:** if the gold re-audit concludes 117.3c really is
required for q016, then this class of question needs multi-hop / cross-
reference following, not rewriting -- a different build, deferred.

---

## 2026-07-21 — Fusing the rewrites with the ORIGINAL query hurts (Phase C, again)

**What:** The plan asserted that always fusing the raw question in alongside
its rewrites was a free safety property: a bad rewrite would degrade rank
gently because the original kept voting. Measured in the spike, it's the
opposite -- RRF(original + rewrites) was worse than the best single rewrite in
EVERY arm (601.2h: 2 alone -> 10 fused; 117.3c: 69 alone -> 145 fused).

**Why:** the original is a weak query -- that is the entire premise of the
slice. Fusing a weak input with strong ones dilutes the strong signal. This is
the Phase C hybrid finding restated (RRF lost there because BM25 at 32% was
forced onto equal footing with vector at 65%), and I walked into it again
having already written that entry. I'd predicted RRF would do well here
because every input is the same retriever at the same strength -- true between
rewrites, false once the original is mixed in, since the original is precisely
NOT an equal-strength input.

**Consequence:** the original is no longer fused in by default. Whether to
include it is now a measured arm (`+orig`) instead of an assumption.

**What would change my mind:** if `+orig` wins across all 31 questions, keep
it -- one question is not enough to settle it, which is why it stays an arm
rather than being deleted outright.

---

## 2026-07-21 — The reproducibility fix wasn't reproducible: rewrites are a random draw

**What:** The retrieval eval's headline recall@5 for rw1-haiku swung 68% / 71% /
77% across three clean re-runs of the SAME prompt, model, and questions -- and
the set of failing questions changed identity between runs (q025 one run,
q003+q030 another). The earlier "freeze query embeddings for reproducibility"
decision fixed Voyage's embedding wobble, but it only stabilizes retrieval GIVEN
A FIXED QUERY STRING. Rewriting makes the query string itself LLM output, i.e. a
random draw. The rewrite cache made any single draw reproducible, which quietly
hid that we were reporting one sample of a noisy variable. Verified directly:
Haiku produced three entirely different rewrites for the same question across
three calls.

**Fix:** `temperature=0` on the shipped Haiku rewriter. Sampling params are
rejected (400) on claude-sonnet-5 / Opus 4.7+ / Fable but ACCEPTED on Haiku 4.5
(older tier) -- and we ship Haiku, so the shipped path can be pinned. Gated by
model (`TEMPERATURE_OK`) so the eval's Sonnet comparison arms don't 400.

**Measured (noise floor, 5 fresh draws at temperature=0, cache bypassed):**
recall@5 = 67.7 / 71.0 / 71.0 / 67.7 / 71.0, mean 69.7%, stdev 1.6%, spread
3.2% (= one question). Per-question: 21 always hit, 9 always miss, 1 flaky
(q031). temperature=0 cut the noise floor from ~9 pts (~3 questions) to ~1
question. temperature=0 does NOT fully eliminate variance (the API docs are
explicit it never guaranteed determinism), but it localizes it to a single
flickering question.

**Consequences, stated honestly:**
- The real rw1-haiku recall@5 is ~70% (mean), NOT the 77% earlier reported.
  77% was a lucky high draw and a narrative was built on it. Honest #3a
  headline: pure vector 65% -> rewriting ~70%, a reliable +1-2 questions at k=5,
  with larger gains at deeper k and on specific buried questions (q016's 601.2i
  went rank 275 -> 16).
- Every prior cell-to-cell and prompt-to-prompt call made on a <2-question
  difference (the v1/v2 "9-point" gap, the q025/q010/q003 regressions) was
  inside the noise band -- dice, not signal. Prompt micro-tuning (v3, few-shot
  examples) is parked: it can't be validated below the noise floor, and the
  remaining 9 misses are dominated by match=all interactions that phrasing
  can't fix. The higher-ROI lever is the deterministic chunking split.

**What would change my mind:** if a future change needs sub-question resolution,
switch from a single frozen draw to reporting a k-draw mean +/- stdev as the
metric. For now temperature=0 + the committed rewrite-cache fixture is enough.

---

## 2026-07-21 — Cache no longer stores fallback results (would freeze a transient failure)

**What:** rewrite_query previously cached its fallback result (queries=[question])
on any failure. Fixed: the fallback path now returns WITHOUT writing the cache.

**Why:** caching a fallback freezes a transient failure (network blip, refusal,
truncation) permanently -- that question would silently never be rewritten
again, and because the cache makes it reproducible, the degradation would look
deterministic and correct. Not caching means the next run retries. Cost: a
persistently failing question re-hits the API every run, which is the loud
failure mode and the one we want.

**What would change my mind:** nothing foreseeable -- caching a known-bad result
is never what we want.

---

## 2026-07-21 — q016 gold re-audited to a single rule: 601.2i

**What:** q016 ("can I respond to a cost being paid?") gold changed from
["117.3c", "601.2h"] (match=all) to ["601.2i"] (single rule). This is the
re-audit promised when the rewriting spike proved 117.3c unreachable.

**Jon's reasoning (do-not-delegate: what counts as a correct answer):**
"respond to" presupposes you do NOT currently have priority -- responding means
acting in a window someone else's action opened. 601.2i is the rule that speaks
to exactly that: once the steps of casting (which include paying costs, 601.2f-h)
are completed, the spell becomes cast, and only THEN does its controller get
priority. So there is no window for anyone else to respond DURING payment --
paying a cost is part of casting, not a point where priority is passed.
- 117.3c ("if a player has priority when they cast... they receive priority
  afterward") is about who RETAINS priority, not about responding -- it never
  answered the question, and the spike proved it unreachable by any rewrite
  (rank stuck ~189).
- 601.2g / 118.2 (mana abilities may be activated during payment) describe what
  the PAYING player may do -- that's still part of casting, not responding to
  someone else. Including them would confuse "things you do while paying" with
  "responding to a payment," which is the exact ambiguity that made the original
  question a good but confusing test.

**Why this matters beyond q016:** the original question was underspecified in a
revealing way -- "respond to a cost being paid" conflates two situations (you
paying vs. reacting to someone else paying). The rewrite/clarification layer is
the right place to surface that ambiguity to a user later (deferred to #4).

**Measured note:** with rw1-haiku, 601.2i sits at rank ~16 -- just outside the
generator's k=15 window and outside recall@5. So this gold change does not flip
q016 to a hit at k=5; it makes the LABEL honest. Whether 601.2i climbs into
range is a target for the chunking split (601.2i is in the exact 601.2 family
whose shared-preamble dilution that change addresses).

**What would change my mind:** if the chunking split or a later multi-hop step
shows a second rule is genuinely required to answer completely, promote back to
match=all -- but on current reading 601.2i alone answers it.

---

## 2026-07-21 — Chunking: split embed_text from text (KEPT, a measured tradeoff)

**What:** Chunk now carries two fields. `text` (generator + citations) is
unchanged. `embed_text` (what vector + BM25 index) = own text + examples,
prepending the immediate parent ONLY when that parent is folded (label-like, no
chunk of its own). Plan + reasoning in docs/plan-chunk-context-split.md.

**Why:** `text` was doing two jobs with opposite needs -- the generator wants
completeness, retrieval wants distinctiveness. Prepending a long shared parent
preamble onto every sibling made whole rule-families embed to nearly one vector
(601.2 family sat at 0.83-0.99 cosine), so which sibling ranked first for a
family-level query was near-arbitrary. The rule is structural, not a tuned
threshold: prepend a parent only when folding it away would delete its words
from the index entirely (median folded-parent text is 7 chars, e.g. "Cast");
when the parent has its own chunk it's already retrievable and duplicating it is
pure noise (median 204 chars of redundant preamble removed).

**Measured:**
- Family separation: 601.2 mean pairwise cosine 0.90 -> 0.63, max 0.994 -> 0.83.
- Whole-corpus audit: 2,882 rule chunks -> 1,138 changed (redundant parent
  dropped), 1,744 identical (900 no-parent + 844 folded-parent-kept, 0
  accidental). Clean two-way partition; 0 empty embed_text.
- Retrieval recall@5/@10/@20/@50: pure vector 65/81/81/90 -> 68/84/87/90;
  rw1-haiku 68/81/87/90 -> 68/87/90/94. Deterministic base up across the board;
  rw1-haiku up at every depth >=10. 7 of 9 match=all interactions now land ALL
  gold within k=15 (the generator's window).

**The tradeoff (do-not-delegate: reading the failure):** q016 REGRESSED.
Isolated cleanly -- same rewrite string, old text-index vs new embed_text-index:
601.2i rank 16 -> 84 (raw question 271 -> 869). The stripped preamble was a
topical anchor: q016's query ("respond to a cost being paid") matches the
casting-process THEME in the 601.2 preamble, not 601.2i's specific "once the
steps are completed" wording. We split the 601.2 family to help q016, and the
separation is exactly what pushed q016 out of reach.

**Why KEEP anyway (Jon's call):** q016 was rank 16 BEFORE the split -- already a
miss at both recall@5 and the generator's k=15 window. The split moved a
near-miss to a far-miss; it did NOT turn a pass into a fail, because there was
no q016 pass to lose. And 84 is the more honest number: at rank 16 q016 looked
like a retrieval near-win (tempting a k-tune to one question); at 84 it is
unambiguously a MULTI-HOP problem -- a thematic query whose answer is a specific
rule, reachable only by retrieving the casting-process rule and following its
reference to the priority consequence. The broad deterministic gains outweigh
one already-failing edge case.

**Rejected:** a partial-preamble heuristic that keeps some family context to
rescue q016 -- a knob fitted to one question, the exact overfitting avoided
everywhere else in this project. The clean structural rule stands; q016's fix is
multi-hop, deferred.

**What would change my mind:** if multi-hop lands and STILL can't reach 601.2i,
revisit whether 601.2i genuinely needs family context in its embed_text.

---

## 2026-07-21 — q016 gold re-broadened; retrieval-miss != answer-wrong

**What:** q016 gold changed AGAIN, from ["601.2i"] to ["601.2", "601.2g",
"601.2h", "601.2i"] (match=any). This supersedes the earlier single-rule
re-audit.

**Why (Jon, do-not-delegate):** the answer eval revealed the ["601.2i"]-only
gold was too narrow. Run on the shipped config, the generator answered q016
CORRECTLY ("No -- no player receives priority in the middle of casting") while
citing 601.2g + 601.2h, NOT the gold 601.2i. Jon's ruling: 601.2a-h are all
steps of casting one spell (601.2 the parent says "a player follows the steps
listed below, in order"); the caster is mid-process and by definition can't be
responded to. You don't need one specific step -- "if you had enough of them you
can infer the right answer." So any of the casting-process rules grounds it;
match=any over 601.2 + the cited steps is the honest gold.

**The meta-lesson (worth the README):** retrieval-recall and answer-correctness
came apart here. The retrieval eval scored q016 a MISS (601.2i at rank 84,
outside k=15) while the answer was CORRECT and grounded, because the question
has multiple valid rule-paths and recall@k against one gold can't see that.
This is the classic RAG-eval gap, hit for real: a single-gold recall metric
undercounts multi-path questions. The fix isn't a better retriever, it's a
gold set that admits the alternatives -- which also flips q016 to a legitimate
retrieval hit (601.2g/h ARE in top-15).

**What would change my mind:** if a grader finds the casting-step citations
don't actually support the conclusion (reasoning beyond the rules), tighten
back -- but on Jon's reading the steps genuinely establish "casting is an
uninterruptible process."

---

## 2026-07-21 — Groundedness bug: confident answers with empty citations, fixed

**What:** On the shipped config, 3 of 31 answers came back answered=true with
citations=[] (q005, q020, q031) -- a regression from 0 in the original grading.
Two sub-causes: q020/q031 put rule refs inline in the prose ("[903.8]...") but
left the structured citations field empty; q005 answered a correct plain-English
"No" grounded to nothing. Fixed by strengthening the system prompt: every rule
number mentioned anywhere in the answer MUST appear in the citations field, and
answered=true REQUIRES non-empty citations (decline instead of answering blank).

**Why it matters:** the citations field is the entire groundedness signal --
it's what the answer-accuracy eval reads and what makes an answer verifiable. A
confident answer with no citations is exactly the failure the `answered` guard
exists to prevent, leaking back in through the structured-output field rather
than through hallucinated prose. Measured after the fix: empty citations 3 -> 0,
confident-but-uncited 3 -> 0, with zero new spurious declines (the guard didn't
over-correct into refusing answerable questions).

**Caveat:** the prompt change reworded all 31 answers, so a clean "only N
changed" diff isn't possible -- re-grade watches for regressions, same as the
earlier prompt-tuning passes.

**What would change my mind:** if forcing citations starts producing padded or
wrong citations (citing rules the answer didn't really use), loosen to "cite
what you relied on" and accept the occasional inline-only ref.

---

## 2026-07-21 — #3b built: Scryfall enrichment (not routing), verified live

**What:** Card enrichment shipped. `[Card Name]` / `[oracle_id]` tokens in a
question are parsed deterministically, resolved via Scryfall (fuzzy name or
oracleid search), and each card's oracle text + all rulings are injected into
the generator prompt AFTER the retrieved rules, before the question. Rules are
ALWAYS retrieved; cards ADDITIONALLY enrich. No router, no tool-use classifier
-- the `[bracket]` is the signal. Rewriter unchanged (never sees card data).
Implemented by a Sonnet subagent against the approved plan; Opus verified.

**Verified LIVE end-to-end** (not just mocked tests): "if I cast [Dovin's Veto]
while [Dovescape] is on the battlefield, does Dovescape counter it?" -> correct
"No," and crucially it used DOVESCAPE'S RULING (not just oracle text) to add
that the Bird tokens are still created even though the spell can't be countered
-- card-specific knowledge the Comprehensive Rules cannot supply. Both cards
cited by name; multiplayer addressed; Scryfall attribution appended. This is the
combined card+rules case (Jon's whole reason for #3b) working.

**Design calls made during the build (accepted):**
- Cache keyed by the raw `ref` token, not a normalized card name -- mirrors the
  rewrite cache (keyed by input, not output). Cost: "[dovins veto]" and
  "[Dovin's Veto]" cache separately. Acceptable; revisit only if it bites.
- Unresolvable `[tokens]` (typo past fuzzy, made-up name) are silently dropped;
  the rules-only answer still runs. Future nicety: surface "couldn't find card
  X" -- deferred, MVP drops silently.
- Attribution appended whenever any card data was fetched (the `Answer` contract
  has no "card-context-used" field; appending to text was the minimal option).
- TTL = 7 days on the cache (rulings get added over time); `card_no_refresh`
  flag on RulesAgent + `no_refresh` on get_card = the eval-reproducibility
  freeze mode (use any cached entry regardless of age).

**Still deferred (unchanged):** the `@` autocomplete UI (needs a frontend; the
pipeline parses `[brackets]` today), nicknames, bulk corpus, ruling relevance-
filtering (all rulings included for now), and the Jon-authored card+rules eval
set (write it after watching the pipeline run).

**What would change my mind:** if including all rulings bloats context on
cards with many rulings, add relevance-filtering (a mini-retrieval over that
card's rulings) -- but not before an eval shows it's a problem.

---

## 2026-07-21 — Bug: empty structured output CRASHED instead of degrading; max_tokens 4096 -> 8192

**What:** Running the card questions through the generator, two of five crashed
with a pydantic ValidationError ("Invalid JSON: EOF ... input_value=''").
Root cause: claude-sonnet-5's adaptive thinking draws from max_tokens, and on
hard card interactions (more context: oracle text + all rulings + rules)
thinking ate the whole 4096 budget, leaving EMPTY structured output.
`messages.parse()` RAISES on empty content -- it never returns
parsed_output=None -- so the existing `if parsed is None` honest-non-answer
guard never fired and the crash propagated.

**Fix (two parts):** (1) max_tokens 4096 -> 8192 -- enough for the 31 rules-only
questions but not for the heavier card prompts; doubling gives thinking room
AND leaves space for the answer. (2) wrap the parse call in try/except
ValidationError -> return the honest non-answer, so a truncation degrades
gracefully instead of ever being fatal. The None-guard stays as a second net.

**Why it matters:** the 31 rules answers (graded 31/31) never hit this because
they carry less context. Card enrichment exposed it. The bug was latent in the
shipped generator, not new to #3b -- any sufficiently hard rules question could
have tripped it too.

**What would change my mind:** if 8192 still truncates on some inputs, the
answer degrades honestly now (the catch) rather than crashing -- and the real
fix at that point is streaming or a task budget, not an ever-larger max_tokens.

---

## 2026-07-21 — Gold-by-ablation: the RAG rules were redundant on 4 of 5 card questions

**What:** Built evals/ablate_gold.py (plan-card-gold-ablation.md): hold card
data fixed, remove each CITED rule, judge whether the answer still holds
(3 trials, majority), and read gold off what's necessary. Ran it on the 5
TheJudge-derived card questions.

**The finding (important, and a risk to the RAG story):** on c001, c002, c003,
c005 the "sanity" check -- remove ALL cited rules -- HELD: the answer stayed
correct with zero retrieved CR rules. The card oracle text + Scryfall rulings +
the model's own trained knowledge of common interactions (countering, trample/
deathtouch, APNAP) answered them; the rules-RAG added nothing. Only **c004**
(SBA timing vs a spell on the stack -- not in the card text, not something the
model nails reliably) genuinely needed rules.

**Implication (Jon's call, being actioned):** most card questions test the
ENRICHMENT, not the rules-RAG. To demonstrate the RAG doing real work with cards
(the whole point of the project), the card set must lean toward c004-shaped
questions -- ones whose answer ISN'T in the card data. Jon also wants the RULES
retrieval demonstrably relevant, and is pushing rulings toward RAG-relevance
retrieval rather than wholesale dump (separate plan, next).

**c004's gold, determined by ablation (the mixed case that motivated the schema
change):** ALL of [704.3, 120.5, 117.2d] AND ANY ONE of [704.5g, 704.4, 120.6,
302.7]. Notably 704.5g (TheJudge's gold, the "obvious" lethal-damage rule)
tested REPLACEABLE, not required -- several rules convey it.

**Judge model:** Haiku vs sonnet-5 agreed on 104/105 verdicts (99%). Haiku is a
reliable judge here, so the harness switches to Haiku -- the method gets cheap
enough to run on a big crowdsourced card set.

**What would change my mind:** if a larger card set shows Haiku diverging from
sonnet on borderline verdicts, move the judge back to sonnet for the calls that
decide gold.

---

## 2026-07-21 — match field extended to "groups" (AND of ORs)

**What:** EvalQuestion.match gains a third mode, "groups", backed by a new
`gold_groups: list[list[str]]`. A hit iff every OR-group has a member in top-k.
any/all are the two degenerate cases (one big OR-group; N one-member groups),
so hit_at derives groups from match and existing any/all questions score
byte-identically -- verified with a synthetic truth-table over any/all/groups.

**Why:** ablation found real MIXED gold (c004: all of X + any of Y) that a single
any/all flag can't express. Rather than a c004-specific hack, "groups" is the
general form that subsumes both -- and Jon expects more mixed cases as the card
set grows, so the general model earns its keep.

**What would change my mind:** nothing foreseeable -- AND-of-ORs is the general
form of "which rules must be retrievable"; anything more exotic (e.g. "at least
2 of N") would be a rare enough case to handle then.

---

## 2026-07-21 — Card eval expanded 5->14; curation driven by the ruling-count data

**What:** Added 9 Jon-authored card questions (c006-c014) to evals/cards.jsonl.
Eight are rulings-RAG cases (each hinges on a specific load-bearing RULING, not a
CR rule): c006 Fork/buyback, c007 Mimic Vat/manifested-nonpermanent, c008
Lithoform Engine/linked-ability, c009 Teferi's Protection/phase-out-Banishing-
Light, c010 Emrakul/counter-the-cast-trigger, c011 Valki//Tibalt/cascade-mana-
value, c012 Emrakul+Lithoform+Voltaic Key (multi-card combo), c013 Mimic
Vat+Lithoform (copy-on-copy). One is a rules-warper (rules-RAG): c014
Trinisphere+Awaken the Woods. Gold is left EMPTY on all nine, pending ablation;
each carries a `note` naming the load-bearing ruling (the future rulings-recall
gold) and the expected conclusion.

**How the pool was chosen (the data, not memory):** pulled Scryfall's rulings
bulk file and found (a) rules-warpers Jon expected to be ruling-heavy are actually
ruling-LIGHT (Trinisphere 2, Humility 3, Blood Moon 4) -- their warping lives in
the CR, so they're rules-RAG cases; (b) the true high-ruling cards are new-keyword
mechanic cards (Rooms/manifest/battles, mostly shared boilerplate) plus complex
singletons. Deduping ruling text shared across cards surfaced the cards with the
most CARD-SPECIFIC rulings (Teferi's Protection, Fork, Mimic Vat, Lithoform
Engine, Emrakul, Valki, ...), which is the rulings-RAG pool. See LOG.md.

**Why this set:** the rulings-on-demand spike showed the old 5-question set was a
thin testbed -- 4 of 5 referenced cards had ZERO rulings, and the 1 that did (c003)
was answerable from rules anyway. These 9 give a real testbed where a specific
ruling is load-bearing (so the mini-RAG has selection work AND its recall is
measurable), plus one rules-warper to keep the rules-RAG exercised. Several are
"the ruling overrides the naive rule reading" cases (Emrakul c010, Valki c011,
Trinisphere c014), the strongest demonstration that grounding on rulings beats the
model's training guess.

**What would change my mind:** if ablation shows some of these are ALSO
over-determined (rules OR rulings each sufficient, like c003), keep them as
rulings-recall / faithfulness tests but don't count them as rules-RAG tests --
same honest bookkeeping as c001-c003.

---

## 2026-07-21 — Card enrichment: layout-first, all printed rules-relevant fields

**What:** The generator enrichment (`_format_cards`) dropped everything but name
+ oracle text + rulings. Rebuilt it to include, PER FACE, mana cost, mana value,
type line, power/toughness, loyalty, defense, colors, color indicator, plus
whole-card layout and color identity. `_card_from_json` now reads `layout` and
`card_faces` FIRST (Jon's architecture call), then builds one `CardFace` per
printed face -- so a modal DFC's two faces each keep their own cost/type. New
`CardFace` submodel; `Card` gains `layout`, `mana_value`, `colors`,
`color_identity`, `faces`. Cache versioned (schema 2) so old-schema entries
auto-refetch. Plan: docs/plan-card-enrichment-fields.md.

**Why:** two baseline misses were pure enrichment gaps. c014 (Trinisphere): the
model guessed Awaken the Woods = {X}{G}{G}{G} (it's {X}{G}{G}) because the cost was
never in the prompt. c011 (Valki//Tibalt): the model invented a "cast it
transformed" restriction because nothing told it the card is a MODAL DFC. Both
are the exact failure the project targets -- relying on training for a printed
fact.

**Result (measured, re-ran all 9):** both misses fixed. c014 now picks X=2 as
best value with the real cost. c011 now IDs the modal DFC correctly AND -- the big
one -- retrieved cascade rule 702.85a and applied its resulting-mana-value clause
to conclude you CANNOT cast Tibalt off a normal cascade. That is the grounded-
CORRECT answer, and it OVERTURNED what both Jon and I confidently believed (the
pre-errata "cast Tibalt for free"). The RAG checked its own builders. The other 6
stayed correct; c006 truncated to an honest non-answer (see max_tokens below).

**Two honesty notes captured in the same slice:** (1) I justified taking
Scryfall's color_identity with a FALSE claim ("Extort's {W/B} makes a colorless
card W/B") -- color identity ignores reminder text, so it doesn't; Blind Obedience
is mono-W, Crypt Ghast mono-B. Fixed the comment; the code (take Scryfall's value)
was already right. (2) See c011 above. Both are model-memory hallucinations caught
by grounding -- README material, and the reason color identity is taken from
Scryfall rather than derived.

**max_tokens 8192 -> 16384 (generator + ablation):** Jon's call. c006 truncated
once the richer enrichment enlarged the prompt (sonnet-5's adaptive thinking ate
the budget -> empty structured output -> honest non-answer via the ValidationError
catch). Raising the cap is nearly free (you pay for tokens produced, not the
ceiling). Supersedes the earlier "don't just raise max_tokens" lean for this
eval-scale use; streaming / a task budget remains the proper fix if 16384 ever
isn't enough.

**What would change my mind:** if per-face MV (read off the shown cost) ever needs
to be an explicit computed field, add it; if 16384 still truncates, move to
streaming rather than raising again.

---

## 2026-07-21 — Rulings on demand: relevance-selected per-card ruling mini-RAG (BUILT + verified)

**What:** Replaced the wholesale ruling dump with a per-card mini-RAG
(`tools/ruling_retrieval.py`): embed a referenced card's own rulings
(voyage-4-large), keep the top-3 whose cosine to the stripped question clears a
0.38 floor, inject only those. Withhold by default (nothing relevant -> nothing
included). Wired into RulesAgent (`ruling_select=True`; False = old dump for
A/B). Ruling ids are `oracle_id#index`; embeddings cached/frozen. Plan +
decisions: docs/plan-rulings-on-demand.md.

**Why this shape (Jon's grounding call):** confidence-gating (withhold until the
model says it can't answer) was rejected -- it's the design that lets the model
lean on training whenever it feels sure, the exact thing to avoid. The need-signal
comes from the corpus (relevance), not the model's confidence, so the mini-RAG
always runs and includes any relevant ruling.

**Measured (19-question card eval, mini-RAG vs dump-all):**
- Floor calibrated on real cosines: load-bearing ruling lands rank-1/top-3 on
  12/15 ruling-bearing questions (0.41-0.66). Set floor 0.38 + top-3 cap.
- **Answer quality HELD**: every question correct under dump-all stayed correct
  with <=3 relevant rulings instead of the full list -- while cutting ruling
  context hard (c009 35->6, c011 22->3, c010 18->3). The RAG does measurable
  selection work with no correctness cost.
- Honest ceiling: 3 questions (c010/c011/c019) have their specific load-bearing
  ruling phrased too differently from the question for relevance to reach it;
  answers held anyway via the rules-RAG + other rulings. Same class as the q016
  multi-hop gap.

**Deferred / not done:** the "cite the ruling by id" step (rulings-recall is
measured off `last_ruling_selection` instead for now); the rewrite-as-ruling-query
arm; the global rulings corpus (the per-card mini-RAG is the chosen long-term
path). c018 truncates reproducibly (generation runaway, both configs) and c015 is
a faithfulness gap (right ruling selected, not applied) -- both open, neither a
retrieval fault.

**What would change my mind:** if a larger card set shows the top-3 cap dropping
load-bearing rulings that DO match the question (not the semantic-mismatch cases),
raise N; if answer quality ever drops vs dump, revisit the floor.

---

## 2026-07-22 — Backend API (FastAPI), v1 for the frontend

**What:** Built `src/rulesagent/api/main.py` -- a thin FastAPI wrapper over
`RulesAgent` so Jon's Claude-Design frontend can call the engine. `POST /answer`
returns an ENRICHED response (cited rule/glossary text resolved via a chunk_map,
the card data + mini-RAG-selected rulings used, and an optional debug panel:
rewrites / retrieved rule ids / selected ruling ids). `GET /cards/autocomplete`
proxies Scryfall for the @-picker. `GET /health`. `RulesAgent` gained
`last_cards` / `last_retrieved` recorders to feed the response. Plan +
decisions: docs/plan-api.md.

**Key calls (Jon):** enriched response (frontend renders rule text + cards);
**private demo** so no auth/rate-limiting in v1; **card images pulled by the
frontend from Scryfall** using the name/oracle_id the API returns (no backend
image field, no cache-schema bump); **autocomplete built now** (nobody
hand-types card names right); **non-streaming v1**; **single worker + a lock**
serializing `/answer` so the whole-file caches can't clobber under concurrency.

**Verified live:** all three endpoints answered correctly against a running
server -- `/answer` on a `[Fork]` buyback question returned the right answer with
resolved rule-text citations, Fork's card data + 3 selected rulings, and the
debug panel; autocomplete returned live Scryfall suggestions.

**What would change my mind / deferred:** the atomic-per-key cache fix is
required before real concurrency (more than the single locked worker); token
streaming if the frontend wants it; `image_uri` in the response if the frontend
would rather not round-trip to Scryfall (a small cache-schema bump).

---

## 2026-07-22 — Outside judge: gpt-5-mini adopted (95% agreement with sonnet-5)

**What:** Validated three non-Claude judges for the eval/ablation harness via
OpenRouter (pinned slugs, allow_fallbacks=false) on evals/judge_pairs.jsonl --
22 same-question answer pairs drawn from this session's real pipeline runs,
seeded with known conclusion-flips so both verdict classes exist (sonnet: 17
same / 5 different). Harness: evals/judge_bakeoff.py; raw verdicts in
evals/judge_bakeoff_results.json. **Adopting openai/gpt-5-mini** as the
outside judge.

**Measured (agreement with claude-sonnet-5, pre-registered bar >=95% -- the
bar Haiku cleared at 94-99%):**
- haiku (incumbent): 21/22 = 95%
- **gpt-5-mini: 21/22 = 95%** -- identical miss-profile to Haiku
- deepseek-v3.2: 20/22 = 91%
- gemini-2.5-flash-lite: 20/22 = 91%

**Reading the misses (the interesting part):** the one pair EVERY judge except
sonnet missed (c006:enr-vs-mini) is degenerate-by-construction -- the
"reference" side is a truncation notice, inverting the rubric's assumption that
the reference is a real answer; sonnet alone applied the rubric strictly.
Excluding it: haiku and gpt-5-mini 21/21, deepseek/gemini 20/21. What actually
separated the field is c015 (confident-wrong "aura stays attached" vs honest
"can't confirm" hedge): sonnet, haiku, and gpt-5-mini all called it DIFFERENT
(right -- the bottom lines diverge materially); deepseek and gemini called it
same. That's a discrimination failure on exactly the class we care about.

**Why gpt-5-mini over the other passers:** it ties the incumbent on the full
set, discriminates the confident-wrong-vs-hedge case correctly, and maximizes
the independence argument -- an OpenAI judge scoring Claude-generated answers
removes same-family bias from the eval story. Cost ~$0.25/$2.00 per M; judge
calls are tiny, effectively free.

**What would change my mind:** n=22 is a screen, not a proof -- if gpt-5-mini
diverges from sonnet on borderline verdicts once used at scale, or a larger
pair set shows drift, re-run the bake-off (the harness is committed and
re-runnable). Borderline verdicts still go to Jon regardless of judge.

---

## 2026-07-22 — One-key config via OpenRouter embeddings: rejected

**What:** Jon asked whether the Voyage embeddings could run through the
OpenRouter key (already in .env for the upcoming outside-judge work) so a
fresh user configures one key instead of three.
**Checked (live, not memory):** OpenRouter does now expose an /embeddings
endpoint — but its 27-model catalog (OpenAI, Google, Qwen, Mistral, BGE,
E5, ...) contains NO Voyage models.
**Why rejected:** routing embeddings through OpenRouter therefore means
switching MODELS, not keys. voyage-4-large is pinned; it won the measured
A/B (recall@5 65% vs voyage-4's 55% vs BM25's 32%) and every retrieval
number since is built on it. A model swap invalidates the entire measured
ladder and forces a corpus re-embed + full eval re-run — a research
project, not a config simplification. Voyage's free tier covers the corpus,
so the second key costs a signup, not money.
**What would change my mind:** Voyage appearing in OpenRouter's embeddings
catalog (then it IS just a key swap — re-verify identical vectors before
believing it), or a deliberate cross-embedding-model A/B done on its own
merits as a README result.

---

## 2026-07-22 — RulesGuru import: 150 external questions with human gold

**What:** Imported 150 judge-curated questions from RulesGuru's public API
(30 per level, 0-3 + Corner Case) into evals/rulesguru.jsonl as a separate
eval set with human-written gold answers AND cited-rule gold — never merged
into the hand-curated questions.jsonl/cards.jsonl. Answers auto-judged by
gpt-5-mini against RulesGuru's answerSimple; the judge (never the bot) gets
the site's player-naming-convention note. Fetched data committed to the repo.
Full plan: docs/plan-rulesguru-import.md.
**Alternatives considered:** 30-60 hard-only questions (cheaper per run);
hand-grading first to calibrate judge trust; gitignoring the fetched data
and fetching on demand; picking one match semantic for recall.
**Why:** The card-gold ablation showed most card questions were answerable
from priors + oracle text — weak RAG tests with empty rules-gold. RulesGuru's
harder tiers arrive with verified citations attached, fixing that for free.
Full spread over hard-only because Jon wanted the difficulty curve visible.
Committing the data because reproducible evals beat a live third-party
dependency. And rather than choosing any-vs-all recall semantics, both are
scored in one pass (--match-both; same top-k, only the hit rule differs) —
Jon's call, and it paid off immediately: a ~2.5x any/all gap (40% vs 16%
best-arm any@5/all@5), far wider than on the hand-curated set, because
RulesGuru cites everything the answer leaned on, not a minimal set.
**What would change my mind:** RulesGuru objecting to committed data (script
regenerates everything, files can drop from the repo); judge spot-checks
showing gpt-5-mini misgrades scenario questions (fall back to hand-grading
via the review UI); ablation showing imported citation-gold is too noisy to
trust for recall (then ablate per-question minimal sets instead).

## 2026-07-22 — Feature shortlist for the public demo

**What:** From a researched candidate list, picked: clarify-then-escalate
(ask the user for context on answered:false BEFORE showing an "ask a real
judge" link), legality chip on discussed cards, misconceptions example
gallery, shareable answer permalinks (post-L3), an "undefined in the CR"
flag, and a donate link. Full list + evidence: docs/feature-ideas.md.
**Alternatives considered:** quiz/practice mode, decklist upload, IPG/MTR
corpora, Commander mode, numeric confidence indicator, CR-version line,
multi-source ruling aggregation, CR version diffing.
**Why:** Ranked by demo credibility per unit of effort. The picks either
reuse machinery we have (Scryfall legalities, the rewriter's clarification
output, L3's answer storage) or harden the project's core story — grounded
honesty over confident guessing. The clarify-first refinement is Jon's:
escalation to a human should be the third rung, not the second.
**What would change my mind:** Real public-demo traffic. If actual users
show up post-deploy, quiz mode and Commander support are the first two to
revisit — they serve users more than they serve the portfolio.

## 2026-07-22 — c004 flipped to correct-with-note (rubric call on undisclosed assumptions)

**What:** Jon ruled the two c004 "partial" verdicts (sonnet-v2 and
deepseek-v4-pro — identical answers per the transitive judge, one grading
note transferred) flip to **correct**, with his original grading note
retained verbatim in the verdict files plus a ruling tag. New baselines for
the prompt-v3 A/B: **sonnet-v2 46/50, deepseek-v4-pro 44/50** (verified by
count after the edit). The other three arms' c004 verdicts (v4-flash,
gemini-flash-lite, gpt-5-mini — all auto-transferred **wrong** vs the
deepseek-v3.2 reference, a different answer cluster with a substantive
SBA-sequencing error) are untouched and stay wrong.
**Alternatives considered:** Keep them partial — Jon's first lean, briefly
recorded here before he reversed it the same session. The case: it preserved
the F5 signal behind prompt-plan §1d and kept that bullet's predicted
c004 flips falsifiable in the A/B.
**Why:** Jon's grading note opens "correct but..." — the answers were right
under the natural reading of the question, and the eval question itself
omits when the damage was marked, so the undisclosed ambiguity is as much
the question's fault as the answer's. Rubric meaning going forward:
*a correct answer that silently assumes away an ambiguity the asker didn't
resolve grades correct-with-note, not partial* — the disclosure bar belongs
to the clarify-then-escalate feature (shortlist #1), not to the correctness
verdict.
**Consequences for the prompt-v3 A/B:** the go/no-go baseline for the
incumbent is now 46/50 (any net drop from 46 = no-go); §1d's two predicted
c004 partial→correct flips are off the board (already correct), so the
"half of predicted flips land" denominator shrinks accordingly — §1d is now
justified by disclosure quality (and the lower-confidence v3.2:c004), not by
count movement on these two arms.
**What would change my mind:** Inconsistency elsewhere in the 300-cell grid
(a same-shaped undisclosed-assumption answer still graded partial) — then
that verdict should move to match this rubric. Also revisit once
clarify-then-escalate ships: if "disclose or ask" becomes the enforced norm,
non-disclosure may re-enter the verdict as partial again.

## 2026-07-23 — v3 A/B outcome calls (after Jon graded the 144-row queue)

Graded rollup (correct/50, r1/r2; strict, partial=not-correct), best condition:
sonnet 46 (flat, 0 flips) · gpt-5-mini 45 (+3, cond C) · v4-pro 45 (+1, cond B)
· v4-flash 44 (+2, cond C) · v3-2 43 (flat) · gemini 37 (regressed from 38).

- **v3: GO, adopted as the INTERIM production prompt, prompt-v4 to supersede.**
  Gate 1 clear (sonnet untouched), 3/5 cheap arms up (meets the go criterion).
  Mixed as predicted: helped mid-tier reasoners (gpt-5-mini +3), overloaded the
  weakest (gemini -1 to -4). Jon's call: adopt now, but the c014 mana-notation
  failures v3 did NOT fix make a prompt-v4 clearly next.
- **Part B ruling-query union: DOES NOT SHIP** (Jon's pre-commit rule D>=C
  failed). Condition D was worse than C on the best arms (gpt-5-mini 45->43,
  v4-flash down), better only on gemini. The retrieval-level win (+4 rulings,
  0 regressions) did not reach generation and actively hurt the lead arm.
  Union stays available behind its flag, OFF by default.
- **L2 generator: gpt-5-mini is the lead candidate; switch DEFERRED until
  prompt-v4 + reasoning-enabled (condition-E) are tested** (Jon's call, on the
  accurate 45/50 vs sonnet 46/50 numbers — he'd misread it as a 100% tie).
  Rationale: gpt-5-mini's own c014 mana errors and the reasoning-off runs mean
  v4/reasoning could push it to 46+, making the switch zero-compromise instead
  of a 1-answer concession. Sonnet stays production ~1-2 experiment cycles. If
  gpt-5-mini then matches/beats 46, switch via a Rule 0 config plan (GEN_MODEL
  -> gpt-5-mini via OpenRouter; reliability/latency notes).
- **2 ungraded rows** (gemini-flash-lite B_r2: c006, c014) still need Jon's
  verdict; gemini's exact count is provisional until then.

## 2026-07-23 — Four pre-commitments while grading the v3 A/B queue

**What:** Jon set decision rules before seeing his own graded numbers (grading
was in progress), so the rules can't be bent to fit the results:
1. **Groundedness tripwire: signed off, not a no-go** — 5 questions / 7
   instances / <1%, scattered, not the 1c-multiplayer spike the rule was
   written for. PLUS a follow-up slice queued: read the 7 answers,
   determine whether a prompt tweak or a post-hoc citation filter could
   zero them out (mini-plan needed, Rule 0).
2. **Part B union ships if D ≥ C on graded correct-counts** (retrieval-level
   already proven: +4 load-bearing rulings, 0 regressions). Watch item: if
   D < C specifically on deepseek-v4-pro (its 13 unstable D-flips), discuss
   instead of auto-shipping.
3. **L2 generator decided from the v3 table:** best cheap arm within 1-2
   correct of sonnet's 46 → Jon reviews the actual flipped answers and
   decides if the gap is livable at ~5-8x cheaper (MEASURED 2026-07-23 from
   real OpenRouter usage: gpt-5-mini ~$0.0059/query vs sonnet ~$0.048 std /
   ~$0.032 intro — the earlier "25-50x" was vs the reasoning-OFF deepseek
   arms, not gpt-5-mini which reasons); gap ≥3 → sonnet stays
   pinned. Final call Jon's either way.
4. **SSO timing: OIDC slice next** (after the v3/Part B/L2 calls settle,
   ahead of local-bulk and deploy; localhost callbacks). SAML + Jon-driven
   breakage lab after L5 deploy when real URLs exist.
**Why:** Pre-committing decision rules before data arrives is the same
discipline as the frozen judge — it keeps the experimenter honest. SSO
ordering favors resume timing (Jon is actively applying) at zero technical
cost since OIDC needs no deployed URL.
**What would change my mind:** Grading results that surprise in a way the
rules didn't anticipate (e.g., D ≥ C overall but a quality cliff visible in
the flipped answers themselves) — the rules route the default, Jon can
always override with reasons on the record.

## 2026-07-23 — Scryfall data licensing: signed off for the public deploy

**What:** Jon reviewed Scryfall's API usage policy (the Wizards Fan Content
Policy pass-through: no "simply repackag[ing], republish[ing], or proxy[ing]"
— software "must create additional value for end-users") and ruled Rulemancer
compliant for the future public Fly.io deploy that will carry the local bulk
snapshot (docs/plan-scryfall-local-bulk.md).
**Why (Jon's words):** "we aren't just serving their data, we're using it as
a reference source to answer questions directly, which their site doesn't do
— that's additional value for sure."
**Alternatives considered:** deferring the call to the deploy slice (the
plan's original checkpoint design); seeking an outside/legal opinion
(disproportionate for a fan project under the Fan Content Policy).
**What would change my mind:** Scryfall revising their policy wording;
Scryfall or Wizards objecting directly; the product's shape changing into
something closer to a card-database mirror (e.g., a card-lookup feature that
just re-serves oracle text without the rules-answering layer).

## 2026-07-24 — prompt-v4 and condition-E ship as ONE slice, measured by SYSTEM-swap

**What:** v4 and the reasoning-effort experiment run on a single grid (sonnet/v4,
gpt-5-mini/v4 default, gpt-5-mini/v4 effort=high; 2 runs each) and are graded in
one session. The v4 arm's prompts are NOT freshly captured — they're derived from
`evals/answers/_prompts_C.json` by replacing the `system` field and copying every
`user` block byte for byte. Plan: docs/plan-v4e-execution-tasks.md.
**Why:** Jon's grading time is the binding constraint, and condition-E's
attribution is only clean if the prompt is fixed across its cells — so merging
them costs nothing and saves a whole grading session. The swap works because the
prompt cache stores `system` and `user` separately and v4 is a SYSTEM-string-only
change (plan-prompt-v4.md §8): v3 and v4 then answer from *byte-identical*
retrieval, which eliminates the 30-34% Voyage embedding nondeterminism from the
comparison instead of merely controlling for it. It also means the v3 baselines
(sonnet 46 / gpt-5-mini 45, condition C) need no re-run — six new runs, not twelve.
**Alternatives rejected:** a fresh `_capture_prompt` pass for v4 (what
plan-prompt-v4.md §5/§6 originally described) — closer to the letter of the v3
methodology but re-draws retrieval, making some flips unattributable; running
condition-E separately after v4 (a second grading session for one extra variable);
adding a generation-side SYSTEM version selector (unnecessary — v3 survives inside
the frozen capture file).
**What would change my mind:** evidence that v4 changes anything upstream of the
SYSTEM string (it doesn't, by its own non-goals), or a per-question byte-equality
failure in the derived prompts file — which is exactly what the plan's Task 3
verification checks and reports.

## 2026-07-24 — condition E (reasoning effort) FAILS ON LATENCY, before accuracy matters

**What:** The `effort=high` arm of condition E was killed mid-run and will not be
graded. Jon's call, on measured latency. The two `gpt-5-mini` default runs and
both sonnet runs stand; the v4 A/B proceeds without a high-effort cell.

**The measurement (single request, q001, no contention — the smoke tests):**
sonnet **9.3s** · gpt-5-mini default **16.0s** · gpt-5-mini `effort=high`
**69.7s**. Under three concurrent eval runs the high arm degraded further to
87-110s/question. Reasoning tokens on the same question: 1,152 default vs
**7,424** at high effort — the flag is definitely effective, it just costs ~7x
the incumbent's wall clock.

**Why this kills it before grading:** Jon's product judgment — "we definitely
can't be waiting an average of 87 seconds for an answer, users will hate that."
Decisive technical detail: **streaming cannot rescue this.** The L5 deploy plan's
answer to slow answers is SSE token streaming, but a reasoning model emits ZERO
output tokens while reasoning (7,424 of 7,839 completion tokens were reasoning).
A visitor would watch a blank screen for ~60s and then get a burst. Streaming
masks generation latency; it cannot mask reasoning latency. So an arm that can't
ship on latency can't change the L2 generator decision no matter what it scores,
and grading its flips would spend Jon's scarcest resource on an unusable option.

**Consequence for the deferred L2 call:** it now rests entirely on the DEFAULT
gpt-5-mini cell vs sonnet — which is the comparison we have. Condition E's
recorded result is a latency verdict, not an accuracy one: raising reasoning
effort is off the table for this product.

**Alternatives rejected:** letting r1 finish for the writeup (~60 min more for
evidence that couldn't be decision-grade anyway — one run can't satisfy the
stable-flip rule); testing `medium` effort instead (same latency class, same
streaming problem); accepting the latency for a "quality mode" toggle (no such
product surface exists, and it would need its own plan).

**What would change my mind:** a reasoning model that streams interim output, or
a deployment where answers are precomputed/async rather than interactive.

## 2026-07-24 — groundedness follow-up does NOT enter prompt v4

**What:** Jon read the 7 flagged groundedness instances and ruled v4 ships exactly
as its six rulings specify — no groundedness-targeted bullet. The post-hoc
citation-filter option stays queued as its own Rule 0 slice; pre-commitment #1
(2026-07-23) is partially discharged, not dropped.
**Why:** the evidence didn't support spending v4's prompt-change window on it.
Only 4 of the 7 belong to arms still in the decision set, and they aren't one
failure class: gpt-5-mini's q028 ×2 cited `601.2` when `601.2a/601.2f/601.2i` WERE
in context (parent-vs-child granularity); sonnet's c016 cited `904.6d` alongside a
real, in-context `704.6d` (one digit apart); sonnet's q012 appended `701.21` to a
claim already grounded in the provided `Sacrifice` glossary entry. The only
whole-cloth ungrounded citations (gemini's `702.7`/`702.4`, stable across both
runs) belong to a dropped arm.
**Alternatives rejected:** folding a bullet into v4 anyway (would aim a prompt fix
at what looks partly like a citation-granularity artifact, and adds an unruled
bullet to a fully-ruled plan); blocking v4 until a citation-filter plan exists.
**What would change my mind:** the v4 run's tripwire spiking above the current
level, or Jon's grading turning up an ungrounded citation that actually changed an
answer's correctness rather than just its citation list.
