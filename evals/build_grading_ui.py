"""Build a self-contained grading UI from an answer-eval run.

Reads a review file (default data/parsed/review_split.json) produced by
run_answer_eval.py and emits data/parsed/grading.html -- a single file Jon
opens in a browser, grades each answer against its cited + gold rule text,
and exports a verdicts JSON in the {id, verdict, note} shape that
evals/answer_verdicts.json uses.

Self-contained (data baked in), no server, autosaves to localStorage,
keyboard-driven. Run: `uv run python evals/build_grading_ui.py [--in PATH]`

Two verdict vocabularies (--verdicts, docs/spec-gold-audit-ui.md):
  answer-quality  correct/partial/wrong on our answer. The default; unchanged.
  gold-audit      who is wrong -- the RulesGuru answer, the gold rules, or us.

Rows carrying `retrieved_rule_ids` also get a Retrieved panel, labelled with
their `retrieved_provenance` ("run" = the row recorded them; "probe" = they were
retrieved later against a possibly-different index). Text comes from the row's
`retrieved_text` map, built by evals/build_gold_audit_input.py, so this stays a
pure renderer and never loads a vector store.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

PARSED = Path(__file__).parent.parent / "data" / "parsed"
VERDICTS = Path(__file__).parent / "answer_verdicts.json"

# Verdict vocabularies (docs/spec-gold-audit-ui.md).
#
# "answer-quality" is the original set and stays the default, so every existing
# invocation is unchanged. "gold-audit" exists because correct/partial/wrong
# does not fit a gold audit: those rows are already known-failed by
# construction, so "ours was wrong" is not a finding -- the open question is
# WHO is wrong, the reference answer or the gold rules or us.
#
# Each set carries its own `storage` key. That is not cosmetic: the two UIs are
# graded in the same browser, and a shared localStorage key would let an
# answer-quality grade surface as a prior verdict in a gold audit whose buttons
# cannot even express it. Separate `export` names keep the two exports from
# being merged downstream for the same reason.
VERDICT_SETS = {
    "answer-quality": {
        "buttons": [
            {"v": "correct", "label": "Correct"},
            {"v": "partial", "label": "Partial"},
            {"v": "wrong", "label": "Wrong"},
        ],
        "export": "answer_verdicts.json",
        "storage": "mtg_grading_v1",
        "title": "MTG answer grading",
        "hint": ("Grade each answer against its cited and gold rule text."),
    },
    "gold-audit": {
        "buttons": [
            {"v": "rulesguru-wrong", "label": "RulesGuru answer wrong"},
            {"v": "gold-incomplete", "label": "Gold incomplete / mis-cited"},
            {"v": "ours-wrong", "label": "Our reasoning wrong"},
            {"v": "ambiguous", "label": "Ambiguous — both defensible"},
        ],
        "export": "gold_audit_verdicts.json",
        "storage": "mtg_gold_audit_v1",
        "title": "MTG gold audit",
        "hint": ("Every row here already failed with complete gold, so the question "
                 "is not whether we got it wrong — it is who is wrong. An official "
                 "card ruling outranks RulesGuru gold (docs/gold-corrections.md)."),
    },
}


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
        out.append({
            "name": card.name, "error": None, "faces": faces,
            # Rulings carry the PROMPT'S OWN INDEX, which is 0-based:
            # answer.py:1867/1873 build the label with enumerate(...) and no
            # start=1, so "[Card ruling #4]" is card.rulings[4] -- the fifth
            # ruling. Numbering these 1..n here would silently misalign every
            # citation by one. The index is a position into an externally-owned
            # list (this repo's recurring defect shape; ruling_id() exists to
            # replace it) -- mirrored rather than reinvented so the UI shows
            # what the model was actually shown.
            "rulings": [{"n": i, "text": t} for i, t in enumerate(card.rulings)],
        })
    return out


_RULING_CITE = re.compile(r"^(?P<card>.+?)\s+ruling\s+#(?P<n>\d+)$")


def _resolve_ruling_citations(row: dict) -> int:
    """Fill cited_text/gold_text entries for citations of the form
    "<Card Name> ruling #N".

    These are not CR chunks, so the UI rendered them as "(text not found as a
    chunk)" -- the grader could see that a card ruling was cited but never what
    it said. Resolved here, server-side, so the existing rule list renders them
    with no template change.
    """
    by_name = {c["name"]: c for c in (row.get("cards") or []) if not c["error"]}
    filled = 0
    for field in ("cited_text", "gold_text"):
        texts = row.setdefault(field, {})
        ids = row.get("citations" if field == "cited_text" else "gold") or []
        for cid in ids:
            if cid in texts and texts[cid]:
                continue
            m = _RULING_CITE.match(cid)
            if not m:
                continue
            card = by_name.get(m.group("card"))
            if not card:
                continue
            n = int(m.group("n"))
            if 0 <= n < len(card["rulings"]):
                texts[cid] = card["rulings"][n]["text"]
                filled += 1
            else:
                # A cited index the card doesn't have. Say so -- an out-of-range
                # ruling citation is a real finding about the answer, not a
                # rendering gap to paper over.
                texts[cid] = (f"(cited ruling #{n} is out of range — "
                              f"{card['name']} has {len(card['rulings'])} rulings, #0-#{len(card['rulings'])-1})")
                filled += 1
    return filled


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
    ap.add_argument(
        "--verdicts", choices=sorted(VERDICT_SETS), default="answer-quality",
        help="which verdict vocabulary to render. Default answer-quality (the "
        "original correct/partial/wrong). gold-audit swaps in the who-is-wrong "
        "buttons and exports to gold_audit_verdicts.json "
        "(docs/spec-gold-audit-ui.md).",
    )
    args = ap.parse_args()
    cfg = VERDICT_SETS[args.verdicts]

    review = json.loads(args.inp.read_text(encoding="utf-8"))

    # Apostrophe aliasing for the three glossary chunks whose source_id carries
    # the CR's curly apostrophe. A citation written with the ASCII apostrophe
    # would otherwise render "(text not found as a chunk)" for a rule that was
    # retrieved perfectly well. Aliases are ADDED, never replacing the original
    # key, so a citation in either form resolves.
    from rulesagent.contracts import normalize_source_id
    for r in review:
        # retrieved_text is aliased too -- a retrieved glossary chunk hits the
        # same curly-apostrophe mismatch as a cited one, and an unaliased key
        # would render "(text not found as a chunk)" for a rule the probe
        # surfaced perfectly well.
        for field in ("cited_text", "gold_text", "retrieved_text"):
            texts = r.get(field)
            if not isinstance(texts, dict):
                continue
            for key, val in list(texts.items()):
                alias = normalize_source_id(key)
                if alias != key and alias not in texts:
                    texts[alias] = val

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
            # Fall back to names the row already carries. The questions file's
            # `cards` field is null for all 150 RulesGuru questions, so without
            # this every rg row renders with no card panel and no rulings --
            # build_gold_audit_input.py parses them out of the question text
            # the way answer.py does.
            names = q.get("cards") or r.get("card_names") or []
            r["cards"] = [] if args.no_cards else _load_card_data(names)
            r["card_names"] = names
        if missing:
            print(f"[warn] {missing} row(s) had no match in {args.questions.name}")
        if not args.no_cards:
            n_cards = sum(len(r.get("cards") or []) for r in review)
            n_bad = sum(1 for r in review for c in (r.get("cards") or []) if c["error"])
            print(f"[cards] resolved {n_cards - n_bad}/{n_cards} across {len(review)} rows")
            n_rul = sum(_resolve_ruling_citations(r) for r in review)
            n_have = sum(len(c["rulings"]) for r in review for c in (r.get("cards") or [])
                         if not c["error"])
            print(f"[rulings] {n_have} card rulings available; "
                  f"resolved {n_rul} '<card> ruling #N' citation(s) to their text")
    # Priors come from THIS vocabulary's own export, not always
    # answer_verdicts.json -- showing a correct/partial/wrong prior above
    # gold-audit buttons that cannot express it would be worse than showing no
    # prior at all.
    prior_path = VERDICTS if args.verdicts == "answer-quality" else \
        Path(__file__).parent / cfg["export"]
    prior = {}
    if prior_path.exists():
        prior = {v["id"]: v for v in json.loads(prior_path.read_text(encoding="utf-8"))}
    for r in review:
        p = prior.get(r["id"])
        r["prior_verdict"] = p["verdict"] if p else None
        r["prior_note"] = p["note"] if p else ""

    n_retr = sum(1 for r in review if r.get("retrieved_rule_ids"))
    if n_retr:
        prov = {r.get("retrieved_provenance") or "unlabelled" for r in review
                if r.get("retrieved_rule_ids")}
        print(f"[retrieved] {n_retr}/{len(review)} rows carry a retrieved set "
              f"({', '.join(sorted(prov))})")

    # Config placeholders are substituted BEFORE __DATA__ so a run whose answer
    # text happens to contain a placeholder token cannot rewrite the template.
    html = (_TEMPLATE
            .replace("__SRC__", args.inp.name)
            .replace("__TITLE__", cfg["title"])
            .replace("__HINT__", cfg["hint"])
            .replace("__CFG__", json.dumps(
                {"buttons": cfg["buttons"], "export": cfg["export"],
                 "storage": cfg["storage"]}, ensure_ascii=False))
            .replace("__DATA__", json.dumps(review, ensure_ascii=False)))
    args.out.write_text(html, encoding="utf-8")
    print(f"Wrote {args.out}  ({len(review)} answers, {args.verdicts} verdicts)")
    print(f"Open it in a browser, grade, then click Export to download "
          f"{cfg['export']}.")


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
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
  /* Retrieved panel. Full width below the cited/gold columns rather than a
     third column: it holds TOP_K rules with full text, which at a third of the
     width would be a column of slivers. Collapsed by default so it never
     buries the two panels a grader reads first, with the count in the summary
     so it can be skipped without opening. */
  .retr{border:1px solid var(--line);border-radius:8px;background:var(--panel2);
    margin-bottom:14px}
  .retr>summary{cursor:pointer;padding:9px 12px;font-size:12px;
    text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
    font-weight:700;list-style:none;display:flex;gap:9px;align-items:center;
    flex-wrap:wrap}
  .retr>summary::-webkit-details-marker{display:none}
  .retr>summary::before{content:"▸";font-size:11px;color:var(--muted)}
  .retr[open]>summary::before{content:"▾"}
  .retr>summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;
    border-radius:8px}
  .retr .body{padding:0 12px 10px}
  .retr .rid{color:var(--muted)}
  /* Provenance is the load-bearing part of this panel: a probe is what we would
     retrieve TODAY, not what the run pulled. Warn-coloured so it cannot be read
     as run provenance at a glance; run-recorded is neutral. */
  .prov{font:11px ui-monospace,monospace;font-weight:600;border-radius:5px;
    padding:2px 7px;border:1px solid;text-transform:none;letter-spacing:0}
  .prov.probe{color:var(--partial);border-color:var(--partial);
    background:rgba(210,153,34,.10)}
  .prov.run{color:var(--ok);border-color:var(--ok);background:rgba(63,185,80,.10)}
  .provnote{color:var(--muted);font-weight:400;text-transform:none;
    letter-spacing:0;font-size:11.5px}
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
  /* Scryfall rulings. Numbered with the PROMPT'S 0-based index so a citation
     like "[Card ruling #4]" can be matched by eye to the row labelled #4. */
  .crulings{margin-top:9px;border-top:1px solid var(--line);padding-top:8px}
  .crulings>h4{font:10px ui-monospace,monospace;font-weight:700;letter-spacing:.06em;
    text-transform:uppercase;color:var(--muted);margin:0 0 6px}
  .crul{display:flex;gap:7px;margin-bottom:6px;font-size:12.5px;line-height:1.45}
  .crul>b{font:11px ui-monospace,monospace;color:var(--gold);flex:none;padding-top:1px}
  .crul>span{color:var(--text)}
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
  /* Gold-audit vocabulary. Dark text on the light selected fill, same as the
     three above, so the selected state clears AA contrast rather than relying
     on colour alone -- the .on class and the button's aria-pressed state carry
     the meaning for anyone who cannot separate these hues. */
  .vbtn[data-v=rulesguru-wrong].on{background:var(--wrong);border-color:var(--wrong);color:#2a0606}
  .vbtn[data-v=gold-incomplete].on{background:var(--gold);border-color:var(--gold);color:#231a02}
  .vbtn[data-v=ours-wrong].on{background:var(--accent);border-color:var(--accent);color:#04152e}
  .vbtn[data-v=ambiguous].on{background:var(--muted);border-color:var(--muted);color:#12151b}
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
    <h1>__TITLE__</h1>
    <div class="prog"><i id="bar"></i></div>
    <span class="count" id="count">0 / 0</span>
    <button id="export" class="btn-primary">Export verdicts</button>
    <button id="reset">Reset</button>
  </div>
</header>
<main>
  <p class="hint">Source: <code>__SRC__</code>. __HINT__
    <span id="keyhint"></span> &middot; <kbd>j</kbd>/<kbd>k</kbd> next/prev.
    Autosaves; Export downloads <code id="expname"></code>.</p>
  <div id="list"></div>
</main>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const CFG = __CFG__;
const KEY = CFG.storage;
let state = JSON.parse(localStorage.getItem(KEY) || "{}");
document.getElementById('expname').textContent = CFG.export;
document.getElementById('keyhint').innerHTML = 'Keys: ' + CFG.buttons
  .map((b,i)=>`<kbd>${i+1}</kbd> ${esc(b.label)}`).join(' &middot; ');

function esc(s){return (s||"").replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function refHighlight(s){return esc(s).replace(/\[(\d{3}\.\d+[a-z]?)\]/g,'[<span class="ref">$1</span>]');}
function ruleList(ids, textMap, cls){
  if(!ids || !ids.length) return '<div class="empty">— none —</div>';
  return ids.map(id=>{
    const t = (textMap && textMap[id]) || '(text not found as a chunk)';
    return `<div class="rule"><span class="rid">[${esc(id)}]</span>${esc(t)}</div>`;
  }).join('');
}

// What retrieval actually surfaced -- the panel that separates a retrieval
// failure from a reasoning failure. Without it a grader sees that the gold rule
// was not cited but cannot tell whether it was never retrieved or was retrieved
// and ignored, which are opposite findings with opposite fixes.
//
// PROVENANCE IS RENDERED, NOT ASSUMED. "probe" means these ids come from
// retrieving NOW against the current index, because the row recorded none (the
// gold-only derivability arms). "run" means the row recorded them itself. The
// two look identical in a list and mean different things, so the label ships
// with the data on every row.
function retrievedPanel(r){
  const ids = r.retrieved_rule_ids;
  if(!ids || !ids.length) return '';
  const prov = r.retrieved_provenance || 'unlabelled';
  const label = prov === 'probe' ? 'retrieved today (probe) — not what the run pulled'
              : prov === 'run'   ? 'retrieved by the run'
              : 'provenance not recorded — do not read as run provenance';
  const cls = prov === 'run' ? 'run' : 'probe';
  const gold = new Set(r.gold || []);
  const hits = ids.filter(id=>gold.has(id)).length;
  return `<details class="retr">
    <summary>Retrieved (${ids.length})
      <span class="prov ${cls}">${esc(label)}</span>
      <span class="provnote">${hits} of ${gold.size} gold id(s) present${
        r.probe_config?` &middot; ${esc(r.probe_config)}`:''}</span>
    </summary>
    <div class="body">${ruleList(ids, r.retrieved_text)}</div>
  </details>`;
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
// Scryfall rulings, numbered with the prompt's own 0-based index (see the
// Python side): "[Card ruling #4]" is rulings[4], the fifth one. Showing them
// 1..n would misalign every citation by one.
function rulingsBlock(c){
  if(!c.rulings || !c.rulings.length) return '';
  return `<div class="crulings"><h4>Scryfall rulings (${c.rulings.length})</h4>
    ${c.rulings.map(r=>`<div class="crul"><b>#${r.n}</b><span>${esc(r.text)}</span></div>`).join('')}
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
    : `<div class="mtgcard">${c.faces.map(faceBlock).join('')}${rulingsBlock(c)}</div>`).join('')}</div>`;
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
    ${retrievedPanel(r)}
    <div class="verdict">
      ${CFG.buttons.map(b=>`<button class="vbtn" data-v="${esc(b.v)}" aria-pressed="false">${esc(b.label)}</button>`).join('')}
      ${r.prior_verdict?`<span class="prior">prior: ${esc(r.prior_verdict)}</span>`:''}
    </div>
    ${r.prior_note?`<div class="priornote"><b>prior note:</b> ${esc(r.prior_note)}</div>`:''}
    <textarea placeholder="fresh note (optional) — the prior note above is reference only"></textarea>`;
  list.appendChild(el);

  const btns = el.querySelectorAll('.vbtn');
  const ta = el.querySelector('textarea');
  function paint(){
    const v = state[r.id]?.verdict;
    btns.forEach(b=>{
      const on = b.dataset.v===v;
      b.classList.toggle('on', on);
      // aria-pressed, not colour alone, is what a screen reader reports.
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
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

// keyboard: 1..N grade the card nearest the viewport top; j/k navigate.
// Built from CFG so a four-button vocabulary gets a 4 key without a second
// hard-coded map drifting out of sync with the buttons actually rendered.
const KEYMAP = Object.fromEntries(CFG.buttons.map((b,i)=>[String(i+1), b.v]));
const order = DATA.map(r=>r.id);
function currentCard(){
  let best=null, bd=1e9;
  for(const id of order){ const c=document.getElementById('card-'+id);
    const d=Math.abs(c.getBoundingClientRect().top-90); if(d<bd){bd=d;best=id;} }
  return best;
}
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='TEXTAREA') return;
  const map=KEYMAP;
  if(map[e.key]){ const id=currentCard(); const c=document.getElementById('card-'+id);
    setVerdict(id, map[e.key], state[id]?.note||'');
    c.querySelectorAll('.vbtn').forEach(b=>{
      const on = b.dataset.v===map[e.key];
      b.classList.toggle('on',on); b.setAttribute('aria-pressed', on?'true':'false');
    });
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
  a.download=CFG.export; a.click();
  const ungraded = out.filter(o=>!o.verdict).map(o=>o.id);
  toast(ungraded.length? ('exported — ungraded: '+ungraded.join(', ')) : 'exported all '+out.length);
};
document.getElementById('reset').onclick=()=>{
  if(confirm('Clear all grades in this browser?')){ state={}; localStorage.removeItem(KEY);
    document.querySelectorAll('.vbtn').forEach(b=>{
      b.classList.remove('on'); b.setAttribute('aria-pressed','false'); });
    document.querySelectorAll('.card').forEach(c=>c.classList.remove('graded')); progress(); }
};
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
