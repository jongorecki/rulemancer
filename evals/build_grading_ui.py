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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

PARSED = Path(__file__).parent.parent / "data" / "parsed"
VERDICTS = Path(__file__).parent / "answer_verdicts.json"


def _load_card_data(names: list[str]) -> list[dict]:
    """Resolve each card name to the fields a human grader needs to check an
    answer: mana cost, type line, P/T (or loyalty/defense), and oracle text.

    PER FACE, deliberately (contracts.py CardFace, docs/plan-card-enrichment-
    fields.md). A card's TOP-LEVEL power/toughness does not exist -- Card has
    no such field, and for a modal DFC like Valki // Tibalt the top-level
    mana_cost is empty while each face has its own. Reading only the top level
    is the c014 miss in a different costume: the grader would show a creature
    with no P/T and a DFC with no cost.

    Local-first against data/scryfall.db. A miss returns a stub rather than
    raising, so one unresolvable name can never cost you the whole grading UI.
    """
    from rulesagent.tools.scryfall import get_card  # local import: keeps the

    # module importable (and --help working) on a machine with no scryfall.db
    out = []
    for name in names:
        try:
            card = get_card(name, no_refresh=True)
        except Exception as e:  # noqa: BLE001 -- a grading UI must still build
            out.append({"name": name, "error": f"{type(e).__name__}: {e}", "faces": []})
            continue
        if card is None:
            out.append({"name": name, "error": "not found", "faces": []})
            continue
        faces = [
            {
                "name": f.name or card.name,
                "mana_cost": f.mana_cost,
                "type_line": f.type_line,
                "oracle_text": f.oracle_text,
                "power": f.power,
                "toughness": f.toughness,
                "loyalty": f.loyalty,
                "defense": f.defense,
            }
            for f in (card.faces or [])
        ]
        if not faces:
            # Single-faced card whose enrichment never populated faces[]:
            # fall back to the whole-card fields so the panel is never blank.
            faces = [{
                "name": card.name, "mana_cost": card.mana_cost,
                "type_line": card.type_line, "oracle_text": card.oracle_text,
                "power": "", "toughness": "", "loyalty": "", "defense": "",
            }]
        out.append({"name": card.name, "error": None, "faces": faces})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, default=PARSED / "review_split.json")
    ap.add_argument("--out", type=Path, default=PARSED / "grading.html")
    ap.add_argument(
        "--questions", type=Path, default=None,
        help="source questions jsonl for the run. Supplies each question's `cards` "
        "list (run output rows don't carry it) and backfills answer_gold when the "
        "run predates that field. Without it the UI still builds -- it just has no "
        "card panel.",
    )
    ap.add_argument(
        "--no-cards", action="store_true",
        help="skip Scryfall enrichment even when --questions is given",
    )
    args = ap.parse_args()

    review = json.loads(args.inp.read_text(encoding="utf-8"))

    # Join card names + judge ruling from the source questions file. The run
    # output carries answer_gold but never `cards`, so without this the grader
    # cannot show what the cards actually do.
    if args.questions:
        src = {}
        for line in args.questions.read_text(encoding="utf-8").splitlines():
            if line.strip():
                q = json.loads(line)
                src[q["id"]] = q
        missing = 0
        for r in review:
            q = src.get(r["id"])
            if not q:
                missing += 1
                continue
            r.setdefault("answer_gold", q.get("answer_gold"))
            # gold_groups is NOT on the run output row (run_answer_eval.py
            # records `match` but not the groups), so without this join a
            # correctly-labelled groups question would still render as a flat
            # list -- the exact misrepresentation the panel exists to fix.
            # `match` is joined too so a relabelled questions file shows its
            # new mode against an older run.
            if q.get("gold_groups"):
                r["gold_groups"] = q["gold_groups"]
            if q.get("match"):
                r["match"] = q["match"]
            r["level"] = q.get("level")
            r["source_url"] = q.get("url")
            names = q.get("cards") or []
            r["cards"] = [] if args.no_cards else _load_card_data(names)
            r["card_names"] = names
        if missing:
            print(f"[warn] {missing} row(s) had no match in {args.questions.name}")
        if not args.no_cards:
            n_cards = sum(len(r.get("cards") or []) for r in review)
            n_bad = sum(1 for r in review for c in (r.get("cards") or []) if c["error"])
            print(f"[cards] resolved {n_cards - n_bad}/{n_cards} across {len(review)} rows")
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
  /* Judge ruling -- the human-authored answer this is graded against. Gold
     accent (same token as gold rules) and a left rule so it reads as the
     reference, visually distinct from the model's answer directly above it. */
  .ruling{border:1px solid var(--gold);border-left-width:3px;border-radius:8px;
    padding:12px 14px;margin-bottom:14px;background:rgba(227,179,65,.06);
    white-space:pre-wrap;font-size:14px}
  .ruling h3{font-size:12px;text-transform:uppercase;letter-spacing:.05em;
    color:var(--gold);margin:0 0 7px;font-weight:700}
  /* Card panel. Grid so 1-3 cards sit side by side on desktop and stack on
     narrow screens; each face is its own block because P/T and cost are
     per-face. */
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
    gap:10px;margin-bottom:14px}
  @media(max-width:680px){.cards{grid-template-columns:1fr}}
  .mtgcard{border:1px solid var(--line);border-radius:8px;background:var(--panel2);
    padding:11px 13px;font-size:13px}
  .mtgcard .cname{font-weight:700;font-size:14px;display:block}
  .mtgcard .cost{font:12px ui-monospace,monospace;color:var(--accent);float:right;
    margin-left:8px}
  .mtgcard .tline{color:var(--muted);font-size:12.5px;margin:2px 0 6px;font-style:italic}
  .mtgcard .otext{white-space:pre-wrap;margin:0}
  .mtgcard .pt{display:inline-block;margin-top:7px;font:12px ui-monospace,monospace;
    font-weight:700;background:var(--panel);border:1px solid var(--line);
    border-radius:6px;padding:2px 8px}
  .mtgcard .face+.face{border-top:1px dashed var(--line);margin-top:9px;padding-top:9px}
  .mtgcard.err{border-color:var(--wrong)}
  .mtgcard.err .cname{color:var(--wrong)}
  /* Gold match-mode legend. One accent per mode so the scoring bar is
     recognisable at a glance rather than read: any=blue (loosest),
     all=red (strictest), groups=gold (structured). */
  .gmode{display:flex;align-items:center;gap:8px;margin-bottom:9px;font-size:12px}
  .gtag{font:11px ui-monospace,monospace;font-weight:700;letter-spacing:.06em;
    border-radius:5px;padding:2px 7px;border:1px solid}
  .gwhy{color:var(--muted)}
  .gm-any .gtag{color:var(--accent);border-color:var(--accent-d);
    background:rgba(110,168,254,.10)}
  .gm-all .gtag{color:var(--wrong);border-color:var(--wrong);
    background:rgba(248,81,73,.10)}
  .gm-groups .gtag{color:var(--gold);border-color:var(--gold);
    background:rgba(227,179,65,.10)}
  /* Each OR-group is its own bordered block; the AND between them is an
     explicit separator, not whitespace the reader has to infer. */
  .ggroup{border:1px solid var(--line);border-left:3px solid var(--gold);
    border-radius:8px;padding:9px 10px 2px}
  .ghead{font:11px ui-monospace,monospace;font-weight:700;color:var(--gold);
    text-transform:uppercase;letter-spacing:.05em;margin-bottom:7px}
  .ghead .gjoin{color:var(--muted);font-weight:400;text-transform:none;
    letter-spacing:0;margin-left:5px}
  .gand{text-align:center;font:11px ui-monospace,monospace;font-weight:700;
    color:var(--muted);letter-spacing:.1em;margin:7px 0}
  .clar{border-left:3px solid var(--partial);padding:6px 12px;margin-bottom:14px;
    color:var(--muted);font-size:13.5px}
  .priornote{color:var(--muted);font-size:12.5px;margin-top:8px;font-style:italic}
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

