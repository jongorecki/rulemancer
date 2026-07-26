import json

def load(p):
    d = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            d[o["id"]] = o
    return d

A = load("evals/gold_proposals_full_b09.jsonl")
B = load("evals/gold_proposals_full_b09_rerun.jsonl")

ids = sorted(set(A) & set(B))
assert len(ids) == 50, len(ids)

rows = []
for qid in ids:
    a, b = A[qid], B[qid]
    setA, setB = set(a["gold"]), set(b["gold"])
    union = setA | setB
    inter = setA & setB
    jaccard = (len(inter) / len(union)) if union else 1.0
    exact_set = (setA == setB)
    shares_nothing = (len(inter) == 0) and (len(union) > 0)
    mode_agree = (a["match"] == b["match"])

    # group structure compare (as frozenset of frozensets)
    def groupset(o):
        return frozenset(frozenset(g) for g in o.get("gold_groups", []))
    groups_equal = groupset(a) == groupset(b)

    order_same_list = (a["gold"] == b["gold"])

    added_by_B = sorted(setB - setA)
    dropped_by_B = sorted(setA - setB)

    rows.append({
        "id": qid,
        "gold_A": a["gold"], "gold_B": b["gold"],
        "match_A": a["match"], "match_B": b["match"],
        "mode_agree": mode_agree,
        "exact_set_match": exact_set,
        "groups_equal": groups_equal,
        "order_identical_list": order_same_list,
        "jaccard": jaccard,
        "shares_nothing": shares_nothing,
        "n_A": len(setA), "n_B": len(setB),
        "added_by_B": added_by_B,
        "dropped_by_B": dropped_by_B,
    })

n = len(rows)
identical_set = sum(r["exact_set_match"] for r in rows)
identical_incl_groups = sum(r["exact_set_match"] and r["groups_equal"] for r in rows)
identical_incl_order = sum(r["order_identical_list"] for r in rows)
share_nothing = sum(r["shares_nothing"] for r in rows)
mean_jaccard = sum(r["jaccard"] for r in rows) / n
mode_agree_n = sum(r["mode_agree"] for r in rows)

# classify each row
order_only = [r for r in rows if r["exact_set_match"] and not r["order_identical_list"]]
same_set_diff_groups = [r for r in rows if r["exact_set_match"] and not r["groups_equal"]]
fully_identical = [r for r in rows if r["exact_set_match"] and r["groups_equal"]]
genuinely_different = [r for r in rows if not r["exact_set_match"]]

print("N =", n)
print("identical gold SET (order/grouping ignored):", identical_set, f"{identical_set/n:.1%}")
print("  of which fully identical incl. group structure & list order:", len(fully_identical))
print("  of which same set, list order differs (order-only):", len(order_only))
print("  of which same set, gold_groups structure differs:", len(same_set_diff_groups))
print("genuinely different rule sets:", len(genuinely_different), f"{len(genuinely_different)/n:.1%}")
print("mean Jaccard overlap:", round(mean_jaccard, 4))
print("rows sharing NO rules at all:", share_nothing)
print("match-mode agreement (any/all/groups):", mode_agree_n, f"{mode_agree_n/n:.1%}")

# size (count) comparison among genuinely different rows
size_same_diff_content = sum(1 for r in genuinely_different if r["n_A"] == r["n_B"])
size_diff = len(genuinely_different) - size_same_diff_content
print("among genuinely-different rows: same COUNT but different members:", size_same_diff_content,
      "| different count:", size_diff)

with open("evals/_double_mine_stability_rows.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2)

print()
print("=== full per-row detail ===")
for r in rows:
    tag = "IDENTICAL" if r["exact_set_match"] and r["groups_equal"] and r["order_identical_list"] else \
          "ORDER-ONLY" if r["exact_set_match"] and not r["groups_equal"] and not r["order_identical_list"] else \
          "SAME-SET-DIFF-GROUP" if r["exact_set_match"] and not r["groups_equal"] else \
          "SAME-SET-DIFF-ORDER" if r["exact_set_match"] else \
          "SHARE-NOTHING" if r["shares_nothing"] else \
          "PARTIAL-OVERLAP"
    print(f"{r['id']:8s} {tag:20s} jaccard={r['jaccard']:.2f} modeA={r['match_A']:6s} modeB={r['match_B']:6s} "
          f"A={r['gold_A']} B={r['gold_B']}")
