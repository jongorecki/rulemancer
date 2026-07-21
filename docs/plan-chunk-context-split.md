# Plan — Chunking: split embedded text from context text (DRAFT, pending review)

Working Rule 0 artifact. No code until reviewed. **Queued AFTER #3a lands** —
a chunking change and a rewriting change must not land together, or a moved
recall number can't be attributed to either.

## The problem, measured

`Chunk.text` currently does two jobs with opposite requirements: it is both
what gets embedded (wants to be *distinctive*) and what the generator reads
(wants to be *complete*). Today it is built as immediate-parent text + own text
+ examples, which serves completeness and sabotages distinctiveness.

Measured on the 601.2 family (rule 601.2 = "To cast a spell is to take it from
where it is..."), whose text is 705 characters:

| chunk | share that is its own text | cosine vs 601.2 |
|---|---|---|
| 601.2g | 21% | 0.963 |
| 601.2e | 24% | **0.994** |
| 601.2i | 32% | 0.964 |
| 601.2h | 47% | 0.898 |

Every pair in that family sits at 0.83–0.99 cosine. The shared 705-char
preamble dominates the vector, so the sentence that actually distinguishes
601.2g ("mana abilities must be activated before costs are paid") from 601.2i
("once the steps are completed... the spell becomes cast") is a fifth of the
embedded text. Which one ranks first is close to arbitrary. This surfaced
during the q016 gold re-audit and is suspected to affect any large-parent
family, not just 601.2.

**Scale (measured, whole corpus):** median parent text is only 55 chars, so the
prepending design is right for the common case. This is a tail: 43% of rules
carry a parent over 100 chars, 29% over 200, 8% over 400.

## The rule (Jon's call: option B, with a structural trigger)

Two fields instead of one:

- **`embed_text`** — what the index embeds. Own text + examples, plus the
  parent's text **only when that parent has no chunk of its own**.
- **`text`** — unchanged in meaning: what the generator reads and what a
  citation displays. Immediate parent + own + examples, exactly as today.

**Why "parent has no chunk" and not a length cutoff.** A length threshold tuned
to maximize recall on 31 questions is overfitting — the same objection raised
against a conditional-rewriting threshold, and it applies here too. The
structural test needs no tuned number, and the corpus splits on it cleanly:

| parent type | rules affected | median parent text |
|---|---|---|
| parent **has its own chunk** (already retrievable — duplication is noise) | 1,138 | 203 chars |
| parent is **folded/label** (text exists nowhere else in the index) | 844 | **7 chars** (max 30) |

The two populations don't overlap in any way that matters — the largest folded
parent is 30 characters. So the rule is principled rather than fitted: if the
parent's text is independently retrievable, don't duplicate it into every
child; if folding it away would delete the words from the index entirely
(701.5 "Cast"), keep it.

This preserves the original chunking decision's actual purpose. Prepending was
introduced so that folded labels still reach the index — that case is untouched.

## Edge cases

- **Glossary chunks** — no parent, unaffected. `embed_text == text`.
- **Examples** — stay in both fields. They're real retrievable content, not
  inherited boilerplate.
- **Citations** — anchor on `source_id`, untouched by this change.
- **Rules whose parent is folded** (844 of them) — behavior identical to today.
- **`601.2` itself** — keeps its own chunk and its own full text. Nothing is
  lost from the index; it simply stops being duplicated into nine children.

## Verification

1. **Golden tests (36) must pass unchanged.** Specifically the section-7 label
   test: 701.5 ("Cast") produces no chunk, and 701.5a leads with "Cast"
   prepended. Under this rule that still holds — assert it explicitly on
   `embed_text`, since that's the field the mechanic now lives in.
2. Add a test asserting the new behavior on a large-parent family: 601.2g's
   `embed_text` must NOT contain the 601.2 preamble, while its `text` must.
3. Re-embed (voyage-4-large, free tier, minutes) and re-run the retrieval eval.
   Report recall@k against the #3a numbers with everything else held fixed.
4. Re-run the answer eval — the generator's context is unchanged by design, so
   answer quality should hold. If it moves, that's a finding worth reporting.
5. Sanity metric to report either way: mean pairwise cosine within the 601.2
   family before vs after. The change is supposed to *separate* them.

## Success criteria (pre-committed)

| Check | Bar |
|---|---|
| Golden tests | 36/36 pass, including the unchanged 701.5a label mechanic |
| Aggregate | recall@5 does not regress vs the #3a result. An improvement is the hypothesis, not the bar |
| Regressions | zero questions flip hit→miss at k=5; any flip explained, not averaged away |
| Family separation | mean pairwise cosine within 601.2 drops meaningfully from ~0.9 |
| Answer eval | no new wrong/partial — generator context is unchanged by construction |

If recall is flat, the honest report is "this made the corpus cleaner and
changed nothing measurable" — which is still worth knowing, and still a better
data model. It does not get talked up into a win.

## Out of scope

Contextual retrieval (LLM-generated situating sentences per chunk — 3,617 calls
and it puts generated text into the corpus), full-chain parent context, and any
change to how citations render.
