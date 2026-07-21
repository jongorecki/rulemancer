# MTG Rules Agent — Build Plan

## The constraint that shapes everything

Capgemini's AI practice lead has read your resume and is expected to reach out
within ~1–2 weeks. You are already through the door. This project is not what
gets you the conversation — it's what you *talk about* during it.

**Therefore: articulation beats polish.** He will not clone your repo. He will
ask why you chunked it that way, how you know retrieval works, and what it costs
per query. Optimize for being able to answer those cold.

Secondary payoff: this is also AI-103 retake prep. The exam covers knowledge
grounding, RAG, agents/tools, and evaluation (groundedness, coherence, F1) —
the same material, made concrete.

---

## Links

**Comprehensive Rules**
- Official download page (always current, TXT/PDF/DOCX):
  https://magic.wizards.com/en/rules
- Direct TXT, Feb 27 2026 revision — check the page above for anything newer:
  https://media.wizards.com/2026/downloads/MagicCompRules%2020260227.txt
- Hyperlinked browsable version (good for *reading*, not for parsing):
  https://yawgatog.com/resources/magic-rules/

Grab the **TXT**, not the PDF. The PDF adds layout noise you'd have to strip.
As of April 2026 the document runs ~308 pages.

**Model access**
- Moonshot / Kimi platform: https://platform.kimi.ai
- Kimi K3 quickstart docs: https://platform.kimi.ai/docs/guide/kimi-k3-quickstart
- OpenRouter: https://openrouter.ai
- OpenRouter K3 model page: https://openrouter.ai/moonshotai/kimi-k3
- Auto Router (read, then don't use — see below): https://openrouter.ai/openrouter/auto

**Reference**
- AI-103 study guide:
  https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/ai-103
- Scryfall API docs: https://scryfall.com/docs/api
- OpenCode: https://opencode.ai

---

## Tonight (15 minutes, phone is fine)

- [ ] Create an OpenRouter account and load ~$20 of credit — https://openrouter.ai
- [ ] Download the Comprehensive Rules TXT to the laptop (link above)
- [ ] Check your Microsoft cert dashboard for the AI-103 retake waiting period
      (don't rebook — just find out the window)
- [ ] Text your buddy: nothing pushy, just keep the channel warm

Do **not** install anything tonight. Sleep.

---

## Tomorrow morning — setup (target: 90 minutes, hard stop)

If setup runs past 90 minutes, stop and start parsing anyway. Environment
perfection is the most common way this kind of project dies on day one.

1. `git init mtg-rules-agent`, Python 3.12, `uv` for deps
2. Install OpenCode; configure both Moonshot and Anthropic keys
3. Create the skeleton (empty files are fine):

```
mtg-rules-agent/
  DESIGN.md
  DECISIONS.md
  LOG.md
  Makefile
  pyproject.toml
  src/rulesagent/
    contracts.py
    ingest/       parser.py  chunker.py
    index/        embed.py   bm25.py   store.py
    retrieve/     hybrid.py  rerank.py
    generate/     answer.py
    tools/        scryfall.py
    api/          main.py
  evals/          questions.jsonl  run_eval.py
  tests/
  data/raw/       (CR txt lives here, gitignored)
```

4. Paste this document into `DESIGN.md` as the starting point
5. First commit before any model touches anything

---

## Day 1 work — the parser

**You write `contracts.py` by hand.** It's ~30 lines and it's the seam every
model works against. Roughly:

```python
class Rule(BaseModel):
    number: str            # "104.3a"
    text: str
    parent_chain: list[str]  # ["104", "104.3"]
    section: str           # "Game Concepts"
    kind: Literal["rule", "subrule", "glossary"]
    examples: list[str]
```

Then specify the parser to a model rather than accepting whatever it writes.
Edge cases it must handle:

- Section headers (`1. Game Concepts`) vs rules (`104.3a`)
- Subrules — letter suffixes nest under their numbered parent
- `Example:` blocks that trail a rule and belong to it
- The Glossary — different format entirely (term, then definition)
- Cross-references (`see rule 704`) — preserve as text for now, don't resolve
- Credits section at the end — exclude
- Leading/trailing whitespace and the file's line-wrapping

**Output:** `data/parsed/rules.jsonl`, one record per rule.

### Then the measurement that drives tomorrow's decision

Before choosing a chunking strategy, count:

1. Total rules parsed (sanity check — should be several thousand)
2. Word-count distribution across rules
3. **How many rules are under ~30 words** ← the number that matters
4. How many glossary entries
5. How many rules have `Example:` blocks

If most rules are short fragments, one-rule-per-chunk will fail and you'll need
to roll parent context into each chunk. Decide from your data, not from advice.

### Golden tests before you move on

Hand-pick ~20 rules covering the weird cases above. Assert the exact expected
parse. Now any model can rewrite the parser and you'll know instantly if it broke.

---

## The 14-day arc

| Days | Work | Done when |
|---|---|---|
| 1–2 | Parse + chunk the CR | Golden tests pass; length counts in hand |
| 3–5 | Eval harness, then retrieval tuning | recall@5 measured for BM25 / vector / hybrid / +rerank |
| 6–9 | Generation w/ citations, Scryfall tool, low-confidence path | Answer accuracy measured separately from retrieval |
| 10–14 | Public repo, README w/ numbers, cheap deployed demo | A stranger can run it in one command |

**Stretch, only if 1–9 land clean:** Azure AI Search parallel build, second
corpus to prove domain-independence, MCP server.

**If you slip:** cut the deployed demo before you cut the eval numbers. A repo
with measured retrieval metrics beats a live demo with none.

---

## Pinned stack (decide now, don't let a model drift)

| Layer | Choice | Why |
|---|---|---|
| Parsing | stdlib `re` | No dependency needed |
| Embeddings | API (Voyage / OpenAI / Cohere) | Indexing the CR costs cents |
| Vector store | **NumPy array + pickle** | ~5k rules ≈ 30MB; brute force is milliseconds |
| Keyword | `rank_bm25` | Simple, adequate |
| Rerank | Cohere Rerank API or local cross-encoder | Stage two only |
| API | FastAPI | |
| Deps | `uv` | |

**No vector database.** Measure that brute force is fast enough at this corpus
size and skip the dependency. This is a stronger interview answer than standing
one up reflexively — it shows you sized the problem.

**No home server. No 3060 Ti. No Activepieces.** All of that is September.
Building infrastructure right now is procrastination that feels like progress.

---

## Working rules

1. **Explain-back rule.** Don't merge anything you can't explain in three
   sentences. Tests passing is necessary, not sufficient.
2. **Whoever writes doesn't review.** Rotate models on review. The author's
   context is exactly what blinds it.
3. **DECISIONS.md as you go.** Every non-obvious choice: what, alternatives
   rejected, why, what would change your mind. 5–10 lines. This *is* your
   interview prep — reconstructing it later produces something hollow.
4. **One slice per branch.** Commit per slice so you can revert cleanly.
5. **The repo is the coordination layer.** Models coordinate through git,
   tests, and DESIGN.md — not through each other.

### Model access: OpenRouter, with models pinned

Use OpenRouter as the key and billing layer. One account, one key, 300+ models
across 60+ providers, OpenAI-compatible so OpenCode and every SDK just work by
swapping the base URL. For a project where you explicitly want to try several
models, this is the right abstraction — and it removes the "sign up for another
provider" friction every time you want to test one.

**But pin the model explicitly on every call. Do not use the Auto Router.**

Two separate reasons, and the second is non-negotiable:

1. *For coding* — Auto Router classifies your prompt and routes to the most
   popular model for that task by aggregate spend. That's a popularity
   heuristic, not a quality judgment about your task. And it makes results
   non-attributable: you won't know whether K3 or something else wrote the code
   you're about to review, which defeats the whole point of rotating reviewers.

2. *For the agent's own generation* — **you cannot evaluate a RAG system whose
   generation model changes underneath you.** If the model varies between eval
   runs, your accuracy numbers mean nothing and regressions become
   unattributable. Eval reproducibility requires a pinned model. Full stop.

The upside OpenRouter *does* unlock: once retrieval is fixed and the eval
harness works, swapping generation models is a one-line change. Holding
retrieval constant and reporting answer accuracy across four generation models
is a genuinely strong result to put in the README — and it's exactly the kind
of build-vs-buy evidence a consultancy cares about.

Note `allow_fallbacks` defaults to true. For eval runs, set it false so a
silent failover doesn't corrupt your numbers.

### Model assignment

- **K3** (`moonshotai/kimi-k3`) — multi-file implementation; 1M context holds
  the whole repo
- **K2.7 Code** — mechanical bulk work, cheaper
- **Opus / Claude Code** — design conversations, diff review, debugging weird
  retrieval behavior
- Parallel work via `git worktree` only where modules are genuinely
  independent (ingest vs. eval harness qualifies; most pairs don't)

> **Status note (2026-07-21):** Starting with Claude Code only. OpenCode /
> OpenRouter model rotation (K3, K2.7 Code) is deferred until Jon sets that up
> separately — see DECISIONS.md.

---

## Content capture (do this from hour one)

The goal is a pipeline of dev docs, support docs, LinkedIn posts, Reddit posts,
and a writeup — all derived from material captured *during* the build, in your
voice. This is the thing that didn't happen for Cardomancer.

**Hard rule: capture during, publish after.** If content work starts eating
build time, the project fails and there's nothing to write about anyway.
Budget: ~5 minutes a day, total.

### The mechanism

`DECISIONS.md` is already 80% of the content pipeline. Every entry — decision,
alternatives rejected, why, what would change your mind — is a post in raw form.
Write it as you go and the rest is editing.

Add one file, `LOG.md`, for what DECISIONS.md misses:

```markdown
## Day 3 — 2026-07-23

- Assumed one-rule-per-chunk would work. Counted: 62% of rules are under 30
  words. Wrong. Rolling parent context in.
- Vector-only recall@5 came back at 61%. Lower than I expected. Jargon is
  killing it — "lifelink" and "deathtouch" embed near each other.
- Wasted 90 min because the glossary parses differently than the numbered
  rules and I didn't notice until the counts looked wrong.
```

Rules for LOG.md:
- **Under 60 seconds per entry or don't write it.**
- Raw, ugly, unedited. Never clean it up during the build.
- Capture the three things that make content good and get forgotten fastest:
  **failures, surprises, and numbers.**
- Screenshot terminal output whenever a number changes meaningfully.

Write real commit messages too. Git history is a free timeline.

### Making capture automatic

You should never have to remember to do this. Two layers, because
**standing instructions to agents decay over long sessions** — a "remember to
ask" line gets honored on day one and forgotten by day six. Mechanical
triggers don't decay. Put the important captures there.

#### Layer 1 — mechanical (deterministic, can't be forgotten)

Wire prompts into the Makefile at the moments that matter most. Every eval run
ends with a capture:

```make
eval:
	python evals/run_eval.py | tee /tmp/eval_out.txt
	@echo ""
	@echo "--- 30 seconds, raw answers, don't make it sound good ---"
	@read -p "What did you expect before this ran? " a; \
	 read -p "What surprised you? " b; \
	 printf "\n## %s — eval\n- expected: %s\n- surprised: %s\n" \
	   "$$(date +%F\ %H:%M)" "$$a" "$$b" >> LOG.md

log:
	@read -p "What just happened? " a; \
	 printf "\n## %s\n- %s\n" "$$(date +%F\ %H:%M)" "$$a" >> LOG.md
```

`make log` is the escape hatch for anything else. One command, ten seconds.

#### Layer 2 — agent instruction (paste into DESIGN.md verbatim)

> **Standing instruction for all agents working in this repo.**
>
> This project is being documented as it's built. At the trigger moments below,
> stop and ask Jon 2–3 short questions, then append his answers *verbatim and
> unedited* to `LOG.md` under a timestamped heading. Do not polish his wording,
> do not expand it, do not turn it into prose. Raw is the point.
>
> **Trigger on:**
> - An assumption of his was disproven by data
> - A metric moved meaningfully, up or down
> - Something worked for the first time
> - A decision was made where real alternatives existed
> - He rejected or overrode your approach
> - Something took far longer than expected
> - End of a work session
>
> **Do not trigger:**
> - Mid-debugging — wait until it resolves
> - During setup or mechanical work
> - More than 4 times in a day
> - Twice in a row on the same thing
>
> Always accept "skip" without argument or follow-up.

#### The question bank

Short, concrete, answerable in one line. Rotate:

- What did you expect before you ran that?
- What surprised you?
- Why this over the alternative — one sentence?
- What was annoying about that?
- What would you tell someone about to make the same mistake?
- What do you understand now that you didn't an hour ago?
- How confident are you this is right, honestly?

And always: **"don't make it sound good."** Polished answers are worthless
here — they're what the editing pass is for. Frustration, doubt, and being
wrong are the most valuable things you can capture, and the hardest to
reconstruct later.

### What gets derived from what

| Artifact | Source |
|---|---|
| README / dev docs | DESIGN.md + contracts.py |
| Support docs, troubleshooting | failure modes hit during the build |
| LinkedIn posts | DECISIONS.md entries + surprises + numbers |
| Reddit (technical subs) | the retrieval tuning arc, with real metrics |
| Reddit (MTG subs) | the working tool — they want the thing, not the method |
| Long writeup / blog | LOG.md read end to end |

### On voice

Don't have a model generate the substance and try to make it sound like you.
That reads as AI-written, and an AI practice lead will clock it instantly.

Invert it: **you write the raw log, models shape structure.** The rawness is
the asset. "I wasted 90 minutes because the glossary parses differently" is
something no model would produce and every engineer recognizes as true.

Your existing voice reference from the resume/cover-letter/outreach work
applies here too — same person, same register.

### Publishing cadence

- **Days 1–14:** capture only. Two posts maximum.
- **End of week 1:** the retrieval numbers post. This is the strongest single
  piece of content the project will generate — do not publish before you have
  it. "I'm building a thing" is worthless; "here's how I moved recall@5 from
  61% to 89%, and what I got wrong first" is not.
- **End of week 2:** the shipped repo.
- **After:** mine LOG.md for the long tail at your leisure.

Reddit warning: technical subs punish self-promotion hard. Lead with the
finding, not the project. The repo link goes at the bottom, or in a comment.

---

## Do not delegate these

These four are the project. Outsource them and you've built nothing of value
to yourself:

1. The chunking decision — after you've counted your own rule lengths
2. Curating the eval question set — your moat, requires domain judgment
3. What counts as a correct answer — the grading criteria
4. Reading the retrieval failures — where the actual learning lives

---

## Explicitly deferred

Job-hunt pipeline · LinkedIn content system · home/personal admin ·
home server buildout · Cardomancer integration · friend's app integration ·
MCP server · Moxfield work

Not abandoned. Not now.

---

## Still open

- **Friend's app** — is it commercial? If yes, resolve the WotC Fan Content
  Policy question before you're deep in. Doesn't block days 1–9.
- **Don't commit CR text or bulk card data to the repo.** Fetch and index at
  build time. Follow Scryfall's attribution and rate-limit guidance.
