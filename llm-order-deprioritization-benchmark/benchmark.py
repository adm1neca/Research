#!/usr/bin/env python3
"""Benchmark LLMs on order deprioritization task.

Calls Claude opus, sonnet, and haiku via the `claude` CLI (--print mode)
3 times each. Collects raw responses, parses JSON, scores against baseline.
"""

import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from baseline import load_orders, select_deprioritized

MODELS = {
    "opus": "claude-opus-4-20250514",
    "sonnet": "claude-sonnet-4-20250514",
    "haiku": "claude-haiku-4-5-20251001",
}

RUNS_PER_MODEL = 3

SYSTEM_PROMPT = (
    "You are a logistics optimization assistant for a grocery delivery service. "
    "You make decisions about which orders to deprioritize when the delivery fleet is at capacity."
)


def build_user_prompt(orders_csv_content: str) -> str:
    return f"""We have 50 pending grocery delivery orders and our fleet can only handle 44 deliveries in this cycle. We need to deprioritize exactly 6 orders to the next delivery cycle.

Here are the orders:

{orders_csv_content}

Deprioritize the 6 orders that are safest to delay, considering these criteria in order of importance:
1. Most time remaining until cutoff (safest to push back)
2. Lower order value (less revenue impact)
3. Standard tier customers before premium or new customers
4. Longer delivery distance (higher fulfillment cost)

Return ONLY a JSON array of exactly 6 order_id strings for the orders to deprioritize. No explanation, no markdown formatting, no additional text. Just the JSON array.

Example format: ["ORD-XXX", "ORD-XXX", "ORD-XXX", "ORD-XXX", "ORD-XXX", "ORD-XXX"]"""


def call_claude_cli(model_id: str, system_prompt: str, user_prompt: str) -> str:
    """Call the claude CLI in --print mode with a specific model."""
    cmd = [
        "claude",
        "--print",
        "--model", model_id,
        "--output-format", "text",
        "--max-turns", "1",
        "--allowedTools", "",
        "--append-system-prompt", system_prompt,
        user_prompt,
    ]
    env = os.environ.copy()
    # Unset CLAUDECODE to allow nested CLI calls
    env.pop("CLAUDECODE", None)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr.strip()}"
    return result.stdout.strip()


def parse_response(raw: str) -> dict:
    """Parse a model response, extracting the JSON array of order IDs."""
    result = {
        "raw": raw,
        "parsed_ids": None,
        "format_valid": False,
        "count_correct": False,
        "parse_error": None,
    }

    # Try direct JSON parse first
    text = raw.strip()

    # Strip markdown code fences if present
    if "```" in text:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Try to find a JSON array in the text
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


def score_response(parsed_ids: list, baseline_ids: list, all_order_ids: set) -> dict:
    """Score a parsed response against the baseline."""
    if parsed_ids is None:
        return {
            "overlap_count": 0,
            "overlap_pct": 0.0,
            "hallucinated_ids": [],
            "hallucinated_count": 0,
        }

    parsed_set = set(parsed_ids)
    baseline_set = set(baseline_ids)

    overlap = parsed_set & baseline_set
    hallucinated = [oid for oid in parsed_ids if oid not in all_order_ids]

    return {
        "overlap_count": len(overlap),
        "overlap_pct": len(overlap) / len(baseline_set) * 100,
        "hallucinated_ids": hallucinated,
        "hallucinated_count": len(hallucinated),
    }


