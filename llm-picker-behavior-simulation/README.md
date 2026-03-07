# LLM Picker Behavior Simulation

## Research Question

**Can an LLM act as a behavioral model for a human warehouse picker — and if so,
what does the resulting throughput curve look like compared to the deterministic
baseline that most WMS planning tools assume?**

The specific question is whether `claude-sonnet-4-20250514`, given only three
state variables (shift hour, cumulative items picked, cumulative distance walked),
will spontaneously reproduce fatigue-like patterns in speed and scan accuracy —
without any reference to historical pick data or an explicit fatigue function.

---

## Simulation Setup

### Warehouse Layout

| Parameter | Value |
|-----------|-------|
| Pick locations | 50 (5 aisles × 10 bays) |
| Aisle spacing | 6 m centre-to-centre |
| Bay pitch | 2 m |
| Items per route | 20 (randomly sampled) |
| Routing strategy | S-curve (serpentine through aisles) |
| Depot position | (0, −2) — entrance of aisle 0 |

### Timing Constants

| Event | Duration |
|-------|----------|
| Successful pick dwell | 5 s |
| Failed-scan retry penalty | 10 s |
| Baseline walking speed | 1.2 m/s (constant) |
| LLM-modelled speed range | 0.8 – 1.4 m/s |

### Simulation Parameters

- **Shift length**: 8 simulated hours
- **Runs per version**: 3 (seeds 42, 137, 2025)
- **Metrics recorded**: items/hour, scan error rate/hour, route time, distance walked
- **LLM calls**: 1 call per pick location (20 per route, batched concurrently per route)
- **Total LLM calls**: ~6,500 across all three LLM runs

---

## Versions Compared

### Version A — Deterministic Baseline

The picker always moves at **1.2 m/s**, scans every barcode correctly on the
first attempt (**0% error rate**), and follows the optimal S-curve path.
This mirrors the assumption embedded in most Warehouse Management Systems.

### Version B — LLM Behavioral Model

At every pick location, the simulation pauses to call `claude-sonnet-4-20250514`
with a prompt (see `prompt.md`) describing the current picker state.
The model returns a JSON object with three fields:

```json
{"actual_speed": 1.12, "scan_success": false, "reason": "mid-shift slump with moderate fatigue"}
```

The returned `actual_speed` replaces the baseline 1.2 m/s for that travel leg;
if `scan_success` is `false`, the pick dwell time increases by 10 s (rescan penalty).

---

## Results

### Aggregate (3-run averages)

| Metric | Baseline | LLM Model | Delta |
|--------|----------|-----------|-------|
| Items per 8-hour shift | 2,811 | 2,112 | **−24.9 %** |
| Items per hour (avg) | 351 | 264 | −87 items/hr |
| Peak speed | 1.20 m/s | 1.37 m/s (hr 0) | +14 % |
| End-of-shift speed | 1.20 m/s | 0.85 m/s (hr 7) | −29 % |
| Throughput degradation | +4.3 % | +58.3 % | +54 pp |
| Scan error rate (avg) | 0.0 % | ~48 % weighted | — |

> Throughput "degradation" is measured as `(hour-1-items − hour-8-items) / hour-1-items × 100`.
> A positive number means the picker completed more items in the first hour than the last
> (counter-intuitive sign convention: the baseline "degrades" slightly because of route
> boundary effects near the end of shift, not true productivity loss).

### Hour-by-Hour Breakdown (averaged across 3 runs)

| Hour | Baseline (items) | LLM (items) | LLM Avg Speed | LLM Error Rate |
|------|-----------------|-------------|---------------|----------------|
| 1    | 360             | 380         | 1.34 m/s      | 0.0 %          |
| 2    | 360             | 360         | 1.30 m/s      | 0.0 %          |
| 3    | 340             | 360         | 1.26 m/s      | 0.0 %          |
| 4    | 360             | 257         | 1.13 m/s      | 37.0 %         |
| 5    | 340             | 260         | 1.09 m/s      | 31.1 %         |
| 6    | 360             | 180         | 0.98 m/s      | 98.5 %         |
| 7    | 347             | 160         | 0.94 m/s      | 100.0 %        |
| 8    | 345             | 159         | 0.85 m/s      | 100.0 %        |

