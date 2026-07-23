"""Assemble the numbers evals/report-v3-ab.md is written from: predicted-flip
scorecard status, go/no-go arithmetic per docs/plan-prompt-tuning.md §4.7,
correct-count floor/ceiling per arm/condition, tripwire + retrieval-noise
rollups. Pure aggregation over the JSON artifacts judge_v3ab.py,
groundedness_v3ab.py, retrieval_noise_v3ab.py, and build_v3ab_queue.py
already wrote -- no network calls, no judgment calls (those are Jon's,
flagged as PENDING where the true count needs his grading of the stable-flip
queue).

Run: .venv/Scripts/python.exe evals/compute_v3ab_report_data.py
Output: evals/v3ab_report_data.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lib_v3ab as L  # noqa: E402

EVALS = Path(__file__).parent

C004_OFF_BOARD_ARMS = {"sonnet", "deepseek-v4-pro"}

# docs/plan-prompt-tuning.md §1/§6, task-3 brief item 4 ("c004 pair off the board")
PREDICTED_FLIPS = [
    # (bullet, arm, qid, expectation, confidence, note)
    ("1a", "deepseek-v4-flash", "c002", "flip_predicted", "high", "F1 card-role confusion, textbook match"),
    ("1a", "gemini-flash-lite", "c002", "flip_predicted", "high", "F1 card-role confusion, textbook match"),
    ("1a", "deepseek-v3-2", "c002", "flip_predicted", "high", "F1 card-role confusion, textbook match"),
    ("1a", "deepseek-v4-pro", "c002", "no_change_expected", "n/a", "already correct pre-v3"),
    ("1a", "gpt-5-mini", "c002", "no_change_expected", "n/a", "already correct pre-v3"),
    ("1a", "sonnet", "c002", "no_change_expected", "n/a", "already correct pre-v3"),
    ("1b", "gemini-flash-lite", "c014", "flip_predicted", "high", "wrong -> correct, F2 mana semantics"),
    ("1b", "gpt-5-mini", "c014", "flip_predicted", "moderate", "partial -> correct"),
    ("1b", "deepseek-v3-2", "c014", "flip_predicted", "moderate", "partial -> correct"),
    ("1b", "sonnet", "c014", "untested_at_plan_time", "n/a", "no verdict on record when plan was written"),
    ("1b", "deepseek-v4-flash", "c014", "untested_at_plan_time", "n/a", "no verdict on record when plan was written"),
    ("1c", "deepseek-v4-pro", "q014", "flip_predicted", "moderate", "partial -> correct; hedged, may only reach honest scoping"),
    ("1c", "gemini-flash-lite", "q014", "flip_predicted", "moderate", "partial -> correct; hedged, may only reach honest scoping"),
    ("1c", "gpt-5-mini", "q014", "flip_predicted", "moderate", "partial -> correct; hedged, may only reach honest scoping"),
    ("1d", "sonnet", "c004", "off_the_board", "n/a", "granted by pre-A/B ruling, excluded from scorecard"),
    ("1d", "deepseek-v4-pro", "c004", "off_the_board", "n/a", "granted by pre-A/B ruling, excluded from scorecard"),
    ("1d", "deepseek-v3-2", "c004", "flip_predicted_low_confidence", "low", "reasoning error, not just undisclosed assumption; may only make wrongness legible, not correct it"),
    ("1e", "deepseek-v4-flash", "c016", "flip_predicted", "high", "wrong -> correct, exact match to Jon's note"),
    ("1f", "deepseek-v4-flash", "q026", "quality_only", "n/a", "already correct; predicted to stay correct, read cleaner"),
    ("1f", "gpt-5-mini", "q026", "quality_only", "n/a", "already correct, already Jon's exemplar; codifies existing best behavior"),
    ("1f", "deepseek-v3-2", "q008", "quality_only", "low", "wrong; intent-reading miss, moderate-low confidence bullet fixes it"),
]


def stable_flip_set(summary: dict, arm: str, qid_filter=None) -> dict[str, list[str]]:
    """{condition: [qids]} of stable flips for this arm across B/C/D."""
    out = {}
    for cond in L.CONDITIONS:
        ids = summary[arm][cond]["stable_flip"]
        if arm in C004_OFF_BOARD_ARMS:
            ids = [i for i in ids if i != "c004"]
        out[cond] = ids
    return out


def main() -> None:
    summary = json.loads((EVALS / "judge_v3ab_summary.json").read_text(encoding="utf-8"))
    noise = json.loads((EVALS / "retrieval_noise_tags.json").read_text(encoding="utf-8"))
    noise_tag = {r["id"]: r["tag"] for r in noise["rows"]}
    grounded = json.loads((EVALS / "groundedness_v3ab.json").read_text(encoding="utf-8"))

    # ---- predicted-flip scorecard ----
    scorecard = []
    for bullet, arm, qid, expectation, confidence, note in PREDICTED_FLIPS:
        stable_by_cond = {c: qid in summary[arm][c]["stable_flip"] for c in L.CONDITIONS}
        any_stable = any(stable_by_cond.values())
        unstable_by_cond = {c: qid in summary[arm][c]["unstable_flip"] for c in L.CONDITIONS}
        any_unstable = any(unstable_by_cond.values())
        a_verdict = L.condition_a_reference(arm)[qid]["verdict"]
        scorecard.append({
            "bullet": bullet, "arm": arm, "qid": qid, "expectation": expectation,
            "confidence": confidence, "note": note, "condition_a_verdict": a_verdict,
            "stable_divergence_by_condition": stable_by_cond,
            "unstable_divergence_by_condition": unstable_by_cond,
            "any_stable_divergence": any_stable, "any_unstable_divergence": any_unstable,
            "retrieval_noise_tag": noise_tag.get(qid),
        })

    # ---- go/no-go arithmetic (§4.7) ----
    sonnet_flips = stable_flip_set(summary, "sonnet")
    sonnet_correct_at_risk = {
        c: [q for q in ids if L.condition_a_reference("sonnet")[q]["verdict"] == "correct"]
        for c, ids in sonnet_flips.items()
    }
    n_sonnet_at_risk = sum(len(v) for v in sonnet_correct_at_risk.values())

    n_flagged_questions = grounded["n_distinct_questions_flagged"]
    tripwire_no_go = n_flagged_questions > 2

    non_incumbent = [a for a in L.ARMS if a != "sonnet"]
    ceiling_gain = {}
    floor_loss = {}
    for arm in non_incumbent:
        flips = stable_flip_set(summary, arm)
        all_ids = {q for ids in flips.values() for q in ids}
        base = L.condition_a_reference(arm)
        gain = sum(1 for q in all_ids if base[q]["verdict"] != "correct")  # could flip wrong/partial->correct
        loss = sum(1 for q in all_ids if base[q]["verdict"] == "correct")  # could flip correct->something else
        ceiling_gain[arm] = gain
        floor_loss[arm] = loss

    landed = sum(1 for s in scorecard if s["expectation"].startswith("flip_predicted") and s["any_stable_divergence"])
    predicted_total = sum(1 for s in scorecard if s["expectation"].startswith("flip_predicted"))

    out = {
        "predicted_flip_scorecard": scorecard,
        "predicted_landed_as_stable_divergence": landed,
        "predicted_total": predicted_total,
        "go_no_go": {
            "no_go_1_sonnet_regression": {
                "rule": "no-go if sonnet drops net correct vs 46/50 baseline, on stable flips (c004 off the board)",
                "sonnet_stable_flips_by_condition": sonnet_flips,
                "sonnet_flips_touching_a_correct_question": sonnet_correct_at_risk,
                "n_at_risk": n_sonnet_at_risk,
                "status": "CLEAR (0 stable flips touch a previously-correct sonnet question)"
                          if n_sonnet_at_risk == 0 else
                          f"PENDING JON -- {n_sonnet_at_risk} stable flip(s) touch a previously-correct "
                          "sonnet question; no-go fires only if any grades wrong/partial",
            },
            "no_go_2_groundedness_spike": {
                "rule": "no-go if > 1-2 distinct questions flagged across all arms",
                "n_distinct_questions_flagged": n_flagged_questions,
                "flagged_ids": grounded["distinct_questions_with_ungrounded_citation_anywhere"],
                "status": "TRIGGERED" if tripwire_no_go else "CLEAR",
            },
            "go_3_net_increase_and_predicted_flips": {
                "rule": ">=3 of 5 non-incumbent arms net +1 correct, AND >=half of predicted flips land",
                "ceiling_gain_per_arm": ceiling_gain,
                "floor_loss_per_arm": floor_loss,
                "predicted_landed_as_stable_divergence": landed,
                "predicted_total": predicted_total,
                "status": "PENDING JON -- correct-count deltas require grading the stable-flip queue; "
                          f"{sum(1 for a in non_incumbent if ceiling_gain[a] > 0)}/5 non-incumbent arms have "
                          "at least one stable flip that COULD net +1 (ceiling only, not confirmed)",
            },
        },
    }
    out_path = EVALS / "v3ab_report_data.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"-> {out_path}")
    print(f"predicted flips landing as stable divergence: {landed}/{predicted_total}")
    print(f"sonnet at-risk stable flips (touch a correct question): {n_sonnet_at_risk}")
    print(f"groundedness no-go: {'TRIGGERED' if tripwire_no_go else 'clear'} "
          f"({n_flagged_questions} distinct questions)")


if __name__ == "__main__":
    main()
