"""Build a self-contained grading UI for the RulesGuru auto-judge disagreements.

Reads evals/rulesguru_disagreements_sonnet.json (42 rows where the frozen
gpt-5-mini judge marked Rulemancer's answer "different" from RulesGuru's
certified-judge reference ruling) and emits
data/parsed/grading_rulesguru_disagreements.html -- a single file Jon opens
in a browser to hand-adjudicate each one: is Rulemancer's answer actually
correct, even though the auto-judge flagged it?

Self-contained (data baked in), no server, autosaves to localStorage,
keyboard-driven. Mirrors evals/build_grading_ui.py's look, keyboard model,
localStorage+export pattern, and verdict color scheme (--ok/--partial/--wrong).

Run: `uv run python evals/build_rulesguru_disagreement_ui.py [--in PATH]`
"""

import argparse
import json
from pathlib import Path

PARSED = Path(__file__).parent.parent / "data" / "parsed"
DEFAULT_IN = Path(__file__).parent / "rulesguru_disagreements_sonnet.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, default=DEFAULT_IN)
    ap.add_argument("--out", type=Path, default=PARSED / "grading_rulesguru_disagreements.html")
    args = ap.parse_args()

    rows = json.loads(args.inp.read_text(encoding="utf-8"))

    PARSED.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps(rows, ensure_ascii=False)
    html = _TEMPLATE.replace("__DATA__", data_json).replace("__SRC__", args.inp.name)
    args.out.write_text(html, encoding="utf-8")
    print(f"Wrote {args.out}  ({len(rows)} disagreements)")
    print("Open it in a browser, grade, then click Export to download verdicts.")


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RulesGuru disagreement grading</title>
<style>
  :root{
    --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --line:#2a2f3a;
    --text:#e6e8ec; --muted:#9aa3b2; --accent:#6ea8fe; --accent-d:#3d6fd6;
    --ok:#3fb950; --partial:#d29922; --wrong:#f85149;
    --gold:#e3b341; --cite:#6ea8fe;
    --radius:12px; --gap:16px; --maxw:960px;
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
  .tally{color:var(--muted);font-variant-numeric:tabular-nums;font-size:13px;display:flex;gap:10px}
  .tally b.ok{color:var(--ok)} .tally b.partial{color:var(--partial)} .tally b.wrong{color:var(--wrong)}
  button{font:inherit;cursor:pointer;border:1px solid var(--line);
    background:var(--panel2);color:var(--text);border-radius:8px;padding:7px 12px}
  button:hover{border-color:var(--accent)}
  button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  .btn-primary{background:var(--accent-d);border-color:var(--accent-d);font-weight:600}
  main{max-width:var(--maxw);margin:0 auto;padding:24px 16px 160px}
  .hint{color:var(--muted);font-size:13px;margin:0 0 20px}
  kbd{background:var(--panel2);border:1px solid var(--line);border-bottom-width:2px;
    border-radius:5px;padding:1px 6px;font:12px ui-monospace,monospace}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
    padding:20px;margin-bottom:var(--gap);scroll-margin-top:80px;overflow-x:hidden}
  .card.graded{border-left:3px solid var(--ok)}
  .meta{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
  .badge{font:12px ui-monospace,monospace;background:var(--panel2);
    border:1px solid var(--line);border-radius:6px;padding:2px 7px;color:var(--muted)}
  .badge.q{color:var(--accent);border-color:var(--accent-d)}
  .badge.level{color:var(--gold);border-color:var(--gold)}
  .badge a{color:inherit;text-decoration:none}
  .badge a:hover{text-decoration:underline}
  .tags{color:var(--muted);font-size:12px;margin:0 0 4px}
  .tags span{background:var(--panel2);border:1px solid var(--line);border-radius:6px;
    padding:1px 6px;margin-right:4px;display:inline-block;margin-bottom:4px}
  .goldrules{color:var(--muted);font-size:11.5px;font-family:ui-monospace,monospace;margin-bottom:12px}
  .q{font-size:17px;font-weight:600;margin:6px 0 16px;white-space:pre-wrap}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px}
  @media(max-width:760px){.cols{grid-template-columns:1fr}}
  .col{border-radius:8px;padding:14px;min-width:0}
  .col h3{font-size:12px;text-transform:uppercase;letter-spacing:.05em;
    margin:0 0 8px;display:flex;align-items:center;gap:6px}
  .col .body{white-space:pre-wrap;font-size:13.5px;max-height:420px;overflow-y:auto;padding-right:4px}
  .cards-ref{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:6px 12px 10px;margin:0 0 16px}
  .cards-ref>summary{cursor:pointer;color:var(--muted);font-size:11.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;user-select:none;padding:4px 0}
  .cards-ref>summary:hover{color:var(--text)}
  .carditem{border-top:1px solid var(--line);padding:8px 0 4px}
  .carditem:first-of-type{border-top:0}
  .cardhdr{display:flex;justify-content:space-between;gap:12px;align-items:baseline}
  .cardname{font-weight:600;font-size:13.5px}
  .cardcost{font-family:ui-monospace,monospace;color:var(--accent);font-size:12.5px;white-space:nowrap}
  .cardtype{color:var(--muted);font-size:12px;font-style:italic;margin:2px 0}
  .cardtext{white-space:pre-wrap;font-size:12.5px;color:var(--text);margin-top:3px}
  .facesep{color:var(--muted);font-family:monospace;margin:5px 0}
  .carderr{color:var(--muted);font-style:italic;font-size:12px}
  .col.gold{background:rgba(227,179,65,.08);border:1px solid rgba(227,179,65,.35)}
  .col.gold h3{color:var(--gold)}
  .col.mine{background:rgba(110,168,254,.08);border:1px solid rgba(110,168,254,.35)}
  .col.mine h3{color:var(--cite)}
  .judgebar{border-left:3px solid var(--muted);background:var(--panel2);border-radius:0 8px 8px 0;
    padding:10px 14px;margin-bottom:16px;color:var(--muted);font-size:13.5px}
  .judgebar b{color:var(--text)}
  .judgebar .diff{color:var(--wrong);font-weight:700;letter-spacing:.03em}
  .prompt{font-weight:600;margin-bottom:10px;font-size:14px}
  .verdict{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .vbtn{padding:8px 16px;font-weight:600;border-width:1.5px}
  .vbtn[data-v=correct].on{background:var(--ok);border-color:var(--ok);color:#04210b}
  .vbtn[data-v=partial].on{background:var(--partial);border-color:var(--partial);color:#231a02}
  .vbtn[data-v=wrong].on{background:var(--wrong);border-color:var(--wrong);color:#2a0606}
  textarea{width:100%;margin-top:10px;background:var(--panel2);color:var(--text);
    border:1px solid var(--line);border-radius:8px;padding:9px;font:inherit;resize:vertical;min-height:38px}
  textarea:focus-visible{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
    background:var(--panel);border:1px solid var(--accent);border-radius:8px;
    padding:10px 18px;opacity:0;transition:opacity .2s;pointer-events:none}
  .toast.show{opacity:1}
  .empty{color:var(--muted);text-align:center;padding:60px 0;font-size:14px}
</style>
</head>
<body>
<header>
  <div class="hrow">
    <h1>RulesGuru disagreement grading</h1>
    <div class="prog"><i id="bar"></i></div>
    <span class="count" id="count">0 / 0</span>
    <span class="tally" id="tally"></span>
    <button id="export" class="btn-primary">Export verdicts</button>
    <button id="reset">Reset</button>
  </div>
</header>
<main>
  <p class="hint">Source: <code>__SRC__</code>. The auto-judge (gpt-5-mini) marked each of
    these "different" from RulesGuru's certified-judge reference. Decide if Rulemancer's
    answer is actually correct anyway (right conclusion, different reasoning) &mdash; a false
    negative from the auto-judge &mdash; or genuinely wrong/partial.
    Keys: <kbd>1</kbd> correct &middot; <kbd>2</kbd> partial &middot; <kbd>3</kbd> wrong
    &middot; <kbd>j</kbd>/<kbd>k</kbd> next/prev card. Autosaves to this browser; Export
    downloads a verdicts JSON.</p>
  <div id="list"></div>
</main>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const KEY = "rulesguru_disagreement_grading_v1";
let state = JSON.parse(localStorage.getItem(KEY) || "{}");

function esc(s){return (s||"").replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function faceBlock(f){
  return `<div class="cardhdr"><span class="cardname">${esc(f.name)}</span>`
    + (f.mana_cost?`<span class="cardcost">${esc(f.mana_cost)}</span>`:``) + `</div>`
    + (f.type_line?`<div class="cardtype">${esc(f.type_line)}</div>`:``)
    + (f.oracle_text?`<div class="cardtext">${esc(f.oracle_text)}</div>`:``);
}
function cardBlock(c){
  if(c.error){return `<div class="carditem"><span class="cardname">${esc(c.name)}</span> <span class="carderr">(${esc(c.error)})</span></div>`;}
  if(c.faces&&c.faces.length){return `<div class="carditem">`+c.faces.map(faceBlock).join(`<div class="facesep">//</div>`)+`</div>`;}
  return `<div class="carditem">`+faceBlock(c)+`</div>`;
}

const list = document.getElementById('list');
if(!DATA.length){
  list.innerHTML = '<div class="empty">No disagreements to grade.</div>';
} else {
DATA.forEach(r=>{
  const el = document.createElement('div');
  el.className = 'card'; el.id = 'card-'+r.id;
  const tags = (r.tags||[]).map(t=>`<span>${esc(t)}</span>`).join('');
  const goldIds = (r.gold_rule_ids||[]).length
    ? `<div class="goldrules">gold rules cited: ${esc((r.gold_rule_ids||[]).join(', '))}</div>` : '';
  el.innerHTML = `
    <div class="meta">
      <span class="badge q">${esc(r.id)}</span>
      <span class="badge level">level ${esc(r.level)}</span>
      <span class="badge">${esc(r.complexity)}</span>
      <span class="badge"><a href="${esc(r.url)}" target="_blank" rel="noopener">source &#8599;</a></span>
    </div>
    ${tags?`<div class="tags">${tags}</div>`:''}
    ${goldIds}
    <div class="q">${esc(r.question)}</div>
    ${(r.cards_data||[]).length?`<details class="cards-ref" open><summary>Cards referenced (${r.cards_data.length})</summary>${r.cards_data.map(cardBlock).join('')}</details>`:''}
    <div class="cols">
      <div class="col gold"><h3>Reference ruling &mdash; RulesGuru (certified judge)</h3>
        <div class="body">${esc(r.answer_gold)}</div></div>
      <div class="col mine"><h3>Rulemancer answered (sonnet)</h3>
        <div class="body">${esc(r.answer)}</div></div>
    </div>
    <div class="judgebar"><span class="diff">Auto-judge (gpt-5-mini): DIFFERENT</span>
      &mdash; <b>${esc(r.judge_reason)}</b></div>
    <div class="prompt">Is Rulemancer's answer actually correct?</div>
    <div class="verdict">
      <button class="vbtn" data-v="correct">Correct</button>
      <button class="vbtn" data-v="partial">Partial</button>
      <button class="vbtn" data-v="wrong">Wrong</button>
    </div>
    <textarea placeholder="note (optional)"></textarea>`;
  list.appendChild(el);

  const btns = el.querySelectorAll('.vbtn');
  const ta = el.querySelector('textarea');
  ta.value = state[r.id]?.note || '';
  function paint(){
    const v = state[r.id]?.verdict;
    btns.forEach(b=>b.classList.toggle('on', b.dataset.v===v));
    el.classList.toggle('graded', !!v);
  }
  btns.forEach(b=>b.onclick=()=>{setVerdict(r.id, b.dataset.v, ta.value); paint(); progress();});
  ta.oninput=()=>{ setVerdict(r.id, state[r.id]?.verdict, ta.value); };
  paint();
});
}

function setVerdict(id, verdict, note){
  state[id] = {verdict: verdict||'', note: note||''};
  localStorage.setItem(KEY, JSON.stringify(state));
}
function progress(){
  const g = DATA.filter(r=>state[r.id]?.verdict).length;
  document.getElementById('count').textContent = g+' / '+DATA.length;
  document.getElementById('bar').style.width = (DATA.length? (100*g/DATA.length):0)+'%';
  const c = DATA.filter(r=>state[r.id]?.verdict==='correct').length;
  const p = DATA.filter(r=>state[r.id]?.verdict==='partial').length;
  const w = DATA.filter(r=>state[r.id]?.verdict==='wrong').length;
  document.getElementById('tally').innerHTML =
    `<b class="ok">${c} correct</b><b class="partial">${p} partial</b><b class="wrong">${w} wrong</b>`;
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
  if(!order.length) return;
  const map={'1':'correct','2':'partial','3':'wrong'};
  if(map[e.key]){ const id=currentCard(); const c=document.getElementById('card-'+id);
    const ta = c.querySelector('textarea');
    setVerdict(id, map[e.key], ta?ta.value:(state[id]?.note||''));
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
  a.download='rulesguru_disagreement_verdicts.json'; a.click();
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