### Speed Distribution by Hour (run 1, per-pick decisions)

| Hour | Avg Speed | Range | Failures/Picks | Error Rate |
|------|-----------|-------|----------------|------------|
| 0    | 1.337 m/s | 1.28–1.38 | 0/371    | 0.0 %      |
| 1    | 1.295 m/s | 1.22–1.35 | 0/359    | 0.0 %      |
| 2    | 1.262 m/s | 1.15–1.28 | 0/360    | 0.0 %      |
| 3    | 1.132 m/s | 1.08–1.18 | 92/253   | 36.4 %     |
| 4    | 1.090 m/s | 1.02–1.18 | 81/275   | 29.5 %     |
| 5    | 0.975 m/s | 0.92–1.12 | 164/167  | 98.2 %     |
| 6    | 0.937 m/s | 0.87–0.97 | 175/175  | 100.0 %    |
| 7    | 0.854 m/s | 0.82–0.92 | 160/160  | 100.0 %    |

---

## What the LLM Behavioral Choices Looked Like

### Sample Decision Reasons Across the Shift

**Hour 0 (fresh):**
> "fresh start of shift, high energy and focus"
> "Fresh start of shift, high alertness and energy"
Speed: 1.37–1.38 m/s, scan_success: **true** (100%)

**Hour 2 (warming up):**
> "Still fresh and alert in early shift hours"
> "early shift alertness with slight fatigue from distance"
Speed: 1.26–1.28 m/s, scan_success: **true** (100%)

**Hour 3 (mid-shift slump begins):**
> "warming up well, moderate fatigue from high item count"
> "Mid-shift slump with moderate fatigue from distance walked"
Speed: 1.12–1.18 m/s, scan_success: **mixed** (~36% fail)

**Hour 5 (collapse begins):**
> "mid-shift fatigue with high item count causing attention drift"
> "mid-shift fatigue with high item count affecting concentration"
Speed: 1.08 m/s, scan_success: **false** (98% fail)

**Hour 6 (total collapse):**
> "late shift fatigue with high item count"
> "fatigue and high item count causing attention drift"
Speed: 0.87–0.92 m/s, scan_success: **false** (100% fail)

**Hour 7 (end-of-shift):**
> "high fatigue from extensive walking reduces scanning accuracy"
> "End shift fatigue, high item count causing attention drift"
> "High fatigue from extensive walking, attention drift near shift end"
Speed: 0.82–0.92 m/s, scan_success: **false** (100% fail)

### Key Behavioural Observations

1. **The LLM largely followed the prompt heuristics**, producing a plausible
   monotonic speed decline from 1.37 m/s (hour 0) to 0.85 m/s (hour 7).

2. **Two-regime behavior.** The scan error rate is not a smooth ramp — it
   switches between two near-binary states: "almost never fails" (hours 0–2)
   and "almost always fails" (hours 5–7). Hours 3–4 are a transition zone.
   This step-function shape is not well-calibrated for the heuristic table
   supplied ("5–8% error rate by hour 5–6"), suggesting the model applies its
   prior knowledge of fatigue non-linearly.

3. **Near-zero within-route variation.** Picks at the same shift hour receive
   almost identical outputs (`reason` strings are often word-for-word the same
   for consecutive picks). The model is not adding meaningful stochasticity
   despite the prompt requesting "small random variation."

4. **Cross-run stability.** All three seeds produced virtually identical
   hourly profiles. The LLM's response is determined almost entirely by the
   shift hour and item count, not by the specific location (aisle/bay).
   This makes it more like a lookup table than a stochastic process.

5. **Items collected drives the error cliff.** At around 1,200–1,400 items
   collected (hours 3–5), the LLM starts treating the accumulated count as
   decisive evidence of severe fatigue, ignoring that the remaining state
   variables (shift hour ~4) still suggest moderate performance.

---

