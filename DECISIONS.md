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
