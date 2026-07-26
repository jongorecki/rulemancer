# Plan — Card enrichment: layout-first, all printed rules-relevant fields (DRAFT, pending Jon's review)

Working Rule 0 artifact. No code until Jon signs off.

## The idea (Jon, 2026-07-21)

Enrich the generator with everything that's **printed on the card and
rules-relevant** -- not just name + oracle text. Jon's principle: *"if it's on
the card, not reminder text, not flavor text, and not artist/collector/etc., it
should be in the enrichment."* And **detect the layout FIRST**: if the card is
double-faced/split we have to read both sides, and we need to know *which kind*
it is (modal DFC vs transform vs battle vs split vs aftermath/adventure), because
each carries different casting/zone rules.

## Why now (the two baseline misses that motivate it)

- **c014 (Trinisphere):** the model used Awaken the Woods = `{X}{G}{G}{G}`; it's
  `{X}{G}{G}`. `_format_cards` emits name + oracle text + rulings and **drops
  `mana_cost` and `type_line`**, so on a cost question the model guessed the cost
  from training and got it wrong. The cost math (and thus the Trinisphere floor
  analysis) came out wrong even though the top-line advice survived.
- **c011 (Valki // Tibalt):** confidently wrong -- the model invented a "you'd
  need permission to cast it transformed" restriction. Valki // Tibalt is a
  **modal** DFC (cast a face by choice), not a transform card. The enrichment
  gave it neither the **layout** nor the **per-face** data, so it had nothing to
  anchor on and hallucinated the wrong regime.

Both are grounding failures caused by the enrichment withholding printed facts.

## Architecture: layout first, then branch

`_card_from_json` currently joins the two faces' *oracle text* and takes the
top-level name; everything else is top-level or dropped. Restructure:

1. **Read `layout` and `card_faces` first.**
2. **Single-face** (`normal`, and the enchantment-with-chapters layouts `saga` /
   `class` / `case`, which are single-faced): pull fields from the top level.
3. **Multi-face** (`card_faces` present): emit the **layout label** + **each
   face's own fields**. One uniform branch handles split / flip / transform /
   modal_dfc / adventure / battle at the DATA level (Scryfall gives `card_faces`
   consistently); the **layout string is what tells the model the rules regime**,
   which is the actual c011 fix. We don't re-implement each layout's rules -- the
   CR + rulings do that -- we just give complete per-face data and name the
   layout so the right rules get retrieved and applied.
4. **meld** (`layout: meld`): special (three cards, a separate melded back object
   via `all_parts`, no `card_faces`). Handle minimally for now -- emit the front
   card's own fields and note a melded back exists; full meld support deferred
   until an eval question needs it (don't build machinery nothing uses yet).

Layouts to recognize and label (verify exact Scryfall strings at build time):
`normal`, `split` (incl. **aftermath** -- Scryfall labels these `split`; the
"Aftermath" keyword in the second face's oracle text distinguishes them, so
surfacing the layout + oracle text is enough), `flip`, `transform`, `modal_dfc`,
`adventure`, `meld`, plus battles/sieges (double-faced). If Scryfall returns a
layout string we don't recognize, fall back to "emit whatever faces exist +
the raw layout string" rather than dropping data.

## Fields

**Per face** (or the single face): name, **mana cost**, **mana value**, **type
line**, **oracle text**, **power/toughness** (creatures), **loyalty**
(planeswalkers), **defense** (battles), **colors**, **color indicator**.

**Whole card:** full name (e.g. "Valki, God of Lies // Tibalt, Cosmic Impostor"),
**layout**, **color identity**, `oracle_id`, rulings.

- **mana cost AND mana value both** -- the cost structure (colored pips, X) is
  what cost questions need (Trinisphere); mana value is derived but worth stating.
- **type line** and **power/toughness** were the concrete gaps (c014 cost, c002
  needed Vampire Nighthawk = 2/3 and wasn't given it).
- **color indicator** is how a colored card with no mana cost defines its color
  (a printed dot) -- needed for those cards' color.
- **reminder text stays.** It's embedded in Scryfall's `oracle_text`, it's
  helpful grounding, and reliably splitting reminder text from real parenthetical
  rules text isn't worth the risk. This is the one place we keep more than Jon's
  principle strictly says -- flagged, not silent.

**Excluded** (agreed): flavor text, artist, collector number, set, rarity,
watermark, frame/border, legalities, prices. Also excluded because they're
*derived* from oracle text (so already covered): `keywords`, `produced_mana`.

## Contract change

- New `CardFace` submodel: name, mana_cost, mana_value, type_line, oracle_text,
  power, toughness, loyalty, defense, colors, color_indicator (all with sensible
  empty defaults so a plain creature doesn't carry loyalty/defense).
- `Card` gains: `layout: str`, `color_identity: list[str]`, `faces:
  list[CardFace]`. A single-faced card has exactly one `CardFace`. Existing
  top-level `oracle_text` / `type_line` / `mana_cost` either become derived
  conveniences from `faces[0]` or are dropped in favor of `faces` -- decide at
  build time to keep the change small; the eval/ablation harness reads
  `_format_cards` output, not the Card fields directly, so the blast radius is
  the formatter.
- `_format_cards` emits, per card: a header line
  `Name {mana cost} (MV N) — Type line — [P/T | loyalty | defense] — colors`
  then oracle text, then relevant rulings; for multi-face cards, the layout label
  and one such block per face.

## Verification (don't assert -- re-run and look)

- Re-run the 9 card questions. Confirm **c014**'s cost math is now correct
  ({X}{G}{G}, X=0 = 2 mana, Trinisphere floors to 3) and **c011** no longer
  invents a transform restriction (it now sees `layout: modal_dfc` + both faces).
- Spot-check one card of each multi-face layout that's reachable
  (Valki=modal_dfc, a transform e.g. Bruce Banner // Hulk, a split e.g. Fire //
  Ice, an adventure e.g. Bonecrusher Giant, a battle e.g. an Invasion) to confirm
  per-face extraction is right -- render and read, don't trust the field dump.

## Decisions for Jon

1. **Layout list** -- anything to add/drop beyond normal / split(+aftermath) /
   flip / transform / modal_dfc / adventure / meld / battle?
2. **meld** handled minimally now (front-face data + note), full support
   deferred -- OK?
3. **Reminder text kept** in oracle text (vs your "exclude reminder") -- OK with
   the reasoning above?
4. **color identity** included even though it's mostly Commander-relevant -- it's
   cheap and printed-derivable, so I lean include. OK?

## After this lands

Re-run to confirm the fix, then do the grounded pass on the new batch
(delayed-trigger token copies, Final Fortune + Sundial/Obeka, fetchland + Gogo,
Clone, Bruce Banner) and draft c015+.
