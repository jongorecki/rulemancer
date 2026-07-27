"""Reproduce every corpus number cited in docs/spec-cards-rag.md.

Read-only over data/scryfall.db. No network, no API spend. Run:

    .venv/Scripts/python.exe evals/cards_corpus_probe.py

Each section prints the figure the spec quotes, so a future session can check
whether a Scryfall refresh has moved any of them. Nothing here is the cards-RAG
feature -- this is the measurement that the spec's claims rest on.
"""
from __future__ import annotations

import json
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "scryfall.db"

# Layouts that are not real cards. "Find me a card like this" must never return
# an art-series print or a token.
NON_CARD = {
    "art_series", "token", "double_faced_token", "emblem",
    "vanguard", "scheme", "planar", "augment", "host",
}

REMINDER = re.compile(r"\((?:[^()]|\([^()]*\))*\)")
WS = re.compile(r"\s+")
NUM = re.compile(r"\b\d+\b")
ADD_CLAUSE = re.compile(r"\{t\}: add ([^.]*)", re.I)

# A normalised key shorter than this is degenerate (vanilla creatures, bare
# keywords). Trivially-twinned cards inflate recall@k, so gold excludes them.
MIN_KEY_CHARS = 20


def load() -> list[dict]:
    rows = sqlite3.connect(DB).execute("select card_json from cards").fetchall()
    return [json.loads(r[0]) for r in rows]


def oracle(card: dict) -> str:
    """Top-level oracle_text already joins faces with '\\n//\\n'."""
    return card.get("oracle_text") or ""


def normalise(card: dict, strip_reminder: bool = True) -> str:
    """Oracle text with self-references replaced and reminder text stripped."""
    text = oracle(card)
    if strip_reminder:
        text = REMINDER.sub(" ", text)
    name = card["name"]
    text = text.replace(name, "~")
    text = text.replace(name.split(",")[0].split(" //")[0], "~")
    return WS.sub(" ", text).strip().lower()


def face_pt(card: dict) -> tuple[int, int] | None:
    """Power/toughness live ONLY at face level -- there is no card-level power."""
    face = (card.get("faces") or [{}])[0]
    try:
        return int(face.get("power")), int(face.get("toughness"))
    except (TypeError, ValueError):
        return None


def playable(cards: list[dict]) -> list[dict]:
    return [c for c in cards if c.get("layout") not in NON_CARD]


def section_corpus(cards: list[dict]) -> None:
    play = playable(cards)
    multi = [c for c in play if len(c.get("faces") or []) > 1]
    print("== corpus shape ==")
    print(f"  rows in db            : {len(cards)}")
    print(f"  non-card layouts      : {len(cards) - len(play)} "
          f"({100 * (len(cards) - len(play)) / len(cards):.1f}%)")
    print(f"  playable cards        : {len(play)}")
    print(f"  multi-face            : {len(multi)} "
          f"({100 * len(multi) / len(play):.1f}% of playable)")
    print("  multi-face by layout  : "
          + ", ".join(f"{k} {v}" for k, v in
                      Counter(c["layout"] for c in multi).most_common()))


def section_reminder(cards: list[dict]) -> None:
    play = playable(cards)
    raw, stripped, with_rem, empties = [], [], 0, 0
    for c in play:
        text = oracle(c)
        if not text:
            continue
        s = REMINDER.sub("", text).strip()
        raw.append(len(text))
        stripped.append(len(s))
        if REMINDER.search(text):
            with_rem += 1
            if len(s) < 5:
                empties += 1
    print("\n== reminder text (decision 1: STRIP, with a guard) ==")
    print(f"  carry a parenthetical : {with_rem} "
          f"({100 * with_rem / len(raw):.1f}%)")
    print(f"  mean chars raw        : {statistics.mean(raw):.1f}")
    print(f"  mean chars stripped   : {statistics.mean(stripped):.1f}")
    print(f"  strip to empty        : {empties}  <- why the guard exists")

    # Does stripping change WHICH cards are twins? Measured on playable cards,
    # degenerate keys excluded -- the population that actually gets indexed.
    kept = twin_groups(cards, strip_reminder=False)
    strip = twin_groups(cards, strip_reminder=True)

    def pairs(groups: dict[str, list[dict]]) -> set[tuple[str, str]]:
        out = set()
        for members in groups.values():
            names = sorted(c["name"] for c in members)
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    out.add((names[i], names[j]))
        return out

    kp, sp = pairs(kept), pairs(strip)
    print(f"  twin groups kept/strip: {len(kept)} / {len(strip)}")
    print(f"  pairs gained by strip : {len(sp - kp)}")
    print(f"  pairs LOST by strip   : {len(kp - sp)}  <- must stay 0")


