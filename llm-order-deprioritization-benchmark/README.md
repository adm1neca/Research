# LLM Order Deprioritization Benchmark

## Research Question

**Can LLMs correctly apply a deterministic, multi-criteria prioritization algorithm to tabular data — and do different model tiers differ in accuracy, consistency, and format compliance?**

Specifically: given 50 grocery delivery orders and a set of prioritized rules, can Claude Opus, Sonnet, and Haiku reliably identify the same 6 orders to deprioritize as a rules-based baseline? Where do they disagree, and why?

## Methodology

### 1. Synthetic Dataset (`orders.csv`)

50 grocery delivery orders were generated with these fields:

| Field | Description |
|-------|-------------|
| `order_id` | ORD-001 through ORD-050 |
| `delivery_window` | Time slot (e.g., "10:00-11:00") |
| `minutes_until_cutoff` | Minutes remaining before the order must be dispatched |
| `order_value_eur` | Order value in euros |
| `customer_tier` | "standard", "premium", or "new" |
| `distance_km` | Delivery distance in kilometers |
| `items_count` | Number of items |
| `is_repeat_customer` | Boolean |

Orders were deliberately designed in three categories:
- **8 clear deprioritization candidates**: High cutoff time, low value, standard tier, long distance
- **16 clear keep candidates**: Tight cutoff, high value, premium/new tier, short distance
- **13 ambiguous orders**: Conflicting signals across criteria (e.g., premium tier but low value, or high value but lots of time left)
- **13 filler orders**: Varied profiles to reach 50 total

The dataset was shuffled (seed=42) to eliminate positional bias.

### 2. Rules-Based Baseline (`baseline.py`)

A deterministic baseline selects 6 orders to deprioritize using a lexicographic sort on these criteria (in order of importance):

1. **Most `minutes_until_cutoff`** (descending) — orders with the most time left are safest to delay
2. **Lowest `order_value_eur`** (ascending) — lower-value orders have less revenue impact
3. **Standard tier first** (standard=0, new=1, premium=2) — standard customers before premium/new
4. **Longest `distance_km`** (descending) — farther orders cost more to fulfill

**Baseline result:** `["ORD-003", "ORD-006", "ORD-002", "ORD-005", "ORD-004", "ORD-007"]`

These are all standard-tier orders with 185-240 minutes until cutoff, values between 10.75-18.20 EUR, and distances of 17.9-25.0 km.

### 3. LLM Benchmark

Three Claude models were each called 3 times with identical prompts:

| Model | Model ID |
|-------|----------|
| Opus | `claude-opus-4-20250514` |
| Sonnet | `claude-sonnet-4-20250514` |
| Haiku | `claude-haiku-4-5-20251001` |

Each call was an independent inference with no shared context, made via the Claude Code Agent tool with the `model` parameter. The exact prompt is documented in [`prompt.md`](prompt.md).

### 4. Scoring Metrics

| Metric | Description |
|--------|-------------|
| **Overlap** | How many of the model's 6 IDs match the baseline's 6 |
| **Consistency** | Jaccard similarity across 3 runs (1.0 = identical every run) |
| **Format compliance** | Whether the response was valid JSON (and whether markdown fences were used) |
| **Count correctness** | Whether exactly 6 order IDs were returned |
| **Hallucinated IDs** | Order IDs that don't exist in the dataset |

## Results

### Summary Table

| Model | Run | Overlap | Format | Clean JSON | Hallucinated | Missed | Extra |
|-------|-----|---------|--------|------------|--------------|--------|-------|
| **Opus** | 1 | **6/6** (100%) | Valid | Yes | 0 | — | — |
| **Opus** | 2 | **6/6** (100%) | Valid | Yes | 0 | — | — |
| **Opus** | 3 | **6/6** (100%) | Valid | Yes | 0 | — | — |
| **Sonnet** | 1 | **4/6** (67%) | Valid | Yes | 0 | ORD-004, ORD-005 | ORD-001, ORD-008 |
| **Sonnet** | 2 | **4/6** (67%) | Valid | Yes | 0 | ORD-004, ORD-005 | ORD-001, ORD-008 |
| **Sonnet** | 3 | **4/6** (67%) | Valid | Yes | 0 | ORD-004, ORD-005 | ORD-001, ORD-008 |
| **Haiku** | 1 | **5/6** (83%) | Valid | No* | 0 | ORD-005 | ORD-001 |
| **Haiku** | 2 | **5/6** (83%) | Valid | No* | 0 | ORD-005 | ORD-001 |
| **Haiku** | 3 | **5/6** (83%) | Valid | No* | 0 | ORD-005 | ORD-001 |

*\*Haiku wrapped responses in markdown code fences despite being told not to.*

### Consistency Scores

| Model | Jaccard Similarity | All Runs Identical | Unique Answer Sets |
|-------|-------------------|-------------------|-------------------|
| Opus | 1.000 | Yes | 1 |
| Sonnet | 1.000 | Yes | 1 |
| Haiku | 1.000 | Yes | 1 |

**All three models were perfectly consistent** across 3 runs — every model returned the exact same set of IDs (though Haiku varied the order within the set).

### Zero Hallucinations

No model produced any order IDs that don't exist in the dataset. All responses contained only valid `ORD-XXX` identifiers from the input.

## Analysis & Findings

### 1. Opus perfectly replicated the deterministic algorithm

