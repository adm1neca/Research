#!/usr/bin/env python3
"""Score collected LLM benchmark results and generate output files.

Processes raw responses from 3 models x 3 runs, scores against baseline,
and generates results/raw.json and results/summary.csv.
"""

import csv
import json
import os
import re

from baseline import load_orders, select_deprioritized

# Baseline ground truth
BASELINE_IDS = None  # computed at runtime

# All valid order IDs
ALL_ORDER_IDS = None  # computed at runtime

# Raw responses collected from agent runs
# Format: model -> list of raw response strings
RAW_RESPONSES = {
    "opus": [
        '["ORD-003", "ORD-006", "ORD-002", "ORD-005", "ORD-004", "ORD-007"]',
        '["ORD-003", "ORD-006", "ORD-002", "ORD-005", "ORD-004", "ORD-007"]',
        '["ORD-003", "ORD-006", "ORD-002", "ORD-005", "ORD-004", "ORD-007"]',
    ],
    "sonnet": [
        '["ORD-003", "ORD-006", "ORD-002", "ORD-007", "ORD-008", "ORD-001"]',
        '["ORD-003", "ORD-006", "ORD-002", "ORD-007", "ORD-008", "ORD-001"]',
        '["ORD-003", "ORD-006", "ORD-002", "ORD-007", "ORD-008", "ORD-001"]',
    ],
    "haiku": [
        '```json\n["ORD-003", "ORD-006", "ORD-004", "ORD-007", "ORD-002", "ORD-001"]\n```',
        '```json\n["ORD-003", "ORD-006", "ORD-004", "ORD-001", "ORD-007", "ORD-002"]\n```',
        '```json\n["ORD-003", "ORD-006", "ORD-004", "ORD-007", "ORD-001", "ORD-002"]\n```',
    ],
}

MODEL_IDS = {
    "opus": "claude-opus-4-20250514",
    "sonnet": "claude-sonnet-4-20250514",
    "haiku": "claude-haiku-4-5-20251001",
}


def parse_response(raw: str) -> dict:
    """Parse a model response, extracting the JSON array of order IDs."""
    result = {
        "raw": raw,
        "parsed_ids": None,
        "format_valid": False,
        "count_correct": False,
        "parse_error": None,
        "used_markdown_fence": "```" in raw,
    }

    text = raw.strip()

    # Strip markdown code fences if present
    if "```" in text:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Try to find a JSON array
    array_match = re.search(r'\[.*?\]', text, re.DOTALL)
    if array_match:
        text = array_match.group(0)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            result["parsed_ids"] = parsed
            result["format_valid"] = True
            result["count_correct"] = len(parsed) == 6
        else:
            result["parse_error"] = "Parsed JSON is not a list of strings"
    except json.JSONDecodeError as e:
        result["parse_error"] = str(e)

    return result


def score_response(parsed_ids, baseline_ids, all_order_ids):
    """Score a parsed response against the baseline."""
    if parsed_ids is None:
        return {
            "overlap_count": 0,
            "overlap_pct": 0.0,
            "overlap_ids": [],
            "missed_ids": list(baseline_ids),
            "extra_ids": [],
            "hallucinated_ids": [],
            "hallucinated_count": 0,
        }

    parsed_set = set(parsed_ids)
    baseline_set = set(baseline_ids)

    overlap = sorted(parsed_set & baseline_set)
    missed = sorted(baseline_set - parsed_set)
    extra = sorted(parsed_set - baseline_set)
    hallucinated = [oid for oid in parsed_ids if oid not in all_order_ids]

    return {
        "overlap_count": len(overlap),
        "overlap_pct": len(overlap) / len(baseline_set) * 100,
        "overlap_ids": overlap,
        "missed_ids": missed,
        "extra_ids": extra,
        "hallucinated_ids": hallucinated,
        "hallucinated_count": len(hallucinated),
    }


def compute_consistency(runs):
    """Compute consistency across multiple runs of the same model."""
    valid_runs = [r for r in runs if r["parsed_ids"] is not None]
    if len(valid_runs) < 2:
        return {
            "pairwise_jaccard_avg": 0.0,
            "all_runs_identical": False,
            "unique_sets": len(valid_runs),
        }

    id_sets = [set(r["parsed_ids"]) for r in valid_runs]

    # Pairwise Jaccard similarity
    jaccards = []
    for i in range(len(id_sets)):
        for j in range(i + 1, len(id_sets)):
            intersection = len(id_sets[i] & id_sets[j])
            union = len(id_sets[i] | id_sets[j])
            jaccards.append(intersection / union if union > 0 else 0)

    unique_sets = len(set(frozenset(s) for s in id_sets))

    return {
        "pairwise_jaccard_avg": sum(jaccards) / len(jaccards) if jaccards else 0,
        "all_runs_identical": unique_sets == 1,
        "unique_sets": unique_sets,
    }


