# Spec — `scripts/check_cr_update.py`

Written 2026-07-25. Jon's ruling: **never renumber gold by hand.** Detect
automatically, fix automatically where the fix is provably safe, and where it
isn't, ask once and record the answer so the next occurrence is automatic too.

> **APPROVED by Jon, 2026-07-25** — content fingerprinting is the agreed
> approach. Rule 0 is satisfied; this is cleared to build. Build it against
> §6's verification list, and note the self-test (old and new pointing at the
> same CR must report 100% `unchanged`, 0 remaps, 0 flags) is the first thing
> to make pass — a differ that can't recognise identity can't be trusted about
> change.

---

## 1. The problem

The Comprehensive Rules are re-released with every set. Three things break, and
none of them raise:

1. **Silent drops** — a malformed source line never parses, and a rule vanishes.
   Cost so far: `606.5` and `119.1d`, both missing for the life of the project;
   `rg4420` was unanswerable because its judge answer quotes 606.5 verbatim.
   **Already solved** by `tests/test_cr_parse_coverage.py` (4 guards). Not this
   spec's job — but the checker re-runs them so one command covers everything.

2. **Renumbering** — the worst of the three, because gold keeps *working*. A
   gold id is a position, not an identity. If 704.5n becomes 704.5p in the next
   release, the old id now points at whatever moved into that slot. Retrieval
   scores a hit against the wrong rule and the eval quietly measures nothing.

3. **Edits** — the number and position survive but the text changed, so a rule
   that used to state the answer may no longer.

## 2. The idea: identity by content, not position

This is the repo's recurring defect in its largest form — *an index into an
externally-owned list, persisted as if it were an identifier*. `ruling_id()`
already fixed exactly this for card rulings by hashing the text (commit
`7a316bd`, "make ruling_id() content-derived, not positional").

Apply the same move to CR rules:

```
rule_fingerprint(rule) = sha256(normalize(rule.text))[:16]
normalize = collapse whitespace, fold curly quotes/apostrophes to ASCII,
            strip the leading rule number if the text repeats it
```

A fingerprint survives renumbering. A number does not. Diffing two releases by
fingerprint turns "what changed?" from guesswork into set arithmetic.

## 3. What it does

```
uv run python scripts/check_cr_update.py --old <old CR.txt> --new <new CR.txt>
```

**Step 1 — parse both, fail loudly on drops.** Run the four
`test_cr_parse_coverage` invariants against the NEW file. If the new release has
a malformed line, stop here and report it — everything downstream would be
measuring a corpus with a hole in it.

**Step 2 — classify every rule** by joining old and new on fingerprint and number:

| class | fingerprint | number | meaning |
|---|---|---|---|
| `unchanged` | same | same | nothing to do |
| `renumbered` | same | changed | text identical, id moved |
| `edited` | changed | same | same slot, new wording |
| `deleted` | gone | — | no rule in the new release has this text |
| `added` | new | — | new rule |
| `ambiguous` | same fingerprint, **several** candidates | — | duplicate text; cannot auto-resolve |

**Step 3 — apply to every gold id in every eval file.** Files: `questions.jsonl`,
`rulesguru.jsonl`, `rulesguru_full.jsonl`, `questions_rulesguru150_v2.jsonl`,
and any `gold_proposals_*.jsonl`. For each gold id, per class:

| class | action |
|---|---|
| `unchanged` | leave it |
| `renumbered` | **auto-remap.** Safe by construction: the text is byte-identical, so the rule the gold meant still exists and this is the only id that reaches it. Recorded in the report, not silently. |
| `edited` | **flag.** The rule may no longer state the answer. Needs Jon or a re-mine — the checker cannot know. |
| `deleted` | **flag.** Gold points at a rule that no longer exists. |
| `ambiguous` | **flag**, listing every candidate. |
| folded-parent (id not a chunk after re-chunking) | **flag** — the `702.16`-class problem, repairable by the existing mining pass |

**Step 4 — write the report** (`docs/cr-update-<new date>.md`): counts per class,
every auto-remap as `old -> new` with the affected question ids, and every flag
grouped by what it needs.

**Step 5 — index.** Report which chunks are added/removed and print the append
command. Append rather than rebuild when nothing was removed: Voyage returns
slightly different vectors per call, so a full re-embed perturbs every retrieval
number ever measured. If any chunk was removed, a rebuild is required and the
report says so plainly.

## 4. The "ask me how to fix it automatically" loop

Jon's requirement, and the part that makes this compound rather than repeat.

Every flag the checker cannot resolve is written to
`evals/cr_update_policy.json` as an open question with its class and evidence.
When Jon answers, the answer is recorded **as a rule, not as a one-off edit**:

```json
{
  "class": "edited",
  "when": "text change is whitespace/punctuation only",
  "decision": "auto-remap, do not flag",
  "ruled_by": "Jon", "ruled_at": "2026-07-25"
}
```

On the next release the checker consults the policy file first and only asks
about genuinely new situations. The set of things Jon must answer shrinks with
each CR release instead of repeating.

**Nothing is auto-applied outside `renumbered` until a policy entry says so.**
That is the line: byte-identical text is a fact, everything else is a judgment.

## 5. What it must never do

- Never rewrite `answer_gold`. Judge-authored, out of scope, always.
- Never silently drop a gold id it cannot resolve — flag and keep.
- Never rebuild the vector index when an append would do.
- Never renumber by editing eval files in place without the report — the report
  is the artifact; `--apply` is a separate, explicit flag.

## 6. Verification

- **Self-test on the current release**: `--old` and `--new` both pointing at
  `MagicCompRules 20260619.txt` must classify 100% `unchanged`, 0 remaps, 0
  flags. Any other result is a bug in the differ.
- **Synthetic renumber**: copy the CR, rename `704.5n` to `704.5zz`, confirm the
  checker classifies it `renumbered` and proposes exactly that remap.
- **Synthetic edit**: change one word in a rule, confirm `edited` and flagged
  rather than remapped.
- **Synthetic drop**: reintroduce the `606.5` typo, confirm step 1 halts.

## 7. Out of scope

Auto-re-mining flagged questions (that's the existing mining pipeline, invoked
separately once the report says which questions need it), and any change to
production retrieval.
