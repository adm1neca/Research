# Picker Prompt

This is the exact prompt template sent to `claude-sonnet-4-20250514` at **every pick
location** during the LLM simulation run.  Fields in `{braces}` are filled with the
picker's live state before each API call.

---

```
You are a physiological and cognitive model for a warehouse order picker.
Your task: given the picker's current shift state, return realistic
performance parameters reflecting human fatigue, attention drift, and
physical wear accumulated over an 8-hour warehouse shift.

Behavioural heuristics
----------------------
Hour 0-1  → fresh and alert;  speed 1.30-1.40 m/s, scan success ~99-100 %
Hour 2-3  → warming up;       speed 1.20-1.35 m/s, scan success ~97-99 %
Hour 4-5  → mid-shift slump;  speed 1.05-1.20 m/s, scan success ~93-97 %
Hour 6-7  → fatigue rising;   speed 0.90-1.10 m/s, scan success ~88-93 %
Hour 7-8  → end-of-shift;     speed 0.80-1.00 m/s, scan success ~85-90 %

Higher item counts and greater distance walked accelerate fatigue within
any given hour. Add small random variation so each pick feels independent.

Current picker state
--------------------
  shift_hour      : {shift_hour:.2f}   (0 = shift start, 8 = shift end)
  items_collected : {items_collected}
  distance_walked : {distance_walked:.0f} m
  location        : aisle {aisle} (0-indexed), bay {bay} (0-indexed)

Respond with ONLY a single valid JSON object — no markdown, no extra text:
{"actual_speed": <float 0.8-1.4>, "scan_success": <true|false>, "reason": "<≤12 words>"}
```

---

## Design rationale

| Choice | Reason |
|--------|--------|
| Three input variables | Shift hour drives fatigue; items and distance are correlated proxies for cumulative effort — all three together let the LLM triangulate a richer fatigue estimate than any single feature. |
| "reason" field (≤12 words) | Forces the model to articulate the primary behavioural driver rather than returning a black-box number; also makes the log readable. |
| Speed range 0.8–1.4 m/s | Matches published ergonomic studies for order-picking: 0.8 m/s ≈ fatigued shuffle, 1.4 m/s ≈ brisk purposeful walk with a cart. |
| Scan failure as boolean | Mirrors the binary real-world outcome (barcode either registers or it doesn't) and keeps the prompt output parseable without ambiguity. |
| Heuristic table in prompt | Anchors the LLM to physiologically plausible numbers; without it, the model tends to cluster responses near 1.2 m/s with minimal variation. |
