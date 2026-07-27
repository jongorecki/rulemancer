"""Build the reference-answer approval UI for the 31 drafted refdraft rows.

Reads evals/_refdraft_merged.jsonl (drafted question/answer/cited-rules rows)
and evals/questions.jsonl (the original mined gold rule ids, keyed by id),
merges them, and emits a self-contained HTML page to
data/parsed/refdraft_approval.html. Same pattern as
build_purerules_approval_ui.py / build_grading_ui.py: data baked into the
page, no server, decisions autosave to localStorage, Export downloads a JSON
of decisions.

These 31 rows are card-free rules questions that had no reference answer, so
they can't be used for accuracy evaluation until a human approves them. The
drafts were written by reading the Comprehensive Rules directly -- the
cr_quotes field carries the verbatim CR text for every cited rule so Jon can
check each claim without opening the CR file himself.

Per-row controls are Approve / Edit / Reject (three explicit decisions, not
collapsed into each other -- unlike the purerules UI's approve/rewrite/cut,
where "rewrite with no change" folds into "approve", here Jon may want to
mark a row Edited even if the text ends up matching the draft, e.g. after
reviewing the CR text he agrees but wants to file a note).

Run:  .venv/Scripts/python.exe evals/build_refdraft_approval_ui.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "evals" / "_refdraft_merged.jsonl"
QUESTIONS = ROOT / "evals" / "questions.jsonl"
OUT = ROOT / "data" / "parsed" / "refdraft_approval.html"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    if not DRAFTS.exists():
        raise SystemExit(f"missing drafts file: {DRAFTS}")
    if not QUESTIONS.exists():
        raise SystemExit(f"missing questions file: {QUESTIONS}")

    drafts = _load_jsonl(DRAFTS)
    questions_by_id = {q["id"]: q for q in _load_jsonl(QUESTIONS)}

    rows = []
    for d in drafts:
        orig = questions_by_id.get(d["id"], {})
        mined_gold = orig.get("gold", [])
        rows.append({
            "id": d["id"],
            "question": d["question"],
            "answer_gold": d["answer_gold"],
            "cited_rules": d.get("cited_rules", []),
            "cr_quotes": d.get("cr_quotes", {}),
            "gold_agrees": d.get("gold_agrees", True),
            "gold_note": d.get("gold_note", ""),
            "confidence": d.get("confidence", "high"),
            "uncertainty": d.get("uncertainty", ""),
            "mined_gold": mined_gold,
            "kind": orig.get("kind", ""),
        })

    payload = json.dumps({"rows": rows}, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("__PAYLOAD__", payload), encoding="utf-8")
    n_disagree = sum(1 for r in rows if not r["gold_agrees"])
    n_notconf = sum(1 for r in rows if r["confidence"] != "high")
    print(f"wrote {OUT} ({len(rows)} rows, {n_disagree} gold disagreements, "
          f"{n_notconf} not high-confidence)")
    print("Open it in a browser, decide each row, then click Export to "
          "download decisions.")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reference answers — approval</title>
<style>
  :root{
    --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --line:#2a2f3a;
    --text:#e8eaf0; --muted:#9aa3b2; --accent:#7aa2f7;
    --ok:#5ac87a; --partial:#e2b341; --wrong:#e2685f;
  }
  @media (prefers-color-scheme: light){
    :root{ --bg:#f5f6f8; --panel:#ffffff; --panel2:#eef0f4; --line:#d7dbe3;
      --text:#1b1f27; --muted:#5b6270; --accent:#3b5fc9;
      --ok:#1c8a4d; --partial:#9a6b00; --wrong:#c22e24; }
  }
  :root[data-theme="light"]{ --bg:#f5f6f8; --panel:#ffffff; --panel2:#eef0f4; --line:#d7dbe3;
    --text:#1b1f27; --muted:#5b6270; --accent:#3b5fc9;
    --ok:#1c8a4d; --partial:#9a6b00; --wrong:#c22e24; }
  :root[data-theme="dark"]{
    --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --line:#2a2f3a;
    --text:#e8eaf0; --muted:#9aa3b2; --accent:#7aa2f7;
    --ok:#5ac87a; --partial:#e2b341; --wrong:#e2685f;
  }
  *{box-sizing:border-box}
  html,body{max-width:100%;overflow-x:hidden}
  body{margin:0;background:var(--bg);color:var(--text);
    font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
  header{position:sticky;top:0;z-index:10;background:var(--panel);
    border-bottom:1px solid var(--line);padding:14px 20px}
  .bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;max-width:1100px;margin:0 auto}
  h1{font-size:18px;margin:0;font-weight:650;letter-spacing:-0.01em}
  .grow{flex:1}
  .count{color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}
  .count b{color:var(--text)}
  .progress-wrap{width:100%;max-width:1100px;margin:10px auto 0;height:6px;
    background:var(--panel2);border-radius:99px;overflow:hidden}
  .progress-bar{height:100%;background:var(--accent);border-radius:99px;
    transition:width .2s ease}
  .filters{display:flex;flex-wrap:wrap;gap:8px;max-width:1100px;margin:10px auto 0}
  .fbtn{background:var(--panel2);color:var(--text);border:1px solid var(--line);
    border-radius:999px;padding:5px 13px;font-size:12.5px;cursor:pointer;font-family:inherit}
  .fbtn:hover{border-color:var(--accent)}
  .fbtn[aria-pressed="true"]{background:var(--accent);color:#0d0f13;border-color:var(--accent);font-weight:650}
  .fbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  main{max-width:1100px;margin:0 auto;padding:20px}
  .intro{color:var(--muted);font-size:13.5px;margin:0 0 20px;
    background:var(--panel);border:1px solid var(--line);
    border-left:3px solid var(--accent);border-radius:8px;padding:14px 16px}
  .intro code{background:var(--panel2);padding:1px 5px;border-radius:4px;font-size:12.5px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:18px;margin-bottom:18px;border-left:4px solid var(--line)}
  .card[data-d="approve"]{border-left-color:var(--ok)}
  .card[data-d="edit"]{border-left-color:var(--partial)}
  .card[data-d="reject"]{border-left-color:var(--wrong);opacity:.75}
  .card.flag-disagree{outline:1px solid var(--wrong)}
  .card.flag-medium{outline:1px solid var(--partial)}
  .card.hidden-by-filter{display:none}
  .hd{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
  .id{font-weight:650;font-size:15px}
  .grow-h{flex:1}
  .tag{background:var(--panel2);border:1px solid var(--line);border-radius:999px;
    padding:2px 9px;font-size:11.5px;color:var(--muted);white-space:nowrap}
  .tag.conf-high{color:var(--ok);border-color:var(--ok)}
  .tag.conf-medium{color:var(--partial);border-color:var(--partial);font-weight:650}
  .tag.conf-low{color:var(--wrong);border-color:var(--wrong);font-weight:650}
  .tag.disagree{color:var(--wrong);border-color:var(--wrong);font-weight:650}
  h3{font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;
    color:var(--muted);margin:16px 0 6px;font-weight:650}
  .q{font-size:15.5px;font-weight:600;margin:0 0 4px}
  .body{white-space:pre-wrap}
  .rules-row{display:flex;flex-wrap:wrap;gap:16px;margin-top:10px}
  .rules-col{flex:1;min-width:220px}
  .ruleset{display:flex;flex-wrap:wrap;gap:6px}
  .rule-chip{background:var(--panel2);border:1px solid var(--line);border-radius:6px;
    padding:2px 8px;font-size:12.5px;font-family:ui-monospace,Consolas,monospace}
  .rule-chip.missing{border-color:var(--wrong);color:var(--wrong)}
  .rule-chip.extra{border-color:var(--partial);color:var(--partial)}
  .gold-note{color:var(--wrong);font-size:13px;margin-top:8px;font-style:italic}
  .uncertainty-note{color:var(--partial);font-size:13px;margin-top:8px;font-style:italic}
  .quotes{margin-top:10px}
  .quote{background:var(--panel2);border:1px solid var(--line);border-radius:7px;
    padding:10px 12px;margin-bottom:8px;overflow-x:auto}
  .quote b{font-family:ui-monospace,Consolas,monospace;font-size:13px;color:var(--accent)}
  .quote-text{white-space:pre-wrap;font-size:13px;margin-top:5px;color:var(--text);
    word-break:break-word}
  .acts{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
  button{background:var(--panel2);color:var(--text);border:1px solid var(--line);
    border-radius:7px;padding:7px 14px;font-size:13.5px;cursor:pointer;
    font-family:inherit;transition:border-color .12s,background .12s}
  button:hover{border-color:var(--accent)}
  button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  button[aria-pressed="true"]{background:var(--accent);color:#0d0f13;
    border-color:var(--accent);font-weight:600}
  button.btn-approve[aria-pressed="true"]{background:var(--ok);border-color:var(--ok)}
  button.btn-edit[aria-pressed="true"]{background:var(--partial);border-color:var(--partial)}
  button.btn-reject[aria-pressed="true"]{background:var(--wrong);border-color:var(--wrong)}
  .edit{display:none;margin-top:14px}
  .card[data-d="edit"] .edit{display:block}
  label{display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;
    color:var(--muted);margin:12px 0 5px;font-weight:650}
  textarea{width:100%;background:var(--panel2);color:var(--text);
    border:1px solid var(--line);border-radius:7px;padding:10px 12px;
    font:inherit;line-height:1.55;resize:vertical}
  textarea:focus-visible{outline:2px solid var(--accent);outline-offset:1px;
    border-color:var(--accent)}
  .notes-wrap{margin-top:14px}
  .empty{color:var(--muted);text-align:center;padding:60px 20px}
  footer{max-width:1100px;margin:0 auto;padding:0 20px 60px;color:var(--muted);font-size:13px}
  @media (max-width:640px){.bar{gap:8px}h1{font-size:16px}main{padding:14px}.rules-row{gap:10px}}
</style></head><body>
<header><div class="bar">
  <h1>Reference answers — approval</h1>
  <span class="grow"></span>
  <span class="count" id="count">—</span>
  <button id="export">Export decisions</button>
  <button id="reset">Reset</button>
</div>
<div class="progress-wrap"><div class="progress-bar" id="progressBar" style="width:0%"></div></div>
<div class="filters" id="filters"></div>
</header>
<main>
  <p class="intro">31 drafted reference answers for card-free rules questions.
  Each card shows the question, the drafted answer, and the verbatim CR text for
  every cited rule so you can check the claim without opening the CR file.
  <b>Approve</b> accepts the draft as written. <b>Edit</b> opens an editable answer
  box pre-filled with the draft. <b>Reject</b> drops the row. 4 rows disagree with
  the originally mined gold rule ids (outlined red) and 1 row is only
  medium-confidence (outlined amber) — review those first. Decisions autosave in
  this browser; click <code>Export decisions</code> when you're done.</p>
  <div id="list"></div>
</main>
<footer id="foot"></footer>
<script>
const DATA = __PAYLOAD__;
const KEY = "refdraft_approval_v1";
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); }
catch(e){ state = {}; console.warn("could not read saved state", e); }

let activeFilter = null; // 'disagree' | 'notconf' | 'undecided' | null

const esc = s => String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

function save(){
  try { localStorage.setItem(KEY, JSON.stringify(state)); }
  catch(e){ console.warn("could not save", e); }
}

function entry(id){
  if(!state[id]) state[id] = {decision:null, answer:null, notes:""};
  return state[id];
}

function ruleSetDiff(cited, mined){
  const citedSet = new Set(cited||[]);
  const minedSet = new Set(mined||[]);
  const missing = (mined||[]).filter(r=>!citedSet.has(r)); // in mined, not in cited
  const extra = (cited||[]).filter(r=>!minedSet.has(r));   // in cited, not in mined
  return {missing, extra};
}

function quotesHtml(row){
  const rules = row.cited_rules || [];
  if(!rules.length) return '<p class="body" style="color:var(--muted)">No rules cited.</p>';
  return '<div class="quotes">' + rules.map(r => {
    const q = (row.cr_quotes && row.cr_quotes[r]) || "(quote not found)";
    return `<div class="quote"><b>CR ${esc(r)}</b><div class="quote-text">${esc(q)}</div></div>`;
  }).join('') + '</div>';
}

function render(){
  const list = document.getElementById("list");
  const rows = DATA.rows || [];
  if(!rows.length){
    list.innerHTML = '<p class="empty">No rows to review.</p>';
    return;
  }
  list.innerHTML = "";
  for(const r of rows){
    const st = entry(r.id);
    const answer = st.answer != null ? st.answer : r.answer_gold;
    const diff = ruleSetDiff(r.cited_rules, r.mined_gold);
    const isDisagree = !r.gold_agrees;
    const isNotConf = r.confidence !== "high";
    const el = document.createElement("div");
    el.className = "card";
    el.dataset.id = r.id;
    if(st.decision) el.dataset.d = st.decision;
    if(isDisagree) el.classList.add("flag-disagree");
    if(isNotConf) el.classList.add("flag-medium");
    el.dataset.disagree = isDisagree ? "1" : "0";
    el.dataset.notconf = isNotConf ? "1" : "0";
    el.dataset.decided = st.decision ? "1" : "0";

    const confClass = r.confidence === "high" ? "conf-high"
      : r.confidence === "medium" ? "conf-medium" : "conf-low";

    el.innerHTML = `
      <div class="hd">
        <span class="id">${esc(r.id)}</span>
        <span class="grow-h"></span>
        <span class="tag ${confClass}">confidence: ${esc(r.confidence)}</span>
        ${isDisagree ? '<span class="tag disagree">gold disagreement</span>' : ""}
      </div>
      <p class="q">${esc(r.question)}</p>
      <h3>Drafted answer</h3>
      <div class="body" data-f="answer">${esc(answer)}</div>
      ${r.uncertainty ? `<p class="uncertainty-note">Uncertainty: ${esc(r.uncertainty)}</p>` : ""}
      ${r.gold_note ? `<p class="gold-note">Gold note: ${esc(r.gold_note)}</p>` : ""}
      <div class="rules-row">
        <div class="rules-col">
          <h3>Cited rules (drafted)</h3>
          <div class="ruleset">${(r.cited_rules||[]).map(c=>{
            const cls = diff.extra.includes(c) ? "rule-chip extra" : "rule-chip";
            return `<span class="${cls}">${esc(c)}</span>`;
          }).join('') || '<span style="color:var(--muted);font-size:12.5px">none</span>'}</div>
        </div>
        <div class="rules-col">
          <h3>Originally mined gold ids</h3>
          <div class="ruleset">${(r.mined_gold||[]).map(c=>{
            const cls = diff.missing.includes(c) ? "rule-chip missing" : "rule-chip";
            return `<span class="${cls}">${esc(c)}</span>`;
          }).join('') || '<span style="color:var(--muted);font-size:12.5px">none</span>'}</div>
        </div>
      </div>
      <h3>CR quotes</h3>
      ${quotesHtml(r)}
      <div class="acts">
        <button class="btn-approve" data-a="approve" aria-pressed="${st.decision==="approve"}">Approve</button>
        <button class="btn-edit" data-a="edit" aria-pressed="${st.decision==="edit"}">Edit</button>
        <button class="btn-reject" data-a="reject" aria-pressed="${st.decision==="reject"}">Reject</button>
      </div>
      <div class="edit">
        <label for="a-${esc(r.id)}">Edited answer</label>
        <textarea id="a-${esc(r.id)}" rows="5" data-e="answer">${esc(answer)}</textarea>
      </div>
      <div class="notes-wrap">
        <label for="n-${esc(r.id)}">Notes</label>
        <textarea id="n-${esc(r.id)}" rows="2" data-e="notes" placeholder="optional">${esc(st.notes||"")}</textarea>
      </div>`;

    el.querySelectorAll("[data-a]").forEach(b=>{
      b.addEventListener("click", ()=>{
        const st2 = entry(r.id);
        st2.decision = (st2.decision === b.dataset.a) ? null : b.dataset.a;
        save(); render();
      });
    });
    el.querySelector('[data-e="answer"]').addEventListener("input", (ev)=>{
      const st2 = entry(r.id);
      st2.answer = ev.target.value;
      el.querySelector('[data-f="answer"]').textContent = ev.target.value;
      save(); tally();
    });
    el.querySelector('[data-e="notes"]').addEventListener("input", (ev)=>{
      const st2 = entry(r.id);
      st2.notes = ev.target.value;
      save();
    });

    list.appendChild(el);
  }
  applyFilter();
  tally();
}

function applyFilter(){
  const cards = document.querySelectorAll("#list .card");
  cards.forEach(c=>{
    let show = true;
    if(activeFilter === "disagree") show = c.dataset.disagree === "1";
    else if(activeFilter === "notconf") show = c.dataset.notconf === "1";
    else if(activeFilter === "undecided") show = c.dataset.decided === "0";
    c.classList.toggle("hidden-by-filter", !show);
  });
}

function tally(){
  const rows = DATA.rows || [];
  let a=0,e=0,x=0;
  for(const r of rows){
    const st = state[r.id];
    if(!st || !st.decision) continue;
    if(st.decision==="approve") a++;
    else if(st.decision==="edit") e++;
    else if(st.decision==="reject") x++;
  }
  const done = a+e+x;
  document.getElementById("count").innerHTML =
    `<b>${done}</b>/${rows.length} decided &nbsp;·&nbsp; ${a} approved · ${e} edited · ${x} rejected`;
  document.getElementById("progressBar").style.width =
    (rows.length ? (done/rows.length*100) : 0) + "%";
}

document.getElementById("export").addEventListener("click", ()=>{
  const out = [];
  for(const r of (DATA.rows||[])){
    const st = state[r.id] || {};
    out.push({
      id: r.id,
      decision: st.decision || null,
      edited_answer: st.answer != null ? st.answer : r.answer_gold,
      notes: st.notes || ""
    });
  }
  const blob = new Blob([JSON.stringify(out,null,2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "refdraft_decisions.json";
  a.click();
  URL.revokeObjectURL(a.href);
});

document.getElementById("reset").addEventListener("click", ()=>{
  if(confirm("Clear all decisions and edits in this browser?")){
    state = {}; localStorage.removeItem(KEY); render();
  }
});

const rows0 = DATA.rows || [];
const nDisagree = rows0.filter(r=>!r.gold_agrees).length;
const nNotConf = rows0.filter(r=>r.confidence !== "high").length;
document.getElementById("filters").innerHTML = `
  <button class="fbtn" data-flt="disagree">Gold disagreements (${nDisagree})</button>
  <button class="fbtn" data-flt="notconf">Not high confidence (${nNotConf})</button>
  <button class="fbtn" data-flt="undecided">Undecided</button>
  <button class="fbtn" data-flt="">Show all</button>
`;
document.querySelectorAll("#filters [data-flt]").forEach(b=>{
  b.addEventListener("click", ()=>{
    const f = b.dataset.flt || null;
    activeFilter = (activeFilter === f && f) ? null : f;
    document.querySelectorAll("#filters [data-flt]").forEach(x=>
      x.setAttribute("aria-pressed", x.dataset.flt === (activeFilter||"") && !!activeFilter));
    applyFilter();
  });
});

document.getElementById("foot").textContent =
  rows0.length + " rows total · " + nDisagree + " gold disagreements · " +
  nNotConf + " not high-confidence.";

render();
</script></body></html>
"""


if __name__ == "__main__":
    main()
