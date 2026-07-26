<p align="center">
  <img src="branding/rulemancer-lockup-light.png" alt="Rulemancer" width="620">
</p>

# Rulemancer

Rulemancer answers Magic: The Gathering rules questions and cites the
Comprehensive Rules text it used. Reference a card and it pulls that card's
official rulings too. FastAPI backend, chat frontend, runs with one command.

I built it because rules arguments at my table get settled by whoever sounds
the most confident, and that person is regularly wrong. I wanted answers that
come with the actual rule attached. During the build it caught me doing the
exact thing it was built to fix, which I'll get to below.

## The numbers

Everything in this table is measured. [DECISIONS.md](DECISIONS.md) has the
reasoning behind each call and [LOG.md](LOG.md) is the raw build log,
failures included.

| Metric | Result |
|---|---|
| Retrieval recall@5, BM25 baseline | 32% |
| Retrieval recall@5, vector (voyage-4-large) | 65% |
| Retrieval recall@5 after the chunk split | 68% (recall@10 87% with rewriting) |
| Query rewriting (always-on Haiku, temp=0) | ~70% @5 as a 5-draw mean |
| Answer grading, 31 rules questions, graded against the cited rule text (sonnet-5, pre-switch) | 31/31 correct, no invented rules |
| Card eval, 19 questions, some multi-card combos (sonnet-5, pre-switch) | quality held while ruling context was cut hard |
| Load-bearing ruling picked by the rulings retrieval | 12 of 15 |
| LLM-judge agreement, Haiku vs Sonnet | 94 to 99% |
| Multi-turn stability fix | bad follow-up draws went from 3 in 6 to 0 in 5 |
| Generator bakeoff, 54 questions, same prompt/rewrite/judge | opus-5 low-effort 74.1% mean vs sonnet-5 64.8% mean (+9.3pp), cheaper and ~2.5x faster |

The corpus is 3,151 rules and 735 glossary entries, chunked into 3,617
chunks. Embedding all of it fits inside Voyage's free tier and a query costs
a few cents.

## Why Magic

I've played for years, so I can write my own eval questions and tell whether
an answer is right. Grading answers in a domain I don't know would've been
guesswork.

The rules are also a good stress test. The CR runs about 300 pages, full of
cross-references and exceptions, and a lot of questions turn on a single
clause.

Nothing in the pipeline is Magic-specific though. Point it at a compliance
manual or an insurance policy and it's the same problem with different text.

