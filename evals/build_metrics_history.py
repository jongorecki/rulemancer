"""Collect every number we own about every judged arm into one comparable table.

WHY THIS EXISTS. Jon, 2026-07-26: he wants cost, accuracy, weighting, tokens and
config for every arm and iteration **side by side across time**, in one page, to
answer a specific question -- *is it time for the full RulesGuru run on the entire
dataset?* Numbers currently live scattered across `docs/results-*.md`,
`docs/report-*.md` and handoff prose, each written at a different moment against a
file that may have moved since.

THE TWO THINGS THAT MAKE THIS HONEST RATHER THAN IMPRESSIVE:

**1. Arms are not all comparable, so the table says which are.** Different arms
ran on different question sets (the v3 150, a hard 54, an easy 50), so a single
ranked list would invite comparisons that mean nothing. Every arm gets a
`qset` fingerprint -- the first 8 hex of a SHA-256 over its sorted question ids --
and arms sharing a fingerprint are the only ones directly comparable. This is
computed from the ids themselves, not inferred from a filename or a count.

**2. Every number carries what produced it.** This repo has already shipped a
results doc that disagreed with its own verdict file inside one commit, because a
number was read at one time and published at another. So each row records its
source files, their mtimes, the judging model and prompt digest, and whether the
accuracy is auto-judged or human-corrected. A row you cannot trace is a row you
cannot use to make a go/no-go call.

**KNOWN PROVENANCE GAP, surfaced rather than papered over.** Verdict files do not
record which answers file they judged -- the link is filename convention
(`verdicts_X.json` <-> `answers/X.json`) plus a small alias table. Every row
reports how its join was made (`exact` / `alias` / `prefix` / `unmatched`), so a
guessed join is visible as a guess. Rows that cannot be joined still appear, with
accuracy and no cost.

COST IS COMPUTED, NOT ASSUMED. Token ratios are not a cost result -- opus costs
more per token than sonnet, so fewer tokens does not establish which is cheaper.
Per-MTok prices below come from the `claude-api` skill (checked 2026-07-26), never
from recall, and cache-tier multipliers are applied separately because a cached
read costs a tenth of a fresh input token. Sonnet 5 is dual-priced: its
introductory rate runs through 2026-08-31, so both are shown and the arm is
costed at BOTH, since which one applies depends on when you re-run it.

Usage:
    python evals/build_metrics_history.py
    python evals/build_metrics_history.py --json evals/_metrics_history.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import weighted_score as ws

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
ANSWERS = EVALS / "answers"

# Per-MTok (input, output). Source: claude-api skill, checked 2026-07-26.
# Never fill these in from memory -- reread the skill when they may have moved.
PRICING = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-sonnet-5": (3.00, 15.00),          # standard rate
    "claude-sonnet-5@intro": (2.00, 10.00),    # introductory, through 2026-08-31
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
SONNET_INTRO_ENDS = "2026-08-31"
CACHE_READ_MULT = 0.10    # cached input bills at ~0.1x
CACHE_WRITE_MULT = 1.25   # 5-minute TTL write premium

# Verdict stems whose answers file is named differently. Kept explicit and small:
# a fuzzy matcher that silently picks the wrong answers file would attach one
# arm's cost to another arm's accuracy, which is worse than reporting no cost.
ALIASES = {
    "derivability_B": "derivability_B_goldonly",
    "derivability_B_human": "derivability_B_goldonly",  # same answers, human-regraded
    "derivability_C": "derivability_C_failures",
    "rulesguru_sonnet": "rulesguru_answers",            # verified: model=claude-sonnet-5, n=150
}


def _mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).astimezone().isoformat(timespec="minutes")


def _ids_of(path: Path) -> frozenset[str] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rows = raw if isinstance(raw, list) else list(raw.values()) if isinstance(raw, dict) else []
    ids = {r["id"] for r in rows if isinstance(r, dict) and "id" in r}
    return frozenset(ids) or None


def resolve_answers(stem: str, want: frozenset[str]) -> tuple[Path | None, str]:
    """(answers path, how the join was made) -- and the join is VERIFIED.

    Filename convention alone is a guess: verdict files do not record which
    answers file they judged. So every candidate is confirmed by comparing
    question-id sets against the verdict's, and a name that matches while the ids
    do not is reported as `name-matched-ids-differ` rather than being used. That
    turns "probably the right file" into a checked fact, which is the difference
    between a cost figure you can publish and one you can't.
    """
    candidates: list[tuple[Path, str]] = []
    exact = ANSWERS / f"{stem}.json"
    if exact.exists():
        candidates.append((exact, "exact"))
    if stem in ALIASES and (p := ANSWERS / f"{ALIASES[stem]}.json").exists():
        candidates.append((p, "alias"))
    for p in sorted(ANSWERS.glob(f"{stem}*.json")):
        if not p.name.startswith("_"):
            candidates.append((p, "prefix"))

    named_but_wrong = False
    for path, how in candidates:
        got = _ids_of(path)
        if got == want:
            return path, how
        if got is not None:
            named_but_wrong = True

    # No name matched, or the named file held different questions. Fall back to
    # an id-set search across every answers file -- a slower but strictly
    # stronger join, since it is decided by the data rather than the filename.
    matches = [p for p in sorted(ANSWERS.glob("*.json"))
               if not p.name.startswith("_") and _ids_of(p) == want]
    if len(matches) == 1:
        return matches[0], "id-match"
    if len(matches) > 1:
        return None, f"ambiguous ({len(matches)} files share these ids)"
    return None, "name-matched-ids-differ" if named_but_wrong else "unmatched"


def cost_of(rows: list[dict], model: str) -> dict:
    """Per-question cost, tokens, and cache behaviour. Returns {} if unpriceable."""
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    n = 0
    for r in rows:
        u = r.get("usage") or {}
        if not u:
            continue
        n += 1
        tot["input"] += u.get("input_tokens", 0) or 0
        tot["output"] += u.get("output_tokens", 0) or 0
        tot["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        tot["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
    if not n:
        return {}

    def price(key: str) -> float | None:
        if key not in PRICING:
            return None
        pin, pout = PRICING[key]
        return (
            tot["input"] * pin
            + tot["cache_write"] * pin * CACHE_WRITE_MULT
            + tot["cache_read"] * pin * CACHE_READ_MULT
            + tot["output"] * pout
        ) / 1_000_000 / n

    out = {
        "n_costed": n,
        "in_per_q": tot["input"] / n,
        "out_per_q": tot["output"] / n,
        "cache_read_per_q": tot["cache_read"] / n,
        "cache_write_per_q": tot["cache_write"] / n,
        "cost_per_q": price(model),
        "priced_as": model if model in PRICING else None,
    }
    # Sonnet's intro rate expires; show both so a re-run decision uses the right one.
    if model == "claude-sonnet-5":
        out["cost_per_q_intro"] = price("claude-sonnet-5@intro")
        out["intro_ends"] = SONNET_INTRO_ENDS
    return out


def collect() -> dict:
    arms, skipped = [], []
    for vpath in sorted(list(EVALS.glob("*verdicts*.json"))):
        try:
            data = json.loads(vpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            skipped.append(f"{vpath.name}: unreadable ({e})")
            continue
        if not isinstance(data, dict):
            # Some *verdicts*.json files are bare arrays of hand-graded rows with
            # no summary at all (e.g. answer_verdicts.json). Nothing to score.
            skipped.append(f"{vpath.name}: bare array, no summary")
            continue
        summary = data.get("summary") or {}
        entries = data.get("entries") or []
        if not summary.get("by_level_counts") or not entries:
            skipped.append(f"{vpath.name}: no summary.by_level_counts")
            continue

        stem = vpath.stem.replace("verdicts_", "").replace("h2h_", "h2h_")
        if vpath.stem.startswith("verdicts_"):
            stem = vpath.stem[len("verdicts_"):]

        ids = sorted(e["id"] for e in entries if "id" in e)
        qset = hashlib.sha256("|".join(ids).encode()).hexdigest()[:8]

        try:
            counts = ws.normalize_counts(summary["by_level_counts"])
            flat = ws.score(counts, ws.WEIGHT_SCHEMES["flat"]["weights"])
            weighted = ws.score(counts, ws.WEIGHT_SCHEMES["corner-half"]["weights"])
        except ws.ScoreError as e:
            skipped.append(f"{vpath.name}: {e}")
            continue

        apath, join = resolve_answers(stem, frozenset(ids))
        cfg, cost = {}, {}
        if apath is not None:
            raw = json.loads(apath.read_text(encoding="utf-8"))
            # Answers files come in two shapes: a list of rows, or a dict keyed
            # by question id. Normalize rather than assume, so a shape mismatch
            # can't silently drop an arm's cost.
            rows = raw if isinstance(raw, list) else list(raw.values())
            rows = [r for r in rows if isinstance(r, dict)]
            first = rows[0] if rows else {}
            cfg = {
                "model": first.get("model"),
                "effort": first.get("effort"),
                "rewrite_version": first.get("rewrite_version"),
                "ruling_query_mode": first.get("ruling_query_mode"),
                "system_version": first.get("system_version"),
                "n_answers": len(rows),
            }
            cost = cost_of(rows, first.get("model") or "")

        arms.append({
            "arm": stem,
            "qset": qset,
            "n": summary.get("n_total") or len(entries),
            "accuracy_flat": flat,
            "accuracy_weighted": weighted,
            "accuracy_auto": summary.get("accuracy_auto"),
            "human_corrected": bool(summary.get("human_overturned")),
            "grader": summary.get("grader"),
            "by_level": {k: {"correct": c, "n": n_} for k, (c, n_) in counts.items()},
            "judge_model": summary.get("judge_model"),
            "judge_digest": summary.get("judge_prompt_sha256"),
            "config": cfg,
            "cost": cost,
            "provenance": {
                "verdicts": vpath.relative_to(REPO).as_posix(),
                "verdicts_mtime": _mtime(vpath),
                "answers": apath.relative_to(REPO).as_posix() if apath else None,
                "answers_mtime": _mtime(apath) if apath else None,
                "join": join,
            },
        })

    arms.sort(key=lambda a: (a["qset"], -(a["accuracy_flat"] or 0)))
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "arms": arms,
        "skipped": skipped,
        "pricing": {"per_mtok": PRICING, "cache_read_mult": CACHE_READ_MULT,
                    "cache_write_mult": CACHE_WRITE_MULT,
                    "sonnet_intro_ends": SONNET_INTRO_ENDS,
                    "source": "claude-api skill, checked 2026-07-26"},
        "current_config": {
            "GEN_MODEL": "claude-opus-5", "GEN_EFFORT": "low", "REWRITE_N": 3,
            "REWRITE_MODEL": "claude-haiku-4-5", "REWRITE_FUSION_DEPTH": 100,
            "TOP_K": 15, "TOP_N": 5, "COSINE_FLOOR": 0.38,
            "note": ("Current values read from source, NOT what each historical arm ran. "
                     "Per-run retrieval config is not recorded in the answers files."),
        },
        "weighting": {
            "scheme": "corner-half", "weights": ws.WEIGHT_SCHEMES["corner-half"]["weights"],
            "ruled_by": "Jon, 2026-07-26",
        },
    }


FULL_CORPUS = 1409  # RulesGuru questions imported (docs/report-rulesguru-full-import.md)

# Colors are the dataviz reference palette, unchanged. Only a single accent plus
# the reserved status steps are used -- no categorical series -- so there is no
# multi-hue CVD adjacency to validate here.
HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rulemancer — metrics history</title>
<style>
:root{color-scheme:dark;
 --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
 --grid:#2c2c2a; --rule:#383835; --accent:#3987e5;
 --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --crit:#d03b3b;
 --ring:rgba(255,255,255,.10);
 --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:40px;}
:root[data-theme=light]{color-scheme:light;
 --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
 --grid:#e1e0d9; --rule:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);}
@media(prefers-color-scheme:light){:root:not([data-theme=dark]){color-scheme:light;
 --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e;
 --grid:#e1e0d9; --rule:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);}}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
 font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;}
.wrap{max-width:1240px;margin:0 auto;padding:var(--s5) var(--s4) var(--s6)}
header{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:baseline;justify-content:space-between;
 margin-bottom:var(--s2)}
h1{font-size:1.5rem;margin:0;letter-spacing:-.01em}
h2{font-size:1.0rem;margin:var(--s5) 0 var(--s2);letter-spacing:.04em;text-transform:uppercase;
 color:var(--ink2)}
.sub{color:var(--ink2);margin:0 0 var(--s5);max-width:68ch}
.meta{color:var(--muted);font-size:.8rem}
button{font:inherit;color:var(--ink2);background:var(--surface);border:1px solid var(--ring);
 border-radius:8px;padding:6px 12px;cursor:pointer}
button:hover{color:var(--ink)}
button:focus-visible,th[tabindex]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:var(--s4)}
.tiles{display:grid;gap:var(--s3);grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
 margin-bottom:var(--s5)}
.tile .k{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}
.tile .v{font-size:1.9rem;line-height:1.15;margin:var(--s1) 0 2px;font-weight:600}
.tile .n{color:var(--ink2);font-size:.82rem}
.decision{border-left:3px solid var(--accent)}
.decision .v{color:var(--accent)}
.scroll{overflow-x:auto;border:1px solid var(--ring);border-radius:12px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{text-align:right;padding:9px var(--s3);border-bottom:1px solid var(--grid);white-space:nowrap}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--surface)}
thead th{color:var(--muted);font-weight:600;font-size:.72rem;text-transform:uppercase;
 letter-spacing:.05em;border-bottom:1px solid var(--rule);cursor:pointer;user-select:none}
thead th::after{content:"";opacity:.5}
thead th[aria-sort=ascending]::after{content:" \\2191";opacity:1}
thead th[aria-sort=descending]::after{content:" \\2193";opacity:1}
tbody tr:hover{background:color-mix(in oklab,var(--accent) 8%,transparent)}
tbody tr:last-child td{border-bottom:none}
.num{font-variant-numeric:tabular-nums}
.dim{color:var(--muted)}
.badge{display:inline-block;font-size:.68rem;padding:1px 7px;border-radius:999px;
 border:1px solid var(--ring);color:var(--ink2);vertical-align:1px}
.b-good{color:var(--good);border-color:color-mix(in oklab,var(--good) 45%,transparent)}
.b-warn{color:var(--warn);border-color:color-mix(in oklab,var(--warn) 45%,transparent)}
.b-crit{color:var(--crit);border-color:color-mix(in oklab,var(--crit) 45%,transparent)}
.grp{display:flex;flex-wrap:wrap;gap:var(--s3);align-items:baseline;margin:var(--s5) 0 var(--s2)}
.grp h3{font-size:.95rem;margin:0}
.note{color:var(--ink2);font-size:.85rem;max-width:74ch}
.empty{padding:var(--s6);text-align:center;color:var(--muted)}
footer{margin-top:var(--s6);padding-top:var(--s4);border-top:1px solid var(--grid);
 color:var(--muted);font-size:.8rem;max-width:80ch}
footer code{color:var(--ink2)}
ul{margin:var(--s2) 0;padding-left:1.1rem}li{margin:3px 0}
@media(max-width:640px){.wrap{padding:var(--s4) var(--s3)}h1{font-size:1.25rem}.tile .v{font-size:1.5rem}}
</style></head><body><div class="wrap">
<header>
 <div><h1>Rulemancer — metrics history</h1>
 <p class="meta">Generated __GENERATED__ · every number read from its file at build time</p></div>
 <button id="themeBtn" type="button" aria-label="Toggle colour theme">Theme</button>
</header>
<p class="sub">Every judged arm we own, side by side, grouped by the question set it
actually ran on. Arms in different groups are <strong>not</strong> comparable — different
questions. The question this exists to answer: is it time for the full RulesGuru run?</p>
<div id="app"></div>
<footer id="foot"></footer>
</div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const pct = v => v==null ? '—' : (v*100).toFixed(1)+'%';
const usd = v => v==null ? '—' : '$'+v.toFixed(5);
const int = v => v==null ? '—' : Math.round(v).toLocaleString();
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const JOIN = {
  'exact':['b-good','verified'], 'alias':['b-good','verified'], 'id-match':['b-good','verified by ids'],
  'prefix':['b-warn','name-matched'], 'unmatched':['b-crit','no answers file'],
  'name-matched-ids-differ':['b-crit','name matched, ids differ']
};
const joinBadge = j => {
  const hit = JOIN[j] || (j.startsWith('ambiguous') ? ['b-crit', j] : ['b-warn', j]);
  return `<span class="badge ${hit[0]}" title="${esc(j)}">${esc(hit[1])}</span>`;
};

// The decision number: measured cost per question x the full corpus.
const costed = D.arms.filter(a => a.cost && a.cost.cost_per_q != null);
const cur = costed.filter(a => (a.config||{}).model === 'claude-opus-5' && (a.config||{}).effort === 'low');
const basis = cur.length ? cur : costed;
const lo = basis.length ? Math.min(...basis.map(a=>a.cost.cost_per_q)) : null;
const hi = basis.length ? Math.max(...basis.map(a=>a.cost.cost_per_q)) : null;
const N = D.full_corpus;

const tiles = [
  {k:'Full RulesGuru run', v: lo==null?'—':('$'+(lo*N).toFixed(0)+'–'+(hi*N).toFixed(0)),
   n:`${N.toLocaleString()} questions at the measured cost/question of the shipped config`
      + (cur.length?` (${cur.length} opus-5/low arms)`:' (no opus-5/low arm — using all priced arms)'),
   cls:'decision'},
  {k:'Cost per question', v: lo==null?'—':usd(lo), n: lo==null?'no priced arm':`to ${usd(hi)} across those arms`},
  {k:'Arms tracked', v: String(D.arms.length),
   n:`${new Set(D.arms.map(a=>a.qset)).size} distinct question sets · ${D.skipped.length} files skipped`},
  {k:'Weighting', v:'Corner ×0.5', n:`flat across L0–L3 · ruled by ${esc(D.weighting.ruled_by)}`},
];

const groups = {};
D.arms.forEach(a => (groups[a.qset] ||= []).push(a));
const order = Object.entries(groups).sort((a,b)=>b[1].length-a[1].length || b[1][0].n-a[1][0].n);

const COLS = [
  ['Arm', a=>`${esc(a.arm)} ${a.human_corrected?'<span class="badge b-good">human-corrected</span>':''}`, a=>a.arm],
  ['Model', a=>`<span class="dim">${esc((a.config||{}).model||'—')}${(a.config||{}).effort?' / '+esc(a.config.effort):''}</span>`, a=>(a.config||{}).model||''],
  ['Flat', a=>`<span class="num">${pct(a.accuracy_flat)}</span>`, a=>a.accuracy_flat],
  ['Weighted', a=>`<span class="num">${pct(a.accuracy_weighted)}</span>`, a=>a.accuracy_weighted],
  ['Auto', a=>`<span class="num dim">${pct(a.accuracy_auto)}</span>`, a=>a.accuracy_auto??-1],
  ['$/question', a=>`<span class="num">${usd((a.cost||{}).cost_per_q)}</span>`, a=>(a.cost||{}).cost_per_q??-1],
  ['In tok', a=>`<span class="num dim">${int((a.cost||{}).in_per_q)}</span>`, a=>(a.cost||{}).in_per_q??-1],
  ['Out tok', a=>`<span class="num dim">${int((a.cost||{}).out_per_q)}</span>`, a=>(a.cost||{}).out_per_q??-1],
  ['Judge', a=>`<span class="dim" title="prompt digest ${esc(a.judge_digest||'?')}">${esc(a.judge_model||'—')}</span>`, a=>a.judge_model||''],
  ['Join', a=>joinBadge(a.provenance.join), a=>a.provenance.join],
  ['Run', a=>`<span class="dim">${esc((a.provenance.verdicts_mtime||'').slice(0,10))}</span>`, a=>a.provenance.verdicts_mtime||''],
];

function table(rows, key){
  const head = COLS.map((c,i)=>`<th tabindex="0" role="columnheader" data-c="${i}" data-k="${key}">${c[0]}</th>`).join('');
  const body = rows.map(a=>`<tr>${COLS.map(c=>`<td>${c[1](a)}</td>`).join('')}</tr>`).join('');
  return `<div class="scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function render(){
  if(!D.arms.length){
    document.getElementById('app').innerHTML =
      '<div class="card empty"><strong>No scorable arms found.</strong><br>'+
      'Every verdict file lacked a <code>summary.by_level_counts</code>. '+
      'Re-run the judge, then rebuild.</div>';
    return;
  }
  let html = `<div class="tiles">${tiles.map(t=>
    `<div class="card tile ${t.cls||''}"><div class="k">${esc(t.k)}</div>
     <div class="v num">${t.v}</div><div class="n">${t.n}</div></div>`).join('')}</div>`;

  html += `<h2>Arms by question set</h2>`;
  order.forEach(([qset, rows], gi) => {
    html += `<div class="grp"><h3>${rows[0].n} questions</h3>
      <span class="meta">fingerprint <code>${esc(qset)}</code> — ${rows.length} arm${rows.length>1?'s':''}, directly comparable to each other and to nothing else</span></div>`;
    html += table(rows, 'g'+gi);
  });
  document.getElementById('app').innerHTML = html;

  document.querySelectorAll('th[data-c]').forEach(th => {
    const go = () => sort(th);
    th.addEventListener('click', go);
    th.addEventListener('keydown', e => { if(e.key==='Enter'||e.key===' '){ e.preventDefault(); go(); }});
  });
}

function sort(th){
  const tbl = th.closest('table'), ci = +th.dataset.c;
  const asc = th.getAttribute('aria-sort') !== 'ascending';
  tbl.querySelectorAll('th').forEach(o=>o.removeAttribute('aria-sort'));
  th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
  const tb = tbl.tBodies[0];
  const rows = [...tb.rows];
  rows.sort((x,y)=>{
    const a = x.cells[ci].textContent.trim(), b = y.cells[ci].textContent.trim();
    const na = parseFloat(a.replace(/[$%,]/g,'')), nb = parseFloat(b.replace(/[$%,]/g,''));
    const cmp = (!isNaN(na)&&!isNaN(nb)) ? na-nb : a.localeCompare(b);
    return asc ? cmp : -cmp;
  });
  rows.forEach(r=>tb.appendChild(r));
}

document.getElementById('foot').innerHTML = `
 <strong>How to read this.</strong>
 <ul>
  <li><strong>Flat vs Weighted.</strong> Flat is how every prior result in this repo is stated.
      Weighted applies Jon's ruling — flat across L0–L3, Corner Case ×0.5. Flat is the number to quote.</li>
  <li><strong>Auto</strong> is the judge's own score before human regrading; where it differs from Flat,
      a human overturned rows. The judge is <em>nondeterministic</em> (~1 verdict flip per 100 rows),
      so treat ±1–2 rows as noise before reading a difference as real.</li>
  <li><strong>$/question</strong> is computed from recorded token usage at
      ${esc(D.pricing.source)}: input, output, cache-write ×${D.pricing.cache_write_mult},
      cache-read ×${D.pricing.cache_read_mult}. Sonnet 5 is shown at its standard rate —
      its introductory rate runs to ${esc(D.pricing.sonnet_intro_ends)}.</li>
  <li><strong>Join</strong> says how an arm's accuracy was linked to its cost. Verdict files do not
      record which answers file they judged, so each link is confirmed by comparing question-id sets.
      Anything not marked <span class="badge b-good">verified</span> should not be used for a cost claim.</li>
  <li><strong>Retrieval config is not per-arm.</strong> The answers files record model and rewrite
      version but not TOP_K / TOP_N / COSINE_FLOOR. Current values —
      TOP_K ${D.current_config.TOP_K}, TOP_N ${D.current_config.TOP_N},
      COSINE_FLOOR ${D.current_config.COSINE_FLOOR}, REWRITE_N ${D.current_config.REWRITE_N} —
      describe the code today, not what each historical arm ran.</li>
 </ul>`;

const btn = document.getElementById('themeBtn');
btn.addEventListener('click', () => {
  const dark = document.documentElement.getAttribute('data-theme') !== 'light';
  document.documentElement.setAttribute('data-theme', dark ? 'light' : 'dark');
});
render();
</script></body></html>
"""