def section_degenerate(cards: list[dict]) -> None:
    """Keys too short to be a meaningful twin -- excluded from computed gold.

    Measured on PLAYABLE cards only. Running this over all 38,336 rows inflates
    the counts with tokens and art-series prints, which are not indexed.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for c in playable(cards):
        key = normalise(c)
        if len(key) < 10:
            continue
        groups[key].append(c["name"])
    degenerate = {k: v for k, v in groups.items()
                  if len(v) > 1 and len(k) < MIN_KEY_CHARS}
    cards_dropped = sum(len(v) for v in degenerate.values())
    print("\n== degenerate keys excluded from gold ==")
    print(f"  groups under {MIN_KEY_CHARS} chars : {len(degenerate)}  "
          f"({cards_dropped} cards)")
    for k, v in sorted(degenerate.items(), key=lambda kv: -len(kv[1]))[:5]:
        print(f"      {len(v):3d} cards keyed {k!r}")


def twin_groups(cards: list[dict], strip_reminder: bool = True,
                drop_degenerate: bool = True) -> dict[str, list[dict]]:
    """Group cards by normalised oracle text.

    Degeneracy is ALWAYS judged on the stripped key, whatever the grouping key
    is. Judging it on the grouping key instead makes the keep-vs-strip
    comparison measure the guard rather than the stripping: reminder text pads
    a vanilla card's key past the threshold, so `Storm Crow` survives the guard
    with reminder text and gets dropped without it. That produced a spurious
    1,709 "pairs lost by stripping" before this was fixed.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in playable(cards):
        key = normalise(c, strip_reminder)
        if len(key) < 10:
            continue
        if drop_degenerate and len(normalise(c, strip_reminder=True)) < MIN_KEY_CHARS:
            continue
        groups[key].append(c)
    return {k: v for k, v in groups.items() if len(v) > 1}


def section_gold(cards: list[dict]) -> None:
    groups = twin_groups(cards)
    comps = shifted = 0
    strict: list[tuple[str, str]] = []
    for members in groups.values():
        for i, a in enumerate(members):
            for j, b in enumerate(members):
                if i < j:
                    comps += 1
                    if sorted(a.get("color_identity") or []) != \
                            sorted(b.get("color_identity") or []):
                        shifted += 1
                if i == j:
                    continue
                if sorted(a.get("color_identity") or []) != \
                        sorted(b.get("color_identity") or []):
                    continue
                amv, bmv = a.get("mana_value"), b.get("mana_value")
                if amv is None or bmv is None or amv > bmv:
                    continue
                apt, bpt = face_pt(a), face_pt(b)
                if (apt is None) != (bpt is None):
                    continue
                better = amv < bmv
                if apt and bpt:
                    if apt[0] < bpt[0] or apt[1] < bpt[1]:
                        continue
                    better = better or apt > bpt
                if better:
                    strict.append((a["name"], b["name"]))
    seen = set()
    uniq = [p for p in strict if p not in seen and not seen.add(p)]
    print("\n== computed gold (shape 1) ==")
    print(f"  twin groups           : {len(groups)}")
    print(f"  functional comp pairs : {comps}")
    print(f"  colour-shifted pairs  : {shifted}")
    print(f"  strictly-better pairs : {len(uniq)}")
    for a, b in uniq[:3]:
        print(f"      {a}  >  {b}")