// Gold rules rendered ACCORDING TO THEIR MATCH MODE.
//
// A flat list misrepresents what is actually being scored: "any" means find
// one of these, "all" means every one is required, and "groups" means an
// AND-of-ORs. Three different bars, and a grader reading one undifferentiated
// list cannot tell which one applies -- so they cannot tell whether a
// retrieval that surfaced two of four ids passed or failed.
function goldPanel(r){
  const mode = r.match || 'any';
  const legend = {
    any:    ['ANY',    'find <b>any one</b> of these'],
    all:    ['ALL',    '<b>every</b> rule is required'],
    groups: ['GROUPS', '<b>all</b> groups, <b>any one</b> within each'],
  }[mode] || ['ANY','find any one of these'];
  const chip = `<div class="gmode gm-${esc(mode)}">
      <span class="gtag">${legend[0]}</span><span class="gwhy">${legend[1]}</span></div>`;

  if(mode === 'groups' && r.gold_groups && r.gold_groups.length){
    const groups = r.gold_groups.map((g,i)=>`
      <div class="ggroup">
        <div class="ghead">Group ${i+1} <span class="gjoin">any one of</span></div>
        ${ruleList(g, r.gold_text)}
      </div>`).join('<div class="gand">AND</div>');
    return chip + groups;
  }
  // groups declared with no gold_groups is a data bug, not a display case --
  // say so rather than silently rendering it as a flat list.
  if(mode === 'groups')
    return chip + `<div class="empty">match is "groups" but gold_groups is empty — check the label</div>`
                + ruleList(r.gold, r.gold_text);
  return chip + ruleList(r.gold, r.gold_text);
}

