# Moved to Tutormancer

The card-similarity / deck-tool spec that used to live here
(`docs/spec-cards-rag.md`) moved to its own repo, **Tutormancer**, at
`D:\Job_hunt\tutormancer` on 2026-07-27.

**New location:** `D:\Job_hunt\tutormancer\docs\spec-tutormancer-v1.md`
(probe script: `D:\Job_hunt\tutormancer\probes\cards_corpus_probe.py`)

## Why

Rulemancer's channel ablation (`docs/results-channel-ablation.md`) found that
card oracle text, not Comprehensive Rules retrieval, is the load-bearing
signal for rules answers. Separately, the cards spec's own measurement found
card resolution never fails on Rulemancer's eval corpus (3,597 refs across
1,399 rows, zero unresolved). Together those two results mean a
card-similarity/deck index does nothing measurable for rules answering — it's
a different product (deckbuilding: functionally equivalent-or-better and
cheaper card swaps against live prices), not a Rulemancer feature. It got its
own repo instead of staying a "maybe integrated" corner of this one.

Git history for the original spec (its authorship, revisions, and the
measurement sessions behind it) is preserved in this repo's history up to the
commit that removed it — nothing was lost, it just isn't at this path anymore.
