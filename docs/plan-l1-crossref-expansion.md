# Plan — L1: deterministic cross-reference expansion (+ rewrite-as-ruling-query arm)

Status: DRAFT for Jon's review (Rule 0). No implementation until approved,
and none until the OpenRouter arm run exits (fresh arm processes import
this code).

## Goal

Close the multi-hop gap (q016 / c010 / c011 / c019 class) two ways:
- **Part A (rules):** after vector retrieval, follow the CR's own "see rule
  X" references in the retrieved chunks and append up to 5 referenced
  chunks the pool missed. No LLM call, no variance, no cost.
- **Part B (rulings):** an eval ARM that selects rulings against the Haiku
  rewrite (rules vocabulary) alongside the raw question, union — measured
  first, shipped only if it wins.

## Part A — cross-ref expansion

### Insertion point

`RulesAgent.answer()` in generate/answer.py, immediately after `retrieved`
is assembled (post `rrf_fuse`/`search`, before `self.last_retrieved =`).
New pure function in retrieve/ (testable without an agent):

```python
def expand_crossrefs(retrieved, chunk_map, max_extra=5) -> list[Retrieved]
```

`chunk_map` ({source_id: chunk}) built once in `RulesAgent.__init__` from
`store.chunks` — same dict api/main.py already builds; the agent becomes
its owner and the API can reuse it.

### Reference extraction

Scan `r.chunk.text` for each retrieved chunk IN RANK ORDER; collect refs in
first-mention order (deterministic):

- `rule[s]? (\d{3}(\.\d+[a-z]?)?)` — "see rule 704.5", "rules 601.2a"
- bare `\b(\d{3}\.\d+[a-z]?)\b` — inline mentions like "(601.2h)"

Dedupe (against the pool AND among refs), then resolve and append until
`max_extra`.

### Resolution rules (the edge cases)

1. Exact `source_id` in chunk_map → that chunk.
2. Bare family ref ("see rule 704"): try `"704"`, else fall back to
   `"704.1"` (the family's entry rule). One chunk, not the whole family —
   the cap is 5 and a family dump would eat it.
3. Ref with no chunk at all (label-like rules never got chunks, e.g.
   701.5 "Cast"): SKIP, count it. Recorded in a new
   `last_crossref` debug field (refs_found / appended / skipped) so misses
   are observable, not silent.

### Appended Retrieved entries

- Appended AFTER the organic top-15, first-mention order — organic ranks
  are untouched, so nothing the retrieval eval measures moves.
- Score: sentinel `0.0` (they weren't scored by the retriever; pretending
  otherwise would poison any future score-reading logic). If `Retrieved`
  needs a field/flag for provenance, prefer the score sentinel + the debug
  record over a contract change.

### What this deliberately does NOT do

- No recursive expansion (refs-of-refs) — one hop, matching the diagnosis.
- No LLM second-hop query — that's the fallback if measurement says
  structural expansion isn't enough (roadmap's explicit ordering).
- No prompt template change — more `[id] text` blocks in the same format.
  PROMPT_VERSION unchanged. The prompt-identity fixture asserts assembly
  on a FIXED retrieved list, so it should pass untouched — verify, don't
  regenerate.

## Part B — rewrite-as-ruling-query ARM (measure before shipping)

`select_rulings()` today embeds the RAW question only (rulings read as
plain English). The c010/c019 failure: the load-bearing ruling is phrased
in rules language the raw question never uses.

- Arm: for each ruling-bearing question, select against (a) raw question,
  (b) each Haiku rewrite string, union by ruling index keeping max cosine,
  cap union at TOP_N+1 (=4) so the union can't flood the prompt.
- Cost: one extra cached query embedding per rewrite string (the ruling
  embeddings themselves are already cached/frozen).
- Harness: extend the existing card-eval path with a `--ruling-query`
  flag (raw | union). Report per-question: did the load-bearing ruling
  (each question's `note` names it) clear the floor / make the cut?
- Ship criterion (Jon decides off the table): c010/c019-class questions
  improve AND no question loses a load-bearing ruling it has today.

## Verification (Part A gates)

1. Unit tests on `expand_crossrefs`: ref extraction (both patterns, dedupe,
   cap), resolution fallbacks (family ref, label skip), determinism (same
   input → same output), pool-dedupe.
2. Prompt-identity test passes UNCHANGED (assembly didn't move).
3. Full retrieval eval: byte-identical rankings (expansion is post-ranking
   by construction — this run proves it).
4. The 4 known misses end-to-end: for each, did the answering rule/ruling
   reach the generator pool? Report the before/after pool for each.
5. Answer regen on affected questions only; Jon grades those few (no full
   re-grade — PROMPT_VERSION didn't bump).

## Sequencing

Both parts wait for: arm run exit → v4-flash gap re-run → sonnet re-grade
arm (queue items 1-2). Part A is then implementable by Sonnet against this
spec; Part B rides the same eval-harness session.
