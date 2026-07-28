<p align="center">
  <img src="branding/rulemancer-lockup-plum.svg" alt="Rulemancer" width="620">
</p>

# Rulemancer

Rulemancer answers Magic: The Gathering rules questions and shows you the
official rule text it used.

Magic has a 300-page rulebook called the Comprehensive Rules, and most
arguments at a game table come down to one sentence buried somewhere in it.
So the bot works in three steps. It searches the rulebook for the handful of
rules that bear on your question. It looks up the real text of any card you
named. Then it hands both of those to Claude and gets back an answer with the
rule numbers attached, so you can check it. If what it found doesn't actually
cover the question, it says so instead of guessing.

I built it because rules arguments at my table get settled by whoever sounds
the most confident, and that person is regularly wrong. During the build it
caught me being that person, which is the Tibalt section below.

The part I'd point at, though, isn't the bot. It's what happened when I
started measuring it, including the night the measurements knocked over a
conclusion I'd already written down as settled.

If you'd rather read the findings than the code, they're on their own page:
**[what was measured](https://jongorecki.github.io/rulemancer/)**. Six
findings, each carrying the set of questions it was computed over, generated
straight from the eval data in this repo.

## Results

I ran it against all 1,409 questions from [RulesGuru](https://rulesguru.net),
a Magic rules quiz site written by certified judges. Every answer was graded
by a second AI model, which is normal for this kind of testing and also the
weakest link, so I went and measured the grader too. That's further down.

**Roughly 86%, ±2pp sampling and a further ~4pp of instrument variance.**

In plain terms: think mid-eighties, not a precise number. Two of those points
are just sample size, the ordinary wobble you get from asking 1,409 questions
instead of a million. The other four points are the grader itself being
imperfect, which is the bigger source of doubt. Quoting a third decimal place
here would be pretending to a precision I don't have.

RulesGuru tags every question with a difficulty level, and the spread across
levels tells you more than the single number does:

| Level | Correct | Accuracy % | 95% CI |
|---|---|---|---|
| Level 0 | 199 / 207 | 96.1 | 92.6 - 98.0 |
| Level 1 | 510 / 565 | 90.3 | 87.5 - 92.4 |
| Level 2 | 342 / 406 | 84.2 | 80.4 - 87.5 |
| Level 3 | 110 / 162 | 67.9 | 60.4 - 74.6 |
| Corner Case | 49 / 69 | 71.0 | 59.4 - 80.4 |

That last column is the range the true number is very likely to sit in. The
smaller the group of questions, the wider it gets. Corner Case looks better
than Level 3 here, but those two ranges overlap almost completely, so I'm not
claiming that order is real.

It refused to answer 10 of the 1,409. Of the answers it did give, 98.1% cite
a specific rule number.

The full run cost $43.61, about three cents a question.

### Why Claude, and why you should believe me

The obvious objection to "I picked Claude and Claude did well" is that I had
a Claude grading the answers. Fair.

So I ran the same 1,409 questions through OpenAI's `gpt-5-mini` on the exact
same prompts, and then had four different graders score both sets, including
gpt-5-mini grading its own work against a competitor's.

| Grader | Whose side the grader is on | n each | claude-opus-5 (%) | gpt-5-mini (%) | Gap (pp) |
|---|---|---|---|---|---|
| gpt-5-mini | its own | 1,409 | 85.9 | 70.1 | +15.8 |
| Claude panel | Claude's | 72 | 87.3 | 68.1 | +19.2 |
| deepseek-v3.2 | neither | 150 | 87.3 | 70.0 | +17.3 |
| gemini-2.5-flash-lite | neither | 150 | 75.3 | 59.3 | +16.0 |

The first row is the one that counts. gpt-5-mini, grading itself, still put
itself about 16 points behind Claude. I wrote down which way each grader was
expected to lean before running any of it, so that row is the case where the
result goes against the grader's own interest.

Most of the gap isn't disagreement about rulings. It's refusals. Claude
declined 0.7% of the questions, gpt-5-mini declined 11.1%, roughly one in
nine, with the rules and the card text sitting right there in the prompt.
That count comes off a flag the model sets itself, so no grader is involved
in it at all.

The two neutral graders never got an agreement check of their own, so read
them as a sanity check on the ranking, not as extra proof. The absolute
scores do move around by grader, gemini-2.5-flash-lite runs about 12 points
low across the board, and that spread is exactly the instrument wobble in the
headline number. What doesn't move is which model wins.

## The reversal

Partway through the build I ran a swap test on the rules search. Take a
question, throw away the rules the search found for it, hand it some other
question's rules instead, and see how much the answer suffers. Everything
else stays identical. Over 120 questions, accuracy dropped 3.3 points, which
is well inside noise.

So I wrote down the conclusion: the rules search is barely doing anything,
the card text is carrying the answers.

That was wrong. How it was wrong is worth more than the original result.

Every one of those 120 questions named a specific card. It had to, because
99.4% of the full 1,409-question RulesGuru set does, and those 120 were drawn
from it. And a Magic card's text, plus the official
rulings attached to it, is already a restatement of the rules that apply to
that card. So the test was deleting one copy of the information and leaving
another copy sitting right next to it.

Magic players have a line for this: reading the card explains the card. You
say it to somebody who asks what a card does when the answer is printed right
there on it. Turns out you can measure that.

The original test wasn't bad arithmetic. It was fine arithmetic on a set of
questions where the answer couldn't have come out any other way.

So I wrote 86 new questions with no card names in them at all, pure rulebook
questions, and ran the same swap test again:

| What the bot was given | Correct | Accuracy % | 95% CI |
|---|---|---|---|
| The rules the search actually found | 85 / 86 | 98.84 | 93.70 - 99.79 |
| Some other question's rules | 13 / 86 | 15.12 | 9.05 - 24.16 |

It falls 83.7 points. Grader wobble everywhere else in this project runs
about 2 to 4 points, so a hole that size isn't the grader being flaky. 86
questions isn't many and the bottom row's range is wide, but nothing about
the direction is in doubt.

What I originally claimed was "the rules don't matter." What the evidence
actually supports is "the rules don't matter *when there's a card in the
question*." Different sentence, and it stops being true the second somebody
asks a question with no card in it.

Overturning my own published conclusion cost about five dollars.

## When it doesn't know, it says so

That swap test doubles as the cleanest look at what the bot does when it has
nothing useful to work with. Every one of those 86 rows fed it rules that
belonged to a different question, so it's confidently wrong material, handed
over as if it were right.

It refused on 90.7% of them and named what was missing. It made something up
on 3.5%, and when I read those three by hand, one of them looks like the
grader being wrong rather than the bot inventing anything.

Here's a refusal, word for word:

> I can't answer this from the rules provided. The context here contains no
> phasing rules at all (nothing from rule 702.25 on phasing, and nothing on
> whether a permanent phasing in counts as entering the battlefield).

It names the rule it would have needed. And on the arm where the search
worked normally it refused zero times out of 86, so this isn't a bot that
just bails a lot.

## Checking the grader

Every accuracy number on this page came out of an AI grader, so the grader is
a thing to be tested, not a thing to be trusted. A number is only as good as
whatever measured it.

It can be wrong in two directions, and I checked both.

**Passing a wrong answer.** 4 out of 90 sampled rows, so 4.4%, and the range
on that is 1.7 to 10.9. Treat it as a ceiling, because the stricter grader I
used to catch those leans toward calling things different in the first place.

**Failing a right answer.** 0 out of 77, range 0 to 4.7. Those 77 come from
two audits: a 30-row sample, and a complete sweep of all 53 hard rows the
grader passed, meaning every Level 2, Level 3 and Corner Case row across
three runs. Six rows are in both audits, so 30 and 53 dedupe to 77 unique
rows rather than 83. I did the full sweep of the hard ones specifically
because that's where I expected the misses to be hiding, and they weren't
there. One row is arguable and could turn that 0 into a 1.

The two errors push opposite ways. Passing wrong answers inflates my number,
failing right ones deflates it, and at these rates they don't cancel out. The
lean is that roughly 86% slightly undersells it. That's a lean, not a proof.
Worst case in both directions is about -11.6 to +10.9 points, and the same
model family graded answers written by its own family, which is a caveat I
can't design my way out of.

## What it gets wrong

Level 3 is 67.9%, and it doesn't get gradually worse, it falls off a cliff. A
separate 311-question sample put the Level 3 failure rate at 42.9%, about 5.8
times that sample's baseline, so the drop shows up in two different sets.

I read 10 of the 23 failures in that sample myself. What keeps coming up:

- Layers. Layers is the part of the rules that decides what order overlapping
  effects apply in (CR 613), and it's the biggest single bucket of failures.
  It's also the hardest part of the rules for people.
- Confusion about when a permanent loses its abilities, especially on Sagas
  and merged permanents.
- Getting the order or timing of triggers wrong.
- Mixing up what a restriction covers, treating "can't cast" as if it also
  meant "can't activate."
- Refusing to answer questions that only need the flavor text.
- Forgetting that some effects keep applying after the card that made them is
  gone.

The other 13 failures I only sorted by the grader's one-line reason, not by
reading the whole answer, so that's a read of the sample rather than a
complete list. And the by-tag pattern is shakier still: the hard run is 49 of
54 Layers questions and no other run has a single one, so I can't separate
"Layers is hard" from "that run was hard." I'm not claiming the first one.

Multi-hop questions also miss. If the answer lives in a rule you can only
reach by following a cross-reference out of a rule the search found, the
search usually doesn't get there.

## How it works

```
question ──► Haiku rewriter (temp=0, sees the conversation transcript)
                 │
                 ▼
         voyage-4-large vector search over 3,619 chunks ── top 15
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

Walking that top to bottom. A small, cheap model first rewrites your question
into something that searches better, and it can see the conversation so far,
so follow-ups like "what if it's blocked?" still work. The rulebook has been
split into 3,619 pieces, and every piece has been turned into a list of
numbers that captures its meaning, so the search can match on meaning rather
than on matching words. Your question gets turned into numbers the same way,
and the 15 closest pieces come back. If you named a card, its real text and
official rulings get pulled from [Scryfall](https://scryfall.com). All of
that goes to Claude, which answers in a fixed shape: the text, the rules it
cited, and a yes/no flag for whether it could answer at all.

The rulebook here is 3,153 rules and 735 glossary entries out of the June 19,
2026 revision, cut into those 3,619 pieces. Turning all of it into numbers
fits inside Voyage's free tier.

There's no vector database, which is the usual thing to reach for. Comparing
your question against all 3,619 pieces by brute force takes under a
millisecond in NumPy. The only real wait is the API call that turns your
question into numbers.

Every model is pinned to a specific version, because test results mean
nothing if the model can change underneath a run. The exact settings get
stamped onto every row of every test, as they actually ran rather than as I
meant them to run, so any result can be traced back to what produced it.

If the rules that came back don't cover the question, that `answered` flag
comes back false and the bot says what's missing instead of filling the gap
from whatever it half-remembers. The swap test above is the deliberate stress
test of that path.

Card rulings get filtered for relevance before they reach the prompt. Some
cards carry dozens of official rulings and almost none of them apply to the
question you asked.

[DECISIONS.md](DECISIONS.md) has the reasoning behind every call, and
[LOG.md](LOG.md) is the raw build log with the failures left in.

## What didn't work

Most writeups about this kind of project only show the wins, so here's the
other half.

Combining two search methods made things worse. The old-fashioned
keyword search found the right rule in the top 5 on 32% of my 31 test
questions. The meaning-based search got 65%. Every way I tried to blend the
two landed somewhere in the middle, because the weak one dragged the strong
one down. None of it shipped. I kept the code so the result stays
reproducible.

My best query-rewriting number was a lucky roll. It came back at 77% on the
first run, then 68, then 71, and the questions that failed weren't even the
same ones each time. The rewriter is an AI, so the rewritten question is a
fresh roll of the dice every time, and my cache had frozen one good roll in
place where it looked like a stable result. With the randomness turned down
and five runs averaged, the real number is about 70%.

The chunking fix hurt the exact question it was built for. Related rules were
sharing so much of the same prefix that they all looked nearly identical to
the search, so I split the text used for searching from the text the model
reads. Search got better across the board, 68% in the top 5 and 87% in the
top 10 with rewriting, and the one question that made me do the work in the
first place fell from 16th place to 84th. It had been matching the shared
preamble the whole time, not its own rule. I kept the change because it helps
everywhere else, and that question is on the multi-hop list now.

One question failed the search and still got answered correctly. There were
several valid ways to get to the answer and my answer key only listed one, so
the search scored it a miss while the bot's answer was right and properly
cited. I fixed the key. If your answer key only allows one right route, it
can't see a question with two.

And the big one: I published a conclusion that the rules search barely
mattered, then knocked it over myself. That's the reversal section above.

## The Tibalt example

I asked whether cascading into
[Valki, God of Lies](https://scryfall.com/card/khm/114/valki-god-of-lies-tibalt-cosmic-impostor)
lets you cast the Tibalt side for free. The bot said no, citing cascade rule 702.85a:
you can only cast the spell if the resulting spell's mana value is less than
the cascading spell's, and Tibalt's is 7.

I was sure it was wrong. Tibalt cascade was a whole archetype in Modern, and
the friend I was testing with agreed with me. But Wizards errata'd cascade to
kill that interaction, the errata is in the current rulebook, and the bot had
retrieved it. We were both arguing from memory that was a few years stale,
against the current text. The bot was right.

## How it was built

Claude Code wrote the code. I'm not going to be cagey about that. It's an AI
project and that's the whole point of it. What I did was set the standing
rules, sign off on the plans, decide what got measured, and read the
failures.

Those rules live in [CLAUDE.md](CLAUDE.md), which is the actual working
contract, not a description of one. Two of them earn their keep constantly.

**Nobody states a Magic fact from memory, me included.** Claims get checked
against the rulebook text in the repo or against Scryfall. The Tibalt section
above is what happened the one time that rule got broken: two people
confidently remembering an interaction that had been errata'd out from under
them.

**Every number gets asked what group of things it was counted over.** In one
evening that caught four of my own figures that were arithmetically fine and
counted over the wrong group.

Here's one of them, and it's the reason the headline up top carries the error
bars it does. I had measured how often the grader changes its mind between
runs and got 0.48%, which would make it about as steady as a ruler. But I'd
measured that on the easiest set of questions I had, where the bot gets
nearly all of them right and almost nothing is close enough to argue about.
Of course the grader agreed with itself. Measured on the sets that motivated the
question, where scores land in the seventies and eighties, it's 2 to 4 points.
That's the ~4pp of instrument variance in the headline. The original number
wasn't a miscalculation, it was a correct calculation over questions that
couldn't show the problem.

The reversal above is that same mistake at a much larger size.

Every non-obvious call went into [DECISIONS.md](DECISIONS.md) when it was
made, with what would change my mind written down before the result came in.

## Run it

```
git clone <this repo>
cd mtg-rules-bot
uv sync
cp .env.example .env       # then add your VOYAGE_API_KEY and ANTHROPIC_API_KEY
```

Download the Comprehensive Rules TXT from
https://magic.wizards.com/en/rules into `data/raw/` (create that folder first,
a fresh clone doesn't include it). The index builder expects
`MagicCompRules 20260619.txt`, so if Wizards has shipped a newer revision,
update the filename in `evals/build_vector_indexes.py`.

```
uv run python evals/build_vector_indexes.py   # parse, chunk, embed (one time)
uv run python run.py                          # serves API + frontend, opens the browser
```

The first page load waits a few seconds while the search index loads. API
docs are at `/docs`.

Tests: `make eval` for the search, `make answers` for answer grading, and
`make ablate` for the swap test. The last two cost API calls.

It serves from a single uvicorn process and hasn't been load-tested. That's
fine for a demo and not sized for real traffic.

## Live demo

It's live at **[rulemancer.jongorecki.com](https://rulemancer.jongorecki.com)**,
gated behind an access code so the API bill stays mine. Codes get handed out
one at a time, so ask me for one.

The [results page](https://jongorecki.github.io/rulemancer/) isn't gated and
doesn't run on the demo's server, so it stays up whether or not the demo is.

## Why Magic

I've played for years, so I can write my own test questions and tell whether
an answer is right. Grading answers in a subject I don't know would've been
guesswork, and this whole project turns on the grading being worth something.

The rules are also a good stress test. The rulebook runs about 300 pages,
full of cross-references and exceptions, and a lot of questions come down to
a single clause.

None of the plumbing is Magic-specific though. Point it at a compliance
manual or an insurance policy and it's the same problem with different text.

This is a sibling project to
[Cardomancer](https://github.com/jongorecki/cardomancer), my card-sorting
machine (OpenCV + image hashing + vector embeddings). Cardomancer figures out
which physical card it's looking at, and this one answers questions about it.

## Attribution

Rulemancer is unofficial Fan Content permitted under the
[Wizards of the Coast Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy).
Not approved or endorsed by Wizards. Magic: The Gathering and the
Comprehensive Rules are © Wizards of the Coast, LLC. The CR text is not
included in this repository, it gets downloaded at build time.

Card data and rulings come from [Scryfall](https://scryfall.com). Scryfall is
not affiliated with this project.

Code is [MIT licensed](LICENSE).
