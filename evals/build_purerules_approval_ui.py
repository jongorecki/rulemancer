"""Build the pure-rules eval approval UI (docs/HANDOFF-development.md measurement gap).

Reads evals/purerules_candidates.json and emits a self-contained HTML page to
data/parsed/purerules_approval.html. Same pattern as build_rulesguru_disagreement_ui.py:
data baked in, no server, autosaves to localStorage, Export downloads a JSON of
decisions.

Three actions per candidate, per Jon's spec:
  approve  -- take the drafted question + gold as-is
  rewrite  -- edit the question and/or gold in place, then it counts as approved
  cut      -- drop it (used when the generalization can't be salvaged)

The rewrite fields are pre-filled with the draft so editing is a diff, not a
retype. A candidate is only exported as `rewrite` if the text actually differs
from the draft -- clicking rewrite and changing nothing exports as `approve`,
so the export reflects what happened rather than which button was pressed.

Run:  .venv/Scripts/python.exe evals/build_purerules_approval_ui.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evals" / "purerules_candidates.json"
OUT = ROOT / "data" / "parsed" / "purerules_approval.html"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing candidates file: {SRC}")
    data = json.loads(SRC.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("__PAYLOAD__", payload), encoding="utf-8")
    n = len(data.get("candidates", []))
    print(f"wrote {OUT} ({n} candidates)")
    print("Open it in a browser, decide each, then click Export to download decisions.")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pure-rules eval — approval</title>
<style>
  :root{
    --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --line:#2a2f3a;
    --text:#e8eaf0; --muted:#9aa3b2; --accent:#7aa2f7;
    --ok:#5ac87a; --partial:#e2b341; --wrong:#e2685f;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
    font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
  header{position:sticky;top:0;z-index:10;background:var(--panel);
    border-bottom:1px solid var(--line);padding:16px 20px}
  .bar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;
    max-width:1000px;margin:0 auto}
  h1{font-size:18px;margin:0;font-weight:650;letter-spacing:-0.01em}
  .grow{flex:1}
  .count{color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums}
  .count b{color:var(--text)}
  main{max-width:1000px;margin:0 auto;padding:20px}
  .intro{color:var(--muted);font-size:14px;margin:0 0 20px;
    background:var(--panel);border:1px solid var(--line);
    border-left:3px solid var(--accent);border-radius:8px;padding:14px 16px}
  .intro code{background:var(--panel2);padding:1px 5px;border-radius:4px;font-size:13px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:18px;margin-bottom:18px;border-left:3px solid var(--line)}
  .card[data-d="approve"]{border-left-color:var(--ok)}
  .card[data-d="rewrite"]{border-left-color:var(--partial)}
  .card[data-d="cut"]{border-left-color:var(--wrong);opacity:.6}
  .hd{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;margin-bottom:12px}
  .id{font-weight:650;font-size:15px}
  .src{color:var(--muted);font-size:12.5px}
  .tag{background:var(--panel2);border:1px solid var(--line);border-radius:999px;
    padding:2px 9px;font-size:11.5px;color:var(--muted);white-space:nowrap}
  h3{font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;
    color:var(--muted);margin:16px 0 6px;font-weight:650}
  .body{white-space:pre-wrap}
  details{margin-top:14px;border-top:1px solid var(--line);padding-top:10px}
  summary{cursor:pointer;color:var(--muted);font-size:13px;
    list-style:none;display:inline-flex;align-items:center;gap:6px}
  summary::-webkit-details-marker{display:none}
  summary::before{content:"▸";display:inline-block;transition:transform .15s}
  details[open] summary::before{transform:rotate(90deg)}
  summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:4px}
  .orig{color:var(--muted);font-size:13.5px;margin-top:8px}
  .why{color:var(--muted);font-size:13px;margin-top:10px;font-style:italic}
  .acts{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
  button{background:var(--panel2);color:var(--text);border:1px solid var(--line);
    border-radius:7px;padding:7px 14px;font-size:13.5px;cursor:pointer;
    font-family:inherit;transition:border-color .12s,background .12s}
  button:hover{border-color:var(--accent)}
  button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  button[aria-pressed="true"]{background:var(--accent);color:#0f1115;
    border-color:var(--accent);font-weight:600}
  .edit{display:none;margin-top:14px}
  .card[data-d="rewrite"] .edit{display:block}
  label{display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;
    color:var(--muted);margin:12px 0 5px;font-weight:650}
  textarea{width:100%;background:var(--panel2);color:var(--text);
    border:1px solid var(--line);border-radius:7px;padding:10px 12px;
    font:inherit;line-height:1.55;resize:vertical}
  textarea:focus-visible{outline:2px solid var(--accent);outline-offset:1px;
    border-color:var(--accent)}
  .dirty{color:var(--partial);font-size:12.5px;margin-top:6px;display:none}
  .card.is-dirty .dirty{display:block}
  .excl{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:16px 18px;margin-top:26px}
  .excl li{color:var(--muted);font-size:13.5px;margin-bottom:8px}
  .empty{color:var(--muted);text-align:center;padding:60px 20px}
  footer{max-width:1000px;margin:0 auto;padding:0 20px 60px;color:var(--muted);font-size:13px}
  @media (max-width:640px){.bar{gap:8px}h1{font-size:16px}main{padding:14px}}
</style></head><body>
<header><div class="bar">
  <h1>Pure-rules eval — approval</h1>
  <span class="grow"></span>
  <span class="count" id="count">—</span>
  <button id="export">Export decisions</button>
  <button id="reset">Reset</button>
</div></header>
<main>
  <p class="intro">Each card is a card-specific question from RulesGuru rewritten as a
  <b>pure rules</b> question, so the model can't answer it from oracle text.
  <b>Approve</b> takes the draft as-is. <b>Rewrite</b> opens editable fields pre-filled with
  the draft — change what you need. <b>Cut</b> drops it. Decisions autosave in this browser;
  click <code>Export decisions</code> when you're done.</p>
  <div id="list"></div>
  <div class="excl" id="excl"></div>
</main>
<footer id="foot"></footer>
<script>
const DATA = __PAYLOAD__;
const KEY = "purerules_approval_v1";
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); }
catch(e){ state = {}; console.warn("could not read saved state", e); }

const esc = s => String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

function save(){
  try { localStorage.setItem(KEY, JSON.stringify(state)); }
  catch(e){ console.warn("could not save", e); }
}

function entry(id){
  if(!state[id]) state[id] = {decision:null, question:null, gold:null};
  return state[id];
}

function render(){
  const list = document.getElementById("list");
  const cands = DATA.candidates || [];
  if(!cands.length){
    list.innerHTML = '<p class="empty">No candidates in this batch.</p>';
    return;
  }
  list.innerHTML = "";
  for(const c of cands){
    const st = entry(c.id);
    const q = st.question != null ? st.question : c.proposed_question;
    const g = st.gold != null ? st.gold : c.proposed_gold;
    const el = document.createElement("div");
    el.className = "card";
    el.dataset.id = c.id;
    if(st.decision) el.dataset.d = st.decision;
    el.innerHTML = `
      <div class="hd">
        <span class="id">${esc(c.id)}</span>
        <span class="src">from ${esc(c.source_qid)}</span>
        <span class="grow"></span>
        ${(c.source_gold_rules||[]).map(r=>`<span class="tag">CR ${esc(r)}</span>`).join("")}
      </div>
      <h3>Proposed rules question</h3>
      <div class="body" data-f="q">${esc(q)}</div>
      <h3>Proposed gold</h3>
      <div class="body" data-f="g">${esc(g)}</div>
      <p class="why">Tests: ${esc(c.tests||"")}</p>
      <details>
        <summary>Show the original card question and its judge-authored gold</summary>
        <div class="orig"><b>Original:</b> ${esc(c.source_question)}</div>
        <div class="orig"><b>Original gold:</b> ${esc(c.source_gold)}</div>
        ${c.note?`<div class="orig"><b>Note:</b> ${esc(c.note)}</div>`:""}
      </details>
      <div class="acts">
        <button data-a="approve" aria-pressed="${st.decision==="approve"}">Approve</button>
        <button data-a="rewrite" aria-pressed="${st.decision==="rewrite"}">Rewrite</button>
        <button data-a="cut"     aria-pressed="${st.decision==="cut"}">Cut</button>
      </div>
      <div class="edit">
        <label for="q-${esc(c.id)}">Question</label>
        <textarea id="q-${esc(c.id)}" rows="5" data-e="q">${esc(q)}</textarea>
        <label for="g-${esc(c.id)}">Gold</label>
        <textarea id="g-${esc(c.id)}" rows="6" data-e="g">${esc(g)}</textarea>
        <p class="dirty">Edited — will export as a rewrite.</p>
      </div>`;

    el.querySelectorAll("[data-a]").forEach(b=>{
      b.addEventListener("click", ()=>{
        const st2 = entry(c.id);
        st2.decision = (st2.decision === b.dataset.a) ? null : b.dataset.a;
        save(); render();
      });
    });
    el.querySelectorAll("[data-e]").forEach(t=>{
      t.addEventListener("input", ()=>{
        const st2 = entry(c.id);
        const field = t.dataset.e === "q" ? "question" : "gold";
        st2[field] = t.value;
        // Mirror edits into the read-only view + dirty flag, without a full
        // re-render (which would steal focus mid-typing).
        el.querySelector(`[data-f="${t.dataset.e}"]`).textContent = t.value;
        const edited = (st2.question != null && st2.question !== c.proposed_question)
                    || (st2.gold     != null && st2.gold     !== c.proposed_gold);
        el.classList.toggle("is-dirty", edited);
        save(); tally();
      });
    });
    const edited0 = (st.question != null && st.question !== c.proposed_question)
                 || (st.gold     != null && st.gold     !== c.proposed_gold);
    if(edited0) el.classList.add("is-dirty");
    list.appendChild(el);
  }
  tally();
}

function tally(){
  const cands = DATA.candidates || [];
  let a=0,r=0,x=0;
  for(const c of cands){
    const st = state[c.id];
    if(!st || !st.decision) continue;
    if(st.decision==="cut") x++;
    else if(effective(c)==="rewrite") r++;
    else a++;
  }
  const done = a+r+x;
  document.getElementById("count").innerHTML =
    `<b>${done}</b>/${cands.length} decided &nbsp;·&nbsp; ${a} approved · ${r} rewritten · ${x} cut`;
}

// A card counts as a rewrite only if the text actually changed. Pressing
// "rewrite" and editing nothing exports as an approve.
function effective(c){
  const st = state[c.id] || {};
  if(st.decision === "cut") return "cut";
  if(!st.decision) return null;
  const changed = (st.question != null && st.question !== c.proposed_question)
               || (st.gold     != null && st.gold     !== c.proposed_gold);
  return changed ? "rewrite" : "approve";
}

document.getElementById("export").addEventListener("click", ()=>{
  const out = {exported_at:new Date().toISOString(), batch:DATA.batch, decisions:[]};
  for(const c of (DATA.candidates||[])){
    const st = state[c.id] || {};
    out.decisions.push({
      id:c.id, source_qid:c.source_qid,
      decision: effective(c),
      question: st.question != null ? st.question : c.proposed_question,
      gold:     st.gold     != null ? st.gold     : c.proposed_gold,
      edited: effective(c) === "rewrite"
    });
  }
  const blob = new Blob([JSON.stringify(out,null,2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "purerules_decisions.json";
  a.click();
  URL.revokeObjectURL(a.href);
});

document.getElementById("reset").addEventListener("click", ()=>{
  if(confirm("Clear all decisions and edits in this browser?")){
    state = {}; localStorage.removeItem(KEY); render();
  }
});

const ex = DATA.deliberately_excluded || [];
document.getElementById("excl").innerHTML =
  `<h3>Deliberately excluded from this batch (${ex.length})</h3><ul>` +
  ex.map(e=>`<li><b>${esc(e.source_qid)}</b> — ${esc(e.reason)}</li>`).join("") + "</ul>";
document.getElementById("foot").textContent =
  "Selection rule: " + (DATA.selection_rule || "");

render();
</script></body></html>
"""


if __name__ == "__main__":
    main()