def main():
    global BASELINE_IDS, ALL_ORDER_IDS

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Load data
    orders = load_orders("orders.csv")
    ALL_ORDER_IDS = {o["order_id"] for o in orders}
    BASELINE_IDS = select_deprioritized(orders)

    print(f"Baseline: {BASELINE_IDS}")
    print(f"Total orders: {len(ALL_ORDER_IDS)}")
    print("=" * 70)

    # Process all results
    all_results = {}

    for model_name in ["opus", "sonnet", "haiku"]:
        print(f"\n--- {model_name} ({MODEL_IDS[model_name]}) ---")
        model_runs = []

        for run_idx, raw in enumerate(RAW_RESPONSES[model_name]):
            parsed = parse_response(raw)
            scores = score_response(parsed["parsed_ids"], BASELINE_IDS, ALL_ORDER_IDS)

            run_result = {
                "model": model_name,
                "model_id": MODEL_IDS[model_name],
                "run": run_idx + 1,
                "raw_response": raw,
                "parsed_ids": parsed["parsed_ids"],
                "format_valid": parsed["format_valid"],
                "format_clean_json": parsed["format_valid"] and not parsed["used_markdown_fence"],
                "count_correct": parsed["count_correct"],
                "parse_error": parsed["parse_error"],
                "used_markdown_fence": parsed["used_markdown_fence"],
                **scores,
            }
            model_runs.append(run_result)

            fence_note = " [markdown fence]" if parsed["used_markdown_fence"] else ""
            print(f"  Run {run_idx+1}: overlap={scores['overlap_count']}/6 "
                  f"| ids={parsed['parsed_ids']}"
                  f"{fence_note}")
            if scores["missed_ids"]:
                print(f"         missed: {scores['missed_ids']}")
            if scores["extra_ids"]:
                print(f"         extra:  {scores['extra_ids']}")

        consistency = compute_consistency(model_runs)
        all_results[model_name] = {
            "runs": model_runs,
            "consistency": consistency,
        }
        print(f"  Consistency: Jaccard={consistency['pairwise_jaccard_avg']:.3f}, "
              f"identical={consistency['all_runs_identical']}, "
              f"unique_sets={consistency['unique_sets']}")

    # === Save raw.json ===
    os.makedirs("results", exist_ok=True)

    raw_output = {
        "benchmark_metadata": {
            "description": "LLM Order Deprioritization Benchmark",
            "date": "2026-03-01",
            "baseline_ids": BASELINE_IDS,
            "total_orders": len(ALL_ORDER_IDS),
            "runs_per_model": 3,
            "models": MODEL_IDS,
            "method": "Each model called via Claude Code Agent tool with model parameter (opus/sonnet/haiku). "
                      "Each call is an independent inference with no shared context.",
        },
        "results": {},
    }
    for model_name, data in all_results.items():
        raw_output["results"][model_name] = {
            "runs": data["runs"],
            "consistency": data["consistency"],
        }

    with open("results/raw.json", "w") as f:
        json.dump(raw_output, f, indent=2)
    print(f"\nSaved results/raw.json")

    # === Save summary.csv ===
    summary_rows = []
    for model_name in ["opus", "sonnet", "haiku"]:
        data = all_results[model_name]
        for run in data["runs"]:
            summary_rows.append({
                "model": run["model"],
                "model_id": run["model_id"],
                "run": run["run"],
                "format_valid": run["format_valid"],
                "format_clean_json": run["format_clean_json"],
                "count_correct": run["count_correct"],
                "overlap_count": run["overlap_count"],
                "overlap_pct": f"{run['overlap_pct']:.1f}",
                "hallucinated_count": run["hallucinated_count"],
                "hallucinated_ids": json.dumps(run["hallucinated_ids"]),
                "missed_baseline_ids": json.dumps(run["missed_ids"]),
                "extra_ids": json.dumps(run["extra_ids"]),
                "parsed_ids": json.dumps(run["parsed_ids"]),
            })

        # Consistency summary row
        c = data["consistency"]
        summary_rows.append({
            "model": f"{model_name}_consistency",
            "model_id": "",
            "run": "ALL",
            "format_valid": "",
            "format_clean_json": "",
            "count_correct": "",
            "overlap_count": "",
            "overlap_pct": "",
            "hallucinated_count": "",
            "hallucinated_ids": "",
            "missed_baseline_ids": "",
            "extra_ids": "",
            "parsed_ids": f"jaccard_avg={c['pairwise_jaccard_avg']:.3f} "
                          f"identical={c['all_runs_identical']} "
                          f"unique_sets={c['unique_sets']}",
        })

    fieldnames = [
        "model", "model_id", "run", "format_valid", "format_clean_json",
        "count_correct", "overlap_count", "overlap_pct",
        "hallucinated_count", "hallucinated_ids",
        "missed_baseline_ids", "extra_ids", "parsed_ids",
    ]
    with open("results/summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Saved results/summary.csv")

    # === Print final summary table ===
    print("\n" + "=" * 90)
    print("FINAL SUMMARY")
    print("=" * 90)
    print(f"Baseline: {BASELINE_IDS}")
    print()
    print(f"{'Model':<10} {'Run':<5} {'Format':<8} {'Clean':<7} {'#OK':<5} "
          f"{'Overlap':<10} {'Halluc':<7} {'Missed':<25} {'Extra':<25}")
    print("-" * 90)

    for row in summary_rows:
        if row["run"] == "ALL":
            print(f"  >> {row['model']}: {row['parsed_ids']}")
        else:
            missed = json.loads(row["missed_baseline_ids"])
            extra = json.loads(row["extra_ids"])
            print(f"{row['model']:<10} {row['run']:<5} "
                  f"{'Y' if row['format_valid'] else 'N':<8} "
                  f"{'Y' if row['format_clean_json'] else 'N':<7} "
                  f"{'Y' if row['count_correct'] else 'N':<5} "
                  f"{row['overlap_count']}/6{'':<6} "
                  f"{row['hallucinated_count']:<7} "
                  f"{','.join(missed) if missed else '-':<25} "
                  f"{','.join(extra) if extra else '-':<25}")


if __name__ == "__main__":
    main()