def render_html(data: dict) -> str:
    return (HTML
            .replace("__GENERATED__", data["generated_at"])
            .replace("__DATA__", json.dumps(data).replace("</", "<\\/")))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", dest="json_out", default="evals/_metrics_history.json")
    ap.add_argument("--html", dest="html_out", default="evals/metrics_history.html")
    args = ap.parse_args()

    data = collect()
    data["full_corpus"] = FULL_CORPUS
    Path(args.json_out).write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    Path(args.html_out).write_text(render_html(data), encoding="utf-8")
    print(f"wrote {args.html_out}")
    print(f"wrote {args.json_out}: {len(data['arms'])} arms, "
          f"{len({a['qset'] for a in data['arms']})} question sets, "
          f"{len(data['skipped'])} skipped")
    groups: dict[str, list] = {}
    for a in data["arms"]:
        groups.setdefault(a["qset"], []).append(a)
    for qset, members in groups.items():
        print(f"\n  qset {qset}  n={members[0]['n']}  ({len(members)} arms)")
        for a in members:
            c = a["cost"].get("cost_per_q")
            cost = f"${c:.5f}" if c else "  --   "
            print(f"    {a['arm']:<34} flat {a['accuracy_flat']:>6.1%}  "
                  f"wtd {a['accuracy_weighted']:>6.1%}  {cost}  "
                  f"{a['config'].get('model') or '?'}/{a['config'].get('effort') or '?'}"
                  f"  [{a['provenance']['join']}]")
    for s in data["skipped"]:
        print(f"  SKIP {s}")


if __name__ == "__main__":
    main()
