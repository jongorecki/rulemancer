"""Build a self-contained grading UI from an answer-eval run.

Reads a review file (default data/parsed/review_split.json) produced by
run_answer_eval.py and emits data/parsed/grading.html -- a single file Jon
opens in a browser, grades each answer against its cited + gold rule text,
and exports a verdicts JSON in the {id, verdict, note} shape that
evals/answer_verdicts.json uses.

Self-contained (data baked in), no server, autosaves to localStorage,
keyboard-driven. Run: `uv run python evals/build_grading_ui.py [--in PATH]`
"""

import argparse
import json
from pathlib import Path

PARSED = Path(__file__).parent.parent / "data" / "parsed"
VERDICTS = Path(__file__).parent / "answer_verdicts.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, default=PARSED / "review_split.json")
    ap.add_argument("--out", type=Path, default=PARSED / "grading.html")
    args = ap.parse_args()

    review = json.loads(args.inp.read_text(encoding="utf-8"))
    prior = {}
    if VERDICTS.exists():
        prior = {v["id"]: v for v in json.loads(VERDICTS.read_text(encoding="utf-8"))}
    for r in review:
        p = prior.get(r["id"])
        r["prior_verdict"] = p["verdict"] if p else None
        r["prior_note"] = p["note"] if p else ""

    data_json = json.dumps(review, ensure_ascii=False)
    html = _TEMPLATE.replace("__DATA__", data_json).replace("__SRC__", args.inp.name)
    args.out.write_text(html, encoding="utf-8")
    print(f"Wrote {args.out}  ({len(review)} answers)")
    print(f"Open it in a browser, grade, then click Export to download verdicts.")


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MTG answer grading</title>
<style>
  :root{
    --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --line:#2a2f3a;
    --text:#e6e8ec; --muted:#9aa3b2; --accent:#6ea8fe; --accent-d:#3d6fd6;
    --ok:#3fb950; --partial:#d29922; --wrong:#f85149;
    --gold:#e3b341; --cite:#6ea8fe;
    --radius:12px; --gap:16px; --maxw:900px;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
    font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  header{position:sticky;top:0;z-index:10;background:rgba(15,17,21,.92);
    backdrop-filter:blur(8px);border-bottom:1px solid var(--line);
    padding:12px max(16px,calc((100% - var(--maxw))/2))}
  .hrow{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
  h1{font-size:16px;margin:0;font-weight:650}
  .prog{flex:1;min-width:180px;height:8px;background:var(--panel2);
    border-radius:99px;overflow:hidden}
  .prog>i{display:block;height:100%;width:0;background:var(--ok);transition:width .2s}
  .count{color:var(--muted);font-variant-numeric:tabular-nums;font-size:13px}
  button{font:inherit;cursor:pointer;border:1px solid var(--line);
    background:var(--panel2);color:var(--text);border-radius:8px;padding:7px 12px}
  button:hover{border-color:var(--accent)}
  button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  .btn-primary{background:var(--accent-d);border-color:var(--accent-d);font-weight:600}
  main{max-width:var(--maxw);margin:0 auto;padding:24px 16px 120px}
  .hint{color:var(--muted);font-size:13px;margin:0 0 20px}
  kbd{background:var(--panel2);border:1px solid var(--line);border-bottom-width:2px;
    border-radius:5px;padding:1px 6px;font:12px ui-monospace,monospace}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
    padding:20px;margin-bottom:var(--gap);scroll-margin-top:80px}
  .card.graded{border-left:3px solid var(--ok)}
  .meta{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
  .badge{font:12px ui-monospace,monospace;background:var(--panel2);
    border:1px solid var(--line);border-radius:6px;padding:2px 7px;color:var(--muted)}
  .badge.q{color:var(--accent);border-color:var(--accent-d)}
  .flag-ok{color:var(--ok)} .flag-no{color:var(--wrong)}
  .q{font-size:17px;font-weight:600;margin:2px 0 14px}
  .ans{white-space:pre-wrap;background:var(--panel2);border:1px solid var(--line);
    border-radius:8px;padding:14px;margin-bottom:14px}
  .ans .ref{color:var(--cite);font-weight:600}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px}
  @media(max-width:680px){.cols{grid-template-columns:1fr}}
  .col h3{font-size:12px;text-transform:uppercase;letter-spacing:.05em;
    color:var(--muted);margin:0 0 8px}
  .rule{border:1px solid var(--line);border-radius:8px;padding:9px 11px;margin-bottom:8px;
    background:var(--panel2);font-size:13.5px}
  .rule .rid{font:12px ui-monospace,monospace;font-weight:600;display:block;margin-bottom:3px}
  .col.cite .rid{color:var(--cite)} .col.gold .rid{color:var(--gold)}
  .empty{color:var(--wrong);font-size:13px;font-style:italic}
  .clar{border-left:3px solid var(--partial);padding:6px 12px;margin-bottom:14px;
    color:var(--muted);font-size:13.5px}
  .verdict{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .vbtn{padding:8px 16px;font-weight:600;border-width:1.5px}
  .vbtn[data-v=correct].on{background:var(--ok);border-color:var(--ok);color:#04210b}
  .vbtn[data-v=partial].on{background:var(--partial);border-color:var(--partial);color:#231a02}
  .vbtn[data-v=wrong].on{background:var(--wrong);border-color:var(--wrong);color:#2a0606}
  .prior{color:var(--muted);font-size:12px;margin-left:auto}
  textarea{width:100%;margin-top:10px;background:var(--panel2);color:var(--text);
    border:1px solid var(--line);border-radius:8px;padding:9px;font:inherit;resize:vertical;min-height:38px}
  textarea:focus-visible{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
    background:var(--panel);border:1px solid var(--accent);border-radius:8px;
    padding:10px 18px;opacity:0;transition:opacity .2s;pointer-events:none}
  .toast.show{opacity:1}
</style>
</head>
<body>
<header>
  <div class="hrow">
    <h1>MTG answer grading</h1>
    <div class="prog"><i id="bar"></i></div>
    <span class="count" id="count">0 / 0</span>
    <button id="export" class="btn-primary">Export verdicts</button>
    <button id="reset">Reset</button>
  </div>
</header>
<main>
  <p class="hint">Source: <code>__SRC__</code>. Grade each answer against its
    <span style="color:var(--cite)">cited</span> and
    <span style="color:var(--gold)">gold</span> rule text.
    Keys: <kbd>1</kbd> correct &middot; <kbd>2</kbd> partial &middot; <kbd>3</kbd> wrong
    &middot; <kbd>j</kbd>/<kbd>k</kbd> next/prev. Autosaves; Export downloads
    <code>answer_verdicts.json</code>.</p>
  <div id="list"></div>
</main>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const KEY = "mtg_grading_v1";
let state = JSON.parse(localStorage.getItem(KEY) || "{}");

function esc(s){return (s||"").replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function refHighlight(s){return esc(s).replace(/\[(\d{3}\.\d+[a-z]?)\]/g,'[<span class="ref">$1</span>]');}
function ruleList(ids, textMap, cls){
  if(!ids || !ids.length) return '<div class="empty">— none —</div>';
  return ids.map(id=>{
    const t = (textMap && textMap[id]) || '(text not found as a chunk)';
    return `<div class="rule"><span class="rid">[${esc(id)}]</span>${esc(t)}</div>`;
  }).join('');
}

const list = document.getElementById('list');
DATA.forEach(r=>{
  const el = document.createElement('div');
  el.className = 'card'; el.id = 'card-'+r.id;
  const emptyCite = !r.citations || !r.citations.length;
  el.innerHTML = `
    <div class="meta">
      <span class="badge q">${r.id}</span>
      <span class="badge">${r.kind}</span>
      <span class="badge">match: ${r.match}</span>
      <span class="badge">answered:
        <b class="${r.answered?'flag-ok':'flag-no'}">${r.answered}</b></span>
      ${emptyCite?'<span class="badge flag-no">EMPTY CITATIONS</span>':''}
    </div>
    <div class="q">${esc(r.question)}</div>
    <div class="ans">${refHighlight(r.answer)}</div>
    ${r.clarification?`<div class="clar"><b>Clarification asked:</b> ${esc(r.clarification)}</div>`:''}
    <div class="cols">
      <div class="col cite"><h3>Cited by the answer</h3>${ruleList(r.citations, r.cited_text)}</div>
      <div class="col gold"><h3>Gold rules</h3>${ruleList(r.gold, r.gold_text)}</div>
    </div>
    <div class="verdict">
      <button class="vbtn" data-v="correct">Correct</button>
      <button class="vbtn" data-v="partial">Partial</button>
      <button class="vbtn" data-v="wrong">Wrong</button>
      ${r.prior_verdict?`<span class="prior">prior: ${r.prior_verdict}</span>`:''}
    </div>
    <textarea placeholder="note (optional)">${esc(r.prior_note||'')}</textarea>`;
  list.appendChild(el);

  const btns = el.querySelectorAll('.vbtn');
  const ta = el.querySelector('textarea');
  function paint(){
    const v = state[r.id]?.verdict;
    btns.forEach(b=>b.classList.toggle('on', b.dataset.v===v));
    el.classList.toggle('graded', !!v);
  }
  btns.forEach(b=>b.onclick=()=>{setVerdict(r.id, b.dataset.v, ta.value); paint(); progress();});
  ta.oninput=()=>{ if(state[r.id]){ setVerdict(r.id, state[r.id].verdict, ta.value); } };
  paint();
});

function setVerdict(id, verdict, note){
  state[id] = {verdict, note: note||''};
  localStorage.setItem(KEY, JSON.stringify(state));
}
function progress(){
  const g = DATA.filter(r=>state[r.id]?.verdict).length;
  document.getElementById('count').textContent = g+' / '+DATA.length;
  document.getElementById('bar').style.width = (100*g/DATA.length)+'%';
}
progress();

// keyboard: 1/2/3 grade the card nearest the viewport top; j/k navigate
const order = DATA.map(r=>r.id);
function currentCard(){
  let best=null, bd=1e9;
  for(const id of order){ const c=document.getElementById('card-'+id);
    const d=Math.abs(c.getBoundingClientRect().top-90); if(d<bd){bd=d;best=id;} }
  return best;
}
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='TEXTAREA') return;
  const map={'1':'correct','2':'partial','3':'wrong'};
  if(map[e.key]){ const id=currentCard(); const c=document.getElementById('card-'+id);
    setVerdict(id, map[e.key], state[id]?.note||'');
    c.querySelectorAll('.vbtn').forEach(b=>b.classList.toggle('on',b.dataset.v===map[e.key]));
    c.classList.add('graded'); progress(); toast(id+': '+map[e.key]);
    const nx=order[order.indexOf(id)+1]; if(nx) document.getElementById('card-'+nx).scrollIntoView({behavior:'smooth'});
  }
  if(e.key==='j'||e.key==='k'){ const id=currentCard(); let i=order.indexOf(id)+(e.key==='j'?1:-1);
    i=Math.max(0,Math.min(order.length-1,i)); document.getElementById('card-'+order[i]).scrollIntoView({behavior:'smooth'});}
});

let tt;
function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');
  clearTimeout(tt);tt=setTimeout(()=>t.classList.remove('show'),1200);}

document.getElementById('export').onclick=()=>{
  const out = DATA.map(r=>({id:r.id, verdict:(state[r.id]?.verdict)||'', note:(state[r.id]?.note)||''}));
  const blob = new Blob([JSON.stringify(out,null,2)], {type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='answer_verdicts.json'; a.click();
  const ungraded = out.filter(o=>!o.verdict).map(o=>o.id);
  toast(ungraded.length? ('exported — ungraded: '+ungraded.join(', ')) : 'exported all '+out.length);
};
document.getElementById('reset').onclick=()=>{
  if(confirm('Clear all grades in this browser?')){ state={}; localStorage.removeItem(KEY);
    document.querySelectorAll('.vbtn').forEach(b=>b.classList.remove('on'));
    document.querySelectorAll('.card').forEach(c=>c.classList.remove('graded')); progress(); }
};
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
