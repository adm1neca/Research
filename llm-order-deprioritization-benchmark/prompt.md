# LLM Prompt for Order Deprioritization

## System Prompt

```
You are a logistics optimization assistant for a grocery delivery service. You make decisions about which orders to deprioritize when the delivery fleet is at capacity.
```

## User Prompt (template)

The `{orders_csv}` placeholder is replaced with the full contents of `orders.csv`.

```
We have 50 pending grocery delivery orders and our fleet can only handle 44 deliveries in this cycle. We need to deprioritize exactly 6 orders to the next delivery cycle.

Here are the orders:

{orders_csv}

Deprioritize the 6 orders that are safest to delay, considering these criteria in order of importance:
1. Most time remaining until cutoff (safest to push back)
2. Lower order value (less revenue impact)
3. Standard tier customers before premium or new customers
4. Longer delivery distance (higher fulfillment cost)

Return ONLY a JSON array of exactly 6 order_id strings for the orders to deprioritize. No explanation, no markdown formatting, no additional text. Just the JSON array.

Example format: ["ORD-XXX", "ORD-XXX", "ORD-XXX", "ORD-XXX", "ORD-XXX", "ORD-XXX"]
```

## Design Notes

- The prompt explicitly states the criteria and their priority order, matching the baseline algorithm.
- It requests strict JSON output with no additional text to test format compliance.
- The "exactly 6" constraint tests whether models can follow numeric constraints.
- Including the full CSV inline tests the model's ability to process tabular data within context.
