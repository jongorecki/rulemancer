**DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.**

# Plan — run progress heartbeats + incremental writes

Written 2026-07-25. Jon's ask: *"is it possible to show a loading bar on the
screen to show how the generations are going? that will make it so I don't have
to ask."*

Grounding read: `evals/run_answer_eval.py`, `evals/run_openrouter_arm.py`,
`src/rulesagent/generate/openrouter_backend.py`, `pyproject.toml`,
`docs/HANDOFF-development.md` (OPERATIONAL LESSONS).

## 1. Why this is not cosmetic

Progress information already exists. Both runners print a per-question line:

- `run_openrouter_arm.py:654` — `[{i}/{n}] {qid} -> {status} ({elapsed}s)`
- `run_answer_eval.py:282` — same shape

Three structural problems make it useless in practice, and all three are
documented failures from the 2026-07-24 session:

1. **It goes to stdout of a detached background job.** Nobody is watching that
   terminal, and the job dies at the ~1hr ceiling regardless.
2. **Piping it block-buffers it** and masks python's exit code behind the
   pipe's `0`. A crashed run reported "exit code 0" and stayed hidden for 40
   minutes. A terminal progress bar hits this same wall — it is the wrong shape
   for how these runs actually execute.
3. **Four concurrent cells need one view.** A run agent reported "monitors
   armed, grid running" while **two of four runs had never been launched**,
   including the decision-relevant condition-E cell.

Problem 3 is the important one. "The grid is running" is currently an
*assertion*. This slice makes it a *falsifiable claim* backed by filesystem
evidence that maintains itself, rather than evidence someone has to remember to
go looking for.

## 2. Design — heartbeat file per run

Each run writes `evals/answers/_progress/{run_name}.json` after **every
question**, written atomically (temp file + `os.replace`) so a reader never
catches a half-write:

```json
{
  "run": "gpt-5-mini_v5_r1",
  "model": "openai/gpt-5-mini",
  "variant": "v5",
  "n_total": 8,
  "n_done": 5,
  "last_qid": "c014",
  "errors": 0,
  "started_at": "2026-07-25T10:04:11Z",
  "updated_at": "2026-07-25T10:06:25Z",
  "status": "running",
  "cost_so_far": 0.0271,
  "pid": 48120
}
```

`status` ∈ `running` | `done` | `failed`. Terminal states are written in a
`finally` block so a crash still records `failed` rather than leaving a
`running` file behind forever.

**`cost_so_far` is OpenRouter-only.** `run_answer_eval.py`'s sonnet rows carry
no `usage` field (confirmed in `report-v4e.md` §11), so the sonnet bar shows
`--` for cost rather than a fabricated number. Adding usage capture to the
sonnet path is a separate, optional item (§6).

## 3. The watcher

`evals/watch_runs.py` reads every file in `_progress/` and renders one line per
run. Stdlib only — no `tqdm`, no `rich` (neither is in `pyproject.toml`, and
adding a dependency for this is not worth the decision):

```
sonnet_v5_r1      [##########------]  5/8   c014     2m14s   $--
sonnet_v3_r1      [################]  8/8   done     3m01s   $--
gpt-5-mini_v5_r1  [###-------------]  2/8   c004       41s   $0.01
gpt-5-mini_v3_r1  [----------------]  0/8   --       STALLED (no heartbeat 6m)
```

- `--watch` refreshes on an interval; bare invocation prints once and exits
  (so it composes with anything).
- **`STALLED` is the load-bearing feature, not the bars.** `status == running`
  with `updated_at` older than a threshold (default 5 min, `--stale-after`)
  renders STALLED. A run that was never launched and a run that died silently
  are indistinguishable to a progress bar that was never drawn; both are
  immediately visible as a heartbeat that stopped advancing.
- Runs whose `pid` is no longer live and whose status is still `running` are
  flagged `DEAD` — this is the `Get-CimInstance` check from the operational
  lessons, automated.

## 4. Bundled: incremental row writes

Both runners currently write results **once, after the loop**
(`run_openrouter_arm.py:691`). Combined with `openrouter_backend._attempt()`
wrapping `data = r.json()` in a try that catches only `httpx` errors, a
malformed or truncated HTTP 200 kills the whole run **with zero rows saved** —
the bug that crashed the first default r2. The handoff calls this out as a real
bug "worth a slice," and notes incremental writes would also make the ~1hr
background-job ceiling survivable.

Since this slice already touches disk after every question for the heartbeat,
it writes the **row** at the same point. Three things fall out of one change:

- **Visibility** — the heartbeat (§2).
- **Crash resilience** — a run that dies at question 6 of 8 keeps 6 rows.
- **Resumability** — a run can skip qids already present in its output file,
  which survives the 1hr kill without the bespoke resume logic Task 2 needed.

Also in scope, because it is the actual crash: widen `_attempt()`'s except
clause to catch JSON decode errors on a 200 body and route them through the
existing retry path, rather than letting them escape as a fatal.

**Output-file compatibility is a hard requirement.** The final file must remain
byte-identical in schema to what the current runners produce — the same
`summary` field, the same row shape — or every downstream consumer
(`judge_*.py`, `build_*_queue.py`, `lib_v3ab.py`, the grading UI) breaks.
Incremental writing changes *when* bytes land, never *what* they are.

## 5. Verification (must return pass/fail, not assertions)

1. **Schema-identity gate** — run one cell before and after the change with a
   fixed prompts cache; the two output files must be byte-identical. This is
   the gate that proves §4 didn't disturb any downstream consumer.
2. **Kill test** — start a run, `kill` it mid-flight, assert the output file
   holds exactly the completed rows and the heartbeat reads `failed` or goes
   STALLED within the threshold.
3. **Resume test** — restart the killed run, assert it skips completed qids and
   the final file matches the uninterrupted run.
4. **Malformed-200 test** — unit test feeding `_attempt()` a 200 with a
   truncated body; assert it retries rather than raising, and that a
   permanently-bad body ends as a recorded error row rather than a dead run.
5. **Atomicity test** — hammer the heartbeat writer while a reader polls;
   assert the reader never sees invalid JSON.

Existing suite (176 tests as of `8c7550f`) must stay green.

## 6. Open questions for Jon

1. **Add usage/cost capture to the sonnet path** so its bar shows real cost
   too? It's a small addition to `run_answer_eval.py` and would retire the
   labeled *estimate* in `report-v4e.md` §11. Recommend yes, but it grows the
   slice — happy to defer.
2. **Split or bundle?** §2-3 (visibility) and §4 (crash resilience) are one
   change to one write path; splitting means editing it twice. Recommend
   bundling.
3. **HTML view?** The heartbeat data is already JSON on disk, so a static page
   is trivial to add later. Not proposed now — the terminal watcher works with
   detached jobs and needs no server. Flagging it as available.

## 7. Non-goals

- No new dependency (`tqdm`/`rich`).
- No change to prompt assembly, retrieval, the frozen judge, or any verdict
  file.
- No change to output-file schema (§4).
- Not binding or touching port 8000.

## 8. Sequencing

Built **before** the v5 grid. The v5 run — 64 generations across 4 variants and
2 arms — is exactly the run where "how's it going?" gets asked, and it doubles
as this slice's real-world validation.
