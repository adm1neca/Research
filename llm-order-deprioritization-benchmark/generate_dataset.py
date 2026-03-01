#!/usr/bin/env python3
"""Generate a synthetic dataset of 50 grocery delivery orders.

Design principles:
- Some orders are OBVIOUS deprioritization candidates (high time-to-cutoff,
  low value, standard tier, long distance).
- Some orders are OBVIOUS keeps (tight cutoff, high value, premium tier).
- ~10-15 orders sit in the AMBIGUOUS middle ground where criteria conflict,
  e.g. high value but tons of time left, or premium tier but very low value.
"""

import csv
import random

random.seed(42)

TIERS = ["standard", "premium", "new"]

def generate_orders():
    orders = []

    # --- CLEAR DEPRIORITIZATION CANDIDATES (6-8 orders) ---
    # High minutes_until_cutoff, low value, standard, long distance
    clear_depri = [
        ("ORD-001", "14:00-16:00", 180, 12.50, "standard", 18.3, 4, False),
        ("ORD-002", "15:00-17:00", 210, 15.00, "standard", 22.1, 3, False),
        ("ORD-003", "16:00-18:00", 240, 10.75, "standard", 25.0, 2, False),
        ("ORD-004", "15:00-17:00", 195, 18.20, "standard", 19.5, 5, False),
        ("ORD-005", "14:00-16:00", 200, 14.00, "standard", 20.8, 3, True),
        ("ORD-006", "16:00-18:00", 220, 11.30, "standard", 24.2, 2, False),
        ("ORD-007", "15:00-17:00", 185, 16.50, "standard", 17.9, 4, False),
        ("ORD-008", "14:00-16:00", 175, 19.00, "standard", 21.3, 6, True),
    ]

    # --- CLEAR KEEP CANDIDATES (15-18 orders) ---
    # Low minutes_until_cutoff, high value, premium/new, short distance
    clear_keep = [
        ("ORD-009", "10:00-11:00", 15, 145.00, "premium", 3.2, 22, True),
        ("ORD-010", "10:00-11:30", 20, 98.50, "premium", 4.1, 18, True),
        ("ORD-011", "10:30-11:00", 25, 112.30, "premium", 2.8, 15, True),
        ("ORD-012", "10:00-11:00", 10, 78.00, "new", 5.0, 12, False),
        ("ORD-013", "10:00-12:00", 30, 65.40, "premium", 3.5, 10, True),
        ("ORD-014", "11:00-12:00", 35, 89.90, "premium", 4.8, 14, True),
        ("ORD-015", "10:00-11:00", 18, 55.20, "new", 6.1, 8, False),
        ("ORD-016", "11:00-12:00", 22, 134.00, "premium", 2.3, 20, True),
        ("ORD-017", "10:30-12:00", 40, 72.80, "standard", 3.9, 11, True),
        ("ORD-018", "10:00-11:30", 12, 210.00, "premium", 1.5, 30, True),
        ("ORD-019", "11:00-12:00", 28, 48.30, "new", 5.5, 7, False),
        ("ORD-020", "10:00-11:00", 8, 165.00, "premium", 2.0, 25, True),
        ("ORD-021", "10:30-11:30", 33, 91.10, "standard", 4.2, 13, True),
        ("ORD-022", "11:00-12:00", 45, 58.70, "premium", 3.1, 9, True),
        ("ORD-023", "10:00-11:00", 16, 125.50, "new", 2.7, 19, False),
        ("ORD-024", "11:00-12:30", 50, 42.00, "standard", 6.8, 6, True),
    ]

    # --- AMBIGUOUS ORDERS (the interesting ones, ~12-15) ---
    # These have conflicting signals across criteria
    ambiguous = [
        # High value BUT lots of time left and long distance
        ("ORD-025", "14:00-16:00", 160, 135.00, "premium", 15.2, 18, True),
        # Premium tier BUT very low value and moderate time
        ("ORD-026", "13:00-15:00", 120, 22.50, "premium", 12.0, 3, False),
        # New customer with moderate everything — hard to call
        ("ORD-027", "12:00-14:00", 90, 45.00, "new", 10.5, 7, False),
        # Standard tier but very high value and moderate time
        ("ORD-028", "13:00-15:00", 110, 155.00, "standard", 8.3, 21, True),
        # Short distance but lots of time and low value
        ("ORD-029", "14:00-16:00", 150, 25.00, "standard", 4.0, 4, True),
        # Premium, high value, but extremely long distance
        ("ORD-030", "12:00-14:00", 85, 120.00, "premium", 28.5, 16, True),
        # New customer, decent value, moderate time
        ("ORD-031", "12:30-14:00", 95, 68.00, "new", 9.2, 10, False),
        # Standard, medium value, medium time — textbook ambiguous
        ("ORD-032", "13:00-14:30", 100, 52.00, "standard", 11.0, 8, True),
        # Repeat customer, standard, low value, moderate time
        ("ORD-033", "12:00-14:00", 105, 28.00, "standard", 13.7, 5, True),
        # Premium but borderline time and middling value
        ("ORD-034", "12:00-13:30", 75, 40.00, "premium", 7.5, 6, True),
        # New customer, high value, long distance, moderate time
        ("ORD-035", "13:00-15:00", 130, 95.00, "new", 16.8, 14, False),
        # Standard, moderate value, just enough time to be risky
        ("ORD-036", "12:30-14:00", 80, 62.00, "standard", 9.8, 9, True),
        # Very high value standard with lots of time
        ("ORD-037", "14:00-16:00", 170, 185.00, "standard", 14.0, 24, True),
    ]

    # --- FILLER with varied profiles (to reach 50) ---
    filler = [
        ("ORD-038", "11:00-12:30", 55, 33.50, "standard", 7.2, 5, False),
        ("ORD-039", "11:30-13:00", 60, 47.80, "new", 8.0, 8, True),
        ("ORD-040", "11:00-12:00", 42, 82.00, "premium", 3.6, 12, True),
        ("ORD-041", "12:00-13:30", 70, 56.30, "standard", 6.4, 9, True),
        ("ORD-042", "11:30-13:00", 65, 39.90, "new", 9.1, 6, False),
        ("ORD-043", "12:00-14:00", 88, 71.20, "premium", 5.3, 11, True),
        ("ORD-044", "11:00-12:30", 48, 105.00, "premium", 4.5, 16, True),
        ("ORD-045", "12:30-14:00", 78, 31.00, "standard", 10.2, 4, False),
        ("ORD-046", "11:00-12:00", 38, 63.50, "new", 5.8, 10, True),
        ("ORD-047", "13:00-15:00", 115, 27.50, "standard", 14.5, 3, False),
        ("ORD-048", "12:00-13:00", 58, 88.00, "premium", 6.0, 13, True),
        ("ORD-049", "11:30-13:00", 52, 44.20, "standard", 8.7, 7, True),
        ("ORD-050", "13:00-14:30", 125, 35.60, "standard", 12.3, 5, False),
    ]

    orders = clear_depri + clear_keep + ambiguous + filler

    # Shuffle to avoid positional bias in LLM evaluation
    random.shuffle(orders)

    return orders


def write_csv(orders, path="orders.csv"):
    headers = [
        "order_id", "delivery_window", "minutes_until_cutoff",
        "order_value_eur", "customer_tier", "distance_km",
        "items_count", "is_repeat_customer"
    ]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for o in orders:
            writer.writerow(o)
    print(f"Wrote {len(orders)} orders to {path}")


if __name__ == "__main__":
    orders = generate_orders()
    write_csv(orders, "orders.csv")
