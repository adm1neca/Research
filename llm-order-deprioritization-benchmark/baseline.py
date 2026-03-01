#!/usr/bin/env python3
"""Rules-based baseline for deprioritizing 6 orders.

Deprioritization criteria applied in order (lexicographic sort):
  1. Most minutes_until_cutoff (descending — more time = safer to delay)
  2. Lower order_value_eur (ascending — less revenue impact)
  3. Standard before premium/new tier (standard=0, new=1, premium=2)
  4. Longer distance_km (descending — costlier to fulfill)

The top 6 orders after this sort are deprioritized.
"""

import csv
import json
import sys


TIER_PRIORITY = {"standard": 0, "new": 1, "premium": 2}


def load_orders(path="orders.csv"):
    orders = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["minutes_until_cutoff"] = int(row["minutes_until_cutoff"])
            row["order_value_eur"] = float(row["order_value_eur"])
            row["distance_km"] = float(row["distance_km"])
            row["items_count"] = int(row["items_count"])
            row["is_repeat_customer"] = row["is_repeat_customer"] == "True"
            orders.append(row)
    return orders


def deprioritization_key(order):
    """Sort key: orders most suitable for deprioritization come first."""
    return (
        -order["minutes_until_cutoff"],       # most time left → deprioritize
        order["order_value_eur"],              # lowest value → deprioritize
        TIER_PRIORITY[order["customer_tier"]], # standard first → deprioritize
        -order["distance_km"],                 # longest distance → deprioritize
    )


def select_deprioritized(orders, n=6):
    ranked = sorted(orders, key=deprioritization_key)
    return [o["order_id"] for o in ranked[:n]]


if __name__ == "__main__":
    orders = load_orders("orders.csv")
    depri = select_deprioritized(orders)
    print("Baseline deprioritized orders:")
    for oid in depri:
        print(f"  {oid}")

    # Also show reasoning
    ranked = sorted(orders, key=deprioritization_key)
    print("\nFull ranking (most deprioritizable first):")
    print(f"{'Rank':<5} {'ID':<10} {'Cutoff':<8} {'Value':<8} {'Tier':<10} {'Dist':<6}")
    print("-" * 50)
    for i, o in enumerate(ranked[:12], 1):
        print(f"{i:<5} {o['order_id']:<10} {o['minutes_until_cutoff']:<8} "
              f"{o['order_value_eur']:<8.2f} {o['customer_tier']:<10} {o['distance_km']:<6.1f}")

    print(f"\nBaseline answer: {json.dumps(depri)}")
