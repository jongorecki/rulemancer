# Mini-plan — waiting ticker walks the turn structure (Jon, 2026-07-22)

Status: DRAFT for Jon's review (Rule 0). Frontend-only; implementation
waits for the quiet tree like everything else.

## What

Replace the random `ARCANE` word draw in frontend/index.html with a
SEQUENTIAL walk through the steps/phases of a Magic turn. Jon's exact
wordlist, in order:

1. untapping
2. upkeeping
3. drawing
4. main phasing
5. combatting
6. declaring attackers
7. declaring blockers
8. resolving damage
9. ending combat
10. main phasing
11. end stepping
12. cleaning up
13. passing turn (added by Jon mid-implementation, 2026-07-22)

## Behavior

- Each new question starts at "untapping" (index 0).
- Advance one step per tick, in order — never random.
- **Interval: ~2500ms** (was 850ms random). 12 steps ≈ 30s ≈ one typical
  answer latency, so most answers arrive mid-turn and the pacing reads as
  real progress rather than a fast loop.
- If the turn completes before the answer arrives: **loop back to
  "untapping"** — taking another turn is the thematically honest behavior
  (and long answers exist; holding on "cleaning up" for 30s looks hung).
- Keep the existing shimmer styling + "…" suffix untouched; this changes
  only the word source and cadence.

## Touchpoints

- `ARCANE` array (line ~82) → `TURN_PHASES` (ordered list above).
- `rand()` (line ~155) → index-based `nextPhase()` with reset on ask.
- The 850 in the `setInterval` (line ~186) → 2500.

## Verify

By PIXELS per the standing rule: ask a question, watch the ticker walk
untap → upkeep → draw... in order at the new cadence; confirm loop
behavior on a slow answer; 375/768/1280 both themes unaffected (word
lengths grew — "declaring attackers" is the longest; confirm no wrap/clip
at 375px). Jon's screen is the final gate.

## Open for Jon

- Interval feel: 2500ms is a starting recommendation — tune by eye.
- Loop vs. hold on "cleaning up": loop recommended (above); say if you'd
  rather it parks.