Opus achieved 6/6 overlap across all 3 runs with clean JSON formatting. It correctly applied the lexicographic sort across all four criteria, including the subtle tiebreaking between ORD-004 (195min, 18.20 EUR, 19.5km) and ORD-005 (200min, 14.00 EUR, 20.8km). This is the most notable finding — Opus essentially "reverse-engineered" the exact sort order from the natural-language description.

### 2. Sonnet made a systematic error in the middle ranks

Sonnet consistently missed ORD-004 and ORD-005 (ranks 5 and 6 in the baseline) and instead chose ORD-001 and ORD-008 (ranks 7 and 8). Looking at the data:

| Order | Cutoff | Value | Tier | Distance |
|-------|--------|-------|------|----------|
| ORD-005 (baseline #4) | 200 | 14.00 | standard | 20.8 |
| ORD-004 (baseline #5) | 195 | 18.20 | standard | 19.5 |
| ORD-001 (sonnet extra) | 180 | 12.50 | standard | 18.3 |
| ORD-008 (sonnet extra) | 175 | 19.00 | standard | 21.3 |

Sonnet appears to have over-weighted the `order_value_eur` criterion relative to `minutes_until_cutoff`. ORD-001 (12.50 EUR) and ORD-008 (19.00 EUR) have lower/comparable values but also less cutoff time. The prompt clearly states cutoff time is the **primary** criterion, but Sonnet blended the criteria rather than applying them in strict lexicographic order. This is a classic LLM failure mode: treating ranked criteria as weighted factors rather than as a priority cascade.

### 3. Haiku outperformed Sonnet on accuracy

Haiku got 5/6 correct, beating Sonnet's 4/6. Haiku only missed ORD-005, choosing ORD-001 instead. This was unexpected — the smaller, faster model was more accurate than the mid-tier model on this task.

The error is understandable: ORD-005 (200min, 14.00 EUR) vs ORD-001 (180min, 12.50 EUR) is close. By strict sort, ORD-005's higher cutoff time (200 > 180) should rank it higher for deprioritization, but ORD-001's lower value makes it a "safer" pick by human intuition. Haiku may have been applying a more holistic evaluation rather than strict lexicographic ordering.

### 4. Format compliance varied by model

- **Opus and Sonnet** returned clean JSON arrays with no extra text — exactly as instructed
- **Haiku** consistently wrapped the JSON in markdown code fences (` ```json ... ``` `) despite the prompt explicitly saying "No markdown formatting." This required the parser to strip fences before parsing. While the JSON inside was valid, this is a format compliance failure.

### 5. All models showed zero variance

The most striking meta-finding: **every model returned the exact same answer on all 3 runs**. This suggests:
- At temperature 0 (or effective temperature 0), these models are highly deterministic for structured reasoning tasks
- The task complexity (50 rows, 4 criteria) is within the "confident" zone where models don't exhibit sampling variance
- Three runs may be insufficient to observe variance; 10-20 runs would be needed for a proper variance study

## What Surprised Me

1. **Haiku beat Sonnet.** The conventional assumption is bigger = better. But Sonnet's systematic error in criterion weighting suggests that mid-tier models may be *more* prone to "clever" reasoning (blending criteria) rather than mechanical rule application. Haiku's simpler reasoning may have been an advantage here.

2. **Perfect consistency across all models.** I expected at least some run-to-run variance, especially from Haiku. The zero-variance result makes the 3-run design somewhat redundant for this task — but it's valuable to confirm that consistency is not a problem for this type of structured decision.

3. **No hallucinated IDs.** With 50 `ORD-XXX` identifiers in context, I expected at least one model on one run to fabricate or misremember an ID. None did.

4. **Sonnet's error was in the "easy" zone.** ORD-004 and ORD-005 are in the "clear deprioritization" category — they're not ambiguous at all. Sonnet's error wasn't at the ambiguous boundary; it was in applying the sorting criteria correctly to the obvious candidates. This suggests the failure is in **algorithm execution**, not in **judgment under uncertainty**.

## What Failed

1. **Initial CLI approach.** The benchmark was originally designed to call models via the `claude` CLI tool with `--print` mode. This failed because: (a) nested Claude Code sessions are blocked, (b) `--dangerously-skip-permissions` can't run as root, and (c) the OAuth token file descriptor isn't accessible to subprocesses. The workaround was using the Claude Code Agent tool's `model` parameter.

2. **Three runs were insufficient** to measure variance. All models showed zero variance, which means we can't distinguish "highly consistent" from "would vary with more runs." A production benchmark should use 10+ runs.

3. **The prompt design may have been too explicit.** By numbering the criteria 1-4 in order of importance, we made it easy for models to understand the priority. A more challenging benchmark would use prose-style descriptions or implicit prioritization.

## File Structure

```
llm-order-deprioritization-benchmark/
├── README.md              # This file
├── prompt.md              # Exact prompt used for LLM evaluation
├── orders.csv             # Synthetic dataset (50 orders)
├── baseline.py            # Rules-based deprioritization baseline
├── generate_dataset.py    # Script that generated orders.csv
├── benchmark.py           # Original CLI-based benchmark script (see note above)
├── score_results.py       # Scoring script that produced results/
└── results/
    ├── raw.json           # Full raw responses and metadata
    └── summary.csv        # Scored summary per model per run
```

## Reproducing

```bash
# Generate dataset (already committed as orders.csv)
python3 generate_dataset.py

# Run baseline
python3 baseline.py

# Score pre-collected results
python3 score_results.py
```

To re-run the LLM benchmark, you would need to invoke each model with the prompt from `prompt.md` (either via the Anthropic API or Claude Code Agent tool) and update the raw responses in `score_results.py`.