def compute_consistency(runs: list) -> dict:
    """Compute consistency across multiple runs of the same model."""
    valid_runs = [r for r in runs if r["parsed_ids"] is not None]
    if len(valid_runs) < 2:
        return {"pairwise_jaccard_avg": 0.0, "all_runs_identical": False, "unique_sets": len(valid_runs)}

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
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Load data
    orders = load_orders("orders.csv")
    all_order_ids = {o["order_id"] for o in orders}
    baseline_ids = select_deprioritized(orders)

    with open("orders.csv") as f:
        orders_csv_content = f.read()

    user_prompt = build_user_prompt(orders_csv_content)

    print(f"Baseline deprioritized: {baseline_ids}")
    print(f"Total orders: {len(all_order_ids)}")
    print(f"Models: {list(MODELS.keys())}")
    print(f"Runs per model: {RUNS_PER_MODEL}")
    print("=" * 60)

    # Collect all results
    all_results = {}

    for model_name, model_id in MODELS.items():
        print(f"\n--- Benchmarking {model_name} ({model_id}) ---")
        model_runs = []

        for run_idx in range(RUNS_PER_MODEL):
            print(f"  Run {run_idx + 1}/{RUNS_PER_MODEL}...", end=" ", flush=True)

            raw_response = call_claude_cli(model_id, SYSTEM_PROMPT, user_prompt)
            parsed = parse_response(raw_response)
            scores = score_response(parsed["parsed_ids"], baseline_ids, all_order_ids)

            run_result = {
                "model": model_name,
                "model_id": model_id,
                "run": run_idx + 1,
                "raw_response": raw_response,
                "parsed_ids": parsed["parsed_ids"],
                "format_valid": parsed["format_valid"],
                "count_correct": parsed["count_correct"],
                "parse_error": parsed["parse_error"],
                **scores,
            }
            model_runs.append(run_result)

            status = "OK" if parsed["format_valid"] else "PARSE_FAIL"
            print(f"{status} | overlap={scores['overlap_count']}/6 | "
                  f"hallucinated={scores['hallucinated_count']}")

            # Brief pause between runs
            if run_idx < RUNS_PER_MODEL - 1:
                time.sleep(2)

        consistency = compute_consistency(model_runs)
        all_results[model_name] = {
            "runs": model_runs,
            "consistency": consistency,
        }
        print(f"  Consistency: Jaccard={consistency['pairwise_jaccard_avg']:.2f}, "
              f"identical={consistency['all_runs_identical']}, "
              f"unique_sets={consistency['unique_sets']}")

    # Save raw results
    os.makedirs("results", exist_ok=True)

    raw_output = {
        "benchmark_metadata": {
            "baseline_ids": baseline_ids,
            "total_orders": len(all_order_ids),
            "runs_per_model": RUNS_PER_MODEL,
            "models": MODELS,
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
    print(f"\nRaw results saved to results/raw.json")

    # Generate summary CSV
    summary_rows = []
    for model_name, data in all_results.items():
        for run in data["runs"]:
            summary_rows.append({
                "model": run["model"],
                "run": run["run"],
                "format_valid": run["format_valid"],
                "count_correct": run["count_correct"],
                "overlap_count": run["overlap_count"],
                "overlap_pct": f"{run['overlap_pct']:.1f}",
                "hallucinated_count": run["hallucinated_count"],
                "hallucinated_ids": json.dumps(run["hallucinated_ids"]),
                "parsed_ids": json.dumps(run["parsed_ids"]),
            })

        # Add a summary row for consistency
        summary_rows.append({
            "model": f"{model_name}_consistency",
            "run": "ALL",
            "format_valid": "",
            "count_correct": "",
            "overlap_count": "",
            "overlap_pct": "",
            "hallucinated_count": "",
            "hallucinated_ids": "",
            "parsed_ids": f"jaccard={data['consistency']['pairwise_jaccard_avg']:.2f} "
                          f"identical={data['consistency']['all_runs_identical']} "
                          f"unique_sets={data['consistency']['unique_sets']}",
        })

    with open("results/summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "run", "format_valid", "count_correct",
            "overlap_count", "overlap_pct", "hallucinated_count",
            "hallucinated_ids", "parsed_ids",
        ])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Summary saved to results/summary.csv")

    # Print final summary table
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"{'Model':<10} {'Run':<5} {'Format':<8} {'Count':<7} {'Overlap':<10} {'Halluc':<8}")
    print("-" * 55)
    for row in summary_rows:
        if row["run"] != "ALL":
            print(f"{row['model']:<10} {row['run']:<5} "
                  f"{'Y' if row['format_valid'] else 'N':<8} "
                  f"{'Y' if row['count_correct'] else 'N':<7} "
                  f"{row['overlap_count']}/6{'':<6} "
                  f"{row['hallucinated_count']:<8}")


if __name__ == "__main__":
    main()