def section_shapes_2_3(cards: list[dict]) -> None:
    """Ability superset and numeric dominance, cost <= and body >=."""
    prepared = []
    for c in playable(cards):
        text = REMINDER.sub(" ", oracle(c)).replace(c["name"], "~")
        text = text.replace(c["name"].split(",")[0].split(" //")[0], "~")
        if len(WS.sub(" ", text).strip()) < 10:
            continue
        lines = frozenset(
            ln for ln in (WS.sub(" ", x).strip().lower() for x in text.split("\n")) if ln
        )
        prepared.append({
            "name": c["name"],
            "mv": c.get("mana_value") if c.get("mana_value") is not None else 99,
            "ci": tuple(sorted(c.get("color_identity") or [])),
            "tl": (c.get("type_line") or "").split("—")[0].strip().lower(),
            "lines": lines,
            "blank": WS.sub(" ", NUM.sub("#", text)).strip().lower(),
            "nums": [int(x) for x in NUM.findall(text)],
            "pt": face_pt(c),
        })

    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for c in prepared:
        buckets[(c["ci"], c["tl"])].append(c)

    superset = numeric = 0
    for members in buckets.values():
        if len(members) < 2 or len(members) > 4000:
            continue
        for a in members:
            for b in members:
                if a is b or a["mv"] > b["mv"]:
                    continue
                if (a["pt"] is None) != (b["pt"] is None):
                    continue
                if a["pt"] and b["pt"] and not (
                        a["pt"][0] >= b["pt"][0] and a["pt"][1] >= b["pt"][1]):
                    continue
                if a["lines"] > b["lines"]:
                    superset += 1
                elif (a["blank"] == b["blank"] and a["nums"]
                      and len(a["nums"]) == len(b["nums"])
                      and a["nums"] != b["nums"]
                      and all(x >= y for x, y in zip(a["nums"], b["nums"]))):
                    numeric += 1
    print("\n== shapes 2 and 3 ==")
    print(f"  ability-superset pairs: {superset}   (text-only tier)")
    print(f"  numeric-dominance     : {numeric}   "
          f"(NOT yet cost-direction corrected)")
    print("  WARNING: digits inside {} are COSTS and invert direction. Without")
    print("  that rule this count includes false positives such as Bold Impaler")
    print("  'beating' Bellows Lizard on a higher activation cost.")


def section_shape_4(cards: list[dict]) -> None:
    shapes = Counter()
    producers = 0
    dorks = 0
    for c in playable(cards):
        text = WS.sub(" ", REMINDER.sub(" ", oracle(c))).strip()
        m = ADD_CLAUSE.search(text)
        if not m:
            continue
        producers += 1
        prod = m.group(1).lower()
        syms = re.findall(r"\{([^}]+)\}", prod)
        shapes[(len(syms), "any color" in prod, "one color" in prod)] += 1
        if c.get("mana_value") == 2 and "Creature" in (c.get("type_line") or ""):
            dorks += 1
    print("\n== shape 4: mana production ==")
    print(f"  cards with '{{T}}: Add ...' : {producers}")
    print(f"  2-mana creature dorks      : {dorks}")
    print("  (symbols, 'any color', 'one color') -> count")
    for k, v in shapes.most_common(6):
        print(f"      {k} -> {v}")


def section_testcases(cards: list[dict]) -> None:
    extra = [c for c in playable(cards)
             if re.search(r"\bextra turn", oracle(c), re.I)]
    golgari = [c for c in extra
               if set(c.get("color_identity") or [])
               and set(c["color_identity"]) <= {"B", "G"}]
    print("\n== test case: 'all extra turn effects in golgari' ==")
    print(f"  cards mentioning 'extra turn' : {len(extra)}")
    print(f"  golgari colour identity       : {len(golgari)} "
          f"({100 * len(golgari) / max(1, len(extra)):.1f}%)")
    for c in golgari:
        print(f"      {c['name']}  {c['color_identity']}  MV {c.get('mana_value')}")
    print("  => filters MUST be applied before ranking, not after top-k.")


def section_index_size(cards: list[dict]) -> None:
    units = chars = extra_faces = 0
    for c in playable(cards):
        text = WS.sub(" ", REMINDER.sub(" ", oracle(c))).strip()
        if len(text) < 10:
            continue
        units += 1
        extra_faces += max(0, len(c.get("faces") or []) - 1)
        chars += len(text) + len(c.get("type_line") or "") + len(c.get("mana_cost") or "")
    print("\n== index size (voyage-4-large, $0.12/1M, first 200M free) ==")
    print(f"  embeddable units : {units} cards + {extra_faces} extra faces "
          f"= {units + extra_faces}")
    print(f"  characters       : {chars:,}")
    print(f"  ~tokens (chars/4): {chars // 4:,}")
    print(f"  cost if billed   : ${chars / 4 / 1_000_000 * 0.12:.4f}")


def main() -> None:
    cards = load()
    section_corpus(cards)
    section_reminder(cards)
    section_degenerate(cards)
    section_gold(cards)
    section_shapes_2_3(cards)
    section_shape_4(cards)
    section_testcases(cards)
    section_index_size(cards)


if __name__ == "__main__":
    main()