This is a sibling project to
[Cardomancer](https://github.com/jongorecki/cardomancer), my card-sorting
machine (OpenCV + image hashing + vector embeddings). Cardomancer identifies
the physical cards, and this answers questions about them.

## What didn't work

Most RAG writeups only show the wins, so here's the other half.

Hybrid retrieval made things worse. BM25 scored 32% recall@5 and vector
scored 65%, and every fusion of the two landed somewhere in between, because
the weak retriever dragged the strong one down. Nothing hybrid shipped. I
kept the code so the result stays reproducible.

My best rewriting number was a lucky roll. Query rewriting came back at 77%
recall@5 on the first run, then 68 on the next, then 71. The rewriter is an
LLM, so the rewritten query is a random draw, and my cache had frozen one
lucky draw in place where it looked deterministic. With temperature pinned to
0 and a 5-draw mean the real number is about 70.

The chunking fix hurt the question it was built for. Rule families shared so
much prepended parent context that siblings embedded nearly on top of each
other, so I split the text that gets embedded from the text the generator
sees. Recall went up across the board, and the one question that motivated
the change dropped from rank 16 to rank 84. It had been matching the shared
preamble rather than its own rule the whole time. I kept the split since it
helps everywhere else, and that question is on the multi-hop list now.

One question failed retrieval and still answered correctly. It had several
valid rule paths and my gold set only listed one of them, so recall@k scored
a miss while the generated answer was right and properly cited. I fixed the
gold.

Additionally, the rules retrieval turned out to be dead weight on 4 of my
first 5 card questions. I built an ablation harness that removes each cited
rule and re-asks the question to see whether the answer survives. On those 4
the card's own text and rulings covered everything. The card eval set got
rebuilt around questions where the retrieved rules actually matter.

## The Tibalt example

I asked whether cascading into
[Valki, God of Lies](https://scryfall.com/search?q=%21%22Valki%2C+God+of+Lies%22)
lets you cast the Tibalt side for free. The bot said no, citing cascade rule
702.85a: you can only cast the spell if the resulting spell's mana value is
less than the cascading spell's, and Tibalt's is 7.

I was sure it was wrong. Tibalt cascade was a whole archetype in Modern, and
the friend I was testing with agreed with me. But Wizards errata'd cascade to
kill that interaction, the errata is in the current CR, and the bot had
retrieved it. We were both arguing from memory that was a few years stale,
against the current text. The bot was right.

## How it works

```
question ──► Haiku rewriter (temp=0, sees the conversation transcript)
                 │
                 ▼
         voyage-4-large vector search over 3,617 chunks ── top 15
                 │
[Card Name] ──► Scryfall enrichment (per-face data, layout, costs)
                 │        └─► per-card rulings retrieval (top 3 over a
                 │            calibrated cosine floor, withhold by default)
                 ▼
         claude-opus-5 (effort=low), structured output: {text, citations, answered}
                 │
                 ▼
         FastAPI /answer: cited rule text resolved, cards + rulings used,
         optional debug panel (rewrites, retrieved ids, selected rulings)
```

A few calls worth explaining. The full reasoning for each is in
[DECISIONS.md](DECISIONS.md).

There's no vector database. Brute-force cosine over 3,617 vectors runs in
under a millisecond in NumPy, so the only real latency is the embedding API
round-trip.

Every model is pinned. Eval numbers mean nothing if a model can change
between runs. Generation was pinned to claude-sonnet-5 for most of the build;
it moved to claude-opus-5 at low effort on July 26, after a controlled 54-
question head-to-head (same prompt, rewrite, and judge) put opus at a 74.1%
mean answer accuracy against sonnet's 64.8%, while also running cheaper and
about 2.5x faster.

If the retrieved rules don't cover the question, the `answered` flag comes
back false and the bot says what's missing instead of filling the gap from
training data. Across the 31 graded questions it never stated a false rule.
The two it got wrong were an honest decline and an incomplete answer.

Each referenced card's rulings get relevance-filtered against the question
before any of them reach the prompt. Two of the eval cards carry 35 rulings
between them, and the filter passes 6 through. Answer quality held everywhere
after the cut.

I wrote the gold sets and graded every answer myself. An LLM judge pre-scores
as a regression check, but it doesn't get to decide what's correct.

## Run it

```
git clone <this repo>
cd mtg-rules-bot
uv sync
cp .env.example .env       # then add your VOYAGE_API_KEY and ANTHROPIC_API_KEY
```

Download the Comprehensive Rules TXT from
https://magic.wizards.com/en/rules into `data/raw/` (create that folder first
-- a fresh clone doesn't include it). The index builder expects
`MagicCompRules 20260619.txt`, so if Wizards has shipped a newer revision,
update the filename in `evals/build_vector_indexes.py`.

```
uv run python evals/build_vector_indexes.py   # parse, chunk, embed (one time)
uv run python run.py                          # serves API + frontend, opens the browser
```

The first page load waits a few seconds while the vector store loads. API
docs are at `/docs`.

Evals: `make eval` for retrieval, `make answers` for answer grading, and
`make ablate` for gold-by-ablation. The last two cost API calls.

## Limitations

Multi-hop questions miss. If the answer lives in a rule you can only reach by
following a cross-reference from a retrieved rule, retrieval likely won't
surface it. That's the rank-84 question above.

Generation has draw variance. The generator sometimes returns a weak or empty
draw. A targeted retry catches the worst shape of it, and the follow-up
failure rate went from 3 in 6 to 0 in 5 after that fix (measured on
sonnet-5), but the variance is still there underneath and hasn't been
re-measured since the switch to opus.

The API runs a single worker with a lock, because the caches are whole-file
read and write. That's fine for a demo. It needs per-key caches before any
real concurrency.

The 31/31 and 19-question numbers above predate two changes since: a
system-prompt revision, and the July 26 swap of the production generator from
sonnet-5 to opus-5 at low effort. Both reword every answer, so a re-grade
against the current pipeline is on the list before I treat those two numbers
as current. The generator bakeoff row is the newer, current evidence for the
model choice itself.

## How it was built

I directed Claude Code through the build, with two standing rules: the plan
gets written and reviewed before the code, and nobody asserts a Magic fact
from memory, me included. Every non-obvious call went into
[DECISIONS.md](DECISIONS.md) at the time it was made, and [LOG.md](LOG.md)
kept the raw notes. The Tibalt section above is what happened the one time
the memory rule got broken.

## Attribution

Rulemancer is unofficial Fan Content permitted under the
[Wizards of the Coast Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy).
Not approved or endorsed by Wizards. Magic: The Gathering and the
Comprehensive Rules are © Wizards of the Coast, LLC. The CR text is not
included in this repository, it gets downloaded at build time.

Card data and rulings come from [Scryfall](https://scryfall.com). Scryfall is
not affiliated with this project.

Code is [MIT licensed](LICENSE).