// Cards: rendered PER FACE. A single-faced card has one face; a DFC/split/
// adventure card has one per face, each with its own cost, type line and P/T.
// Only emit the P/T badge for a face that actually has those values -- an
// empty "/" on every instant would be noise.
function faceBlock(f){
  const pt = f.power !== '' && f.toughness !== '' ? `${esc(f.power)}/${esc(f.toughness)}`
           : f.loyalty ? `loyalty ${esc(f.loyalty)}`
           : f.defense ? `defense ${esc(f.defense)}` : '';
  return `<div class="face">
    ${f.mana_cost?`<span class="cost">${esc(f.mana_cost)}</span>`:''}
    <span class="cname">${esc(f.name)}</span>
    <div class="tline">${esc(f.type_line)}</div>
    <p class="otext">${esc(f.oracle_text)}</p>
    ${pt?`<span class="pt">${pt}</span>`:''}
  </div>`;
}
function cardPanel(cards, names){
  if(!cards || !cards.length){
    // No enrichment available -- still name the cards the question references
    // rather than silently showing nothing.
    if(names && names.length)
      return `<div class="cards"><div class="mtgcard"><span class="cname">${names.map(esc).join(', ')}</span>
        <div class="tline">card text not loaded — rebuild with --questions</div></div></div>`;
    return '';
  }
  return `<div class="cards">${cards.map(c=>c.error
    ? `<div class="mtgcard err"><span class="cname">${esc(c.name)}</span>
         <div class="tline">could not resolve: ${esc(c.error)}</div></div>`
    : `<div class="mtgcard">${c.faces.map(faceBlock).join('')}</div>`).join('')}</div>`;
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
      ${r.level?`<span class="badge">level: ${esc(r.level)}</span>`:''}
      <span class="badge">answered:
        <b class="${r.answered?'flag-ok':'flag-no'}">${r.answered}</b></span>
      ${emptyCite?'<span class="badge flag-no">EMPTY CITATIONS</span>':''}
    </div>
    <div class="q">${esc(r.question)}</div>
    ${cardPanel(r.cards, r.card_names)}
    <div class="ans">${refHighlight(r.answer)}</div>
    ${r.answer_gold?`<div class="ruling"><h3>Judge ruling (gold answer)</h3>${refHighlight(r.answer_gold)}</div>`:''}
    ${r.clarification?`<div class="clar"><b>Clarification asked:</b> ${esc(r.clarification)}</div>`:''}
    <div class="cols">
      <div class="col cite"><h3>Cited by the answer</h3>${ruleList(r.citations, r.cited_text)}</div>
      <div class="col gold"><h3>Gold rules</h3>${goldPanel(r)}</div>
    </div>
    <div class="verdict">
      <button class="vbtn" data-v="correct">Correct</button>
      <button class="vbtn" data-v="partial">Partial</button>
      <button class="vbtn" data-v="wrong">Wrong</button>
      ${r.prior_verdict?`<span class="prior">prior: ${r.prior_verdict}</span>`:''}
    </div>
    ${r.prior_note?`<div class="priornote"><b>prior note:</b> ${esc(r.prior_note)}</div>`:''}
    <textarea placeholder="fresh note (optional) — the prior note above is reference only"></textarea>`;
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