## What Surprised Us

### 1. The near-complete scan collapse in late hours

We expected gradual degradation. Instead, the LLM produced a **phase
transition**: pick accuracy is essentially perfect for the first half of the
shift and then near-zero for the second. In hours 6–7, every single pick
returned `scan_success: false`. This is physiologically implausible — even
very fatigued workers don't fail 100% of scans — but it reveals that the
LLM's fatigue model is a threshold classifier, not a stochastic generator.

### 2. LLM is faster in hour 1 than the 1.2 m/s baseline

The baseline fixes speed at 1.2 m/s, but the LLM-modelled picker walks at
1.37 m/s when fresh. This makes hour-1 LLM throughput **higher** than baseline
(380 vs 360 items/hr), a result that's easy to miss when only looking at shift
totals. A WMS that assumes 1.2 m/s flat is pessimistic about fresh-shift
productivity and optimistic about late-shift productivity.

### 3. The "reason" field homogenized rather than diversified

Forcing the LLM to articulate a reason was expected to produce varied, nuanced
explanations. Instead, within any given hour, the reason strings converged to 2–3
near-identical templates repeated across all picks in that hour. The brief
format (≤12 words) made it easy for the model to pattern-match rather than
reason independently about each location.

### 4. Item count as the dominant driver, not distance

The prompt included three state variables (shift hour, items, distance walked).
Inspection of the transition point shows it correlates strongly with items
collected crossing ~1,200, regardless of distance walked (which grows
proportionally). The LLM appears to weight item count most heavily, perhaps
because it's the most salient "effort indicator" in the prompt.

### 5. Three seeds → three nearly-identical runs

Each run used a different random seed for route selection, so the exact pick
locations, travel distances, and cumulative distances differed. Yet the hourly
error-rate profiles across the three runs differed by at most 2 percentage
points per hour. The LLM's behavior is essentially invariant to the specific
path taken — only the aggregated state variables matter.

---

## Methodology Notes

### Prompt Design

See `prompt.md` for the full prompt and design rationale. In brief: the prompt
provides a heuristic table mapping shift hours to expected performance ranges.
The model was instructed to add "small random variation so each pick feels
independent" — an instruction it largely ignored in practice.

### LLM Call Architecture

Each route's 20 picks are batched concurrently (up to 10 simultaneous calls)
using Python `asyncio` and `anthropic.AsyncAnthropic`. Within a route, the
state for pick `i` is estimated using the baseline speed (1.2 m/s) as a proxy
for the expected arrival time, then the actual LLM-returned speed is applied
sequentially to compute true route time. This means intra-route adaptation is
one-step lagged.

### Scan Failure Accounting

The **>100% error rates** shown in the last hour of some summaries are an
artefact of partial-route boundary handling: the last route of a shift is
truncated by wall-clock, so only `fraction × items` are counted, but the full
route's scan failures are reported. The underlying per-pick measurements are
accurate; only the final-hour aggregate rate is affected.

### Reproducibility

All results are saved to `results/` as JSON. Each file includes the full list
of per-pick decisions (shift hour, speed, scan success, reason) so every number
in this README can be re-derived from the raw data.

---

## File Layout

```
llm-picker-behavior-simulation/
├── simulate.py          # Main simulation (baseline + LLM, 8h × 3 runs each)
├── prompt.md            # Picker prompt template with design rationale
├── requirements.txt     # Python dependencies (anthropic)
├── README.md            # This file
└── results/
    ├── baseline_run1.json   # Run 1: seed=42
    ├── baseline_run2.json   # Run 2: seed=137
    ├── baseline_run3.json   # Run 3: seed=2025
    ├── llm_run1.json        # Run 1: seed=42
    ├── llm_run2.json        # Run 2: seed=137
    ├── llm_run3.json        # Run 3: seed=2025
    └── summary.json         # Aggregated comparison
```

## Running the Simulation

```bash
pip install anthropic
python simulate.py
```

Runtime: ~8–10 minutes per LLM run (20 concurrent API calls per route).
Baseline runs complete in < 1 second.
