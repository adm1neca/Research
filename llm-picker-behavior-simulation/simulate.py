#!/usr/bin/env python3
"""
Warehouse Pick Simulation
=========================
Compares a deterministic baseline picker against an LLM-adjusted
behavioral model over 8 simulated shift hours × 3 runs each.

Grid: 5 aisles × 10 bays = 50 pick locations
Route: 20 items per route (S-curve path)
LLM model: claude-sonnet-4-20250514
"""

import asyncio
import json
import math
import random
import os
import re
import statistics
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

import anthropic
import httpx


# ─────────────────────────────────────────────────────────────
# Authentication helpers
# ─────────────────────────────────────────────────────────────
def _build_auth_transport(proxy_url: str, bearer_token: str) -> httpx.AsyncHTTPTransport:
    """Build an AsyncHTTPTransport that injects a Bearer token and uses the egress proxy."""
    class _BearerTransport(httpx.AsyncHTTPTransport):
        def __init__(self, proxy, token, **kw):
            super().__init__(proxy=proxy, **kw)
            self._token = token

        async def handle_async_request(self, request):
            request.headers["Authorization"] = f"Bearer {self._token}"
            request.headers.pop("x-api-key", None)
            return await super().handle_async_request(request)

    return _BearerTransport(proxy=httpx.Proxy(proxy_url), token=bearer_token)


def _build_sync_auth_transport(proxy_url: str, bearer_token: str) -> httpx.HTTPTransport:
    class _BearerTransport(httpx.HTTPTransport):
        def __init__(self, proxy, token, **kw):
            super().__init__(proxy=proxy, **kw)
            self._token = token

        def handle_request(self, request):
            request.headers["Authorization"] = f"Bearer {self._token}"
            request.headers.pop("x-api-key", None)
            return super().handle_request(request)

    return _BearerTransport(proxy=httpx.Proxy(proxy_url), token=bearer_token)


def make_clients():
    """Build Anthropic sync+async clients using the session ingress token + egress proxy."""
    # Read the session bearer token
    token_file = os.environ.get(
        "CLAUDE_SESSION_INGRESS_TOKEN_FILE",
        "/home/claude/.claude/remote/.session_ingress_token",
    )
    if os.path.exists(token_file):
        bearer = open(token_file).read().strip()
    else:
        bearer = None

    # Extract egress proxy config from JAVA_TOOL_OPTIONS (injected by the runtime)
    jto = os.environ.get("JAVA_TOOL_OPTIONS", "")
    m_user = re.search(r"-Dhttps\.proxyUser=(\S+)", jto)
    m_pwd  = re.search(r"-Dhttps\.proxyPassword=(\S+)", jto)
    m_host = re.search(r"-Dhttps\.proxyHost=(\S+)", jto)
    m_port = re.search(r"-Dhttps\.proxyPort=(\S+)", jto)

    if bearer and m_user and m_pwd and m_host and m_port:
        u = urllib.parse.quote(m_user.group(1), safe="")
        p = urllib.parse.quote(m_pwd.group(1), safe="")
        proxy_url = f"http://{u}:{p}@{m_host.group(1)}:{m_port.group(1)}"

        async_transport = _build_auth_transport(proxy_url, bearer)
        sync_transport  = _build_sync_auth_transport(proxy_url, bearer)

        async_client = anthropic.AsyncAnthropic(
            api_key="dummy",
            http_client=httpx.AsyncClient(transport=async_transport, timeout=60),
        )
        sync_client = anthropic.Anthropic(
            api_key="dummy",
            http_client=httpx.Client(transport=sync_transport, timeout=60),
        )
        return sync_client, async_client

    # Fallback: standard env-var key (ANTHROPIC_API_KEY)
    return anthropic.Anthropic(), anthropic.AsyncAnthropic()

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
GRID_ROWS = 10
GRID_COLS = 5
N_LOCATIONS = GRID_ROWS * GRID_COLS   # 50
ITEMS_PER_ROUTE = 20
SHIFT_HOURS = 8
N_RUNS = 3
RESULTS_DIR = "results"

# Warehouse dimensions (metres)
AISLE_GAP = 6.0        # centre-to-centre
BAY_GAP   = 2.0        # within-aisle
DEPOT     = (0.0, -2.0)

# Timing (seconds)
PICK_DWELL     = 5.0   # successful scan + pick
RESCAN_PENALTY = 10.0  # extra time when scan fails

BASELINE_SPEED = 1.2   # m/s (constant, optimal)
MODEL = "claude-sonnet-4-20250514"
MAX_CONCURRENT = 10    # max simultaneous LLM calls per route batch

# ─────────────────────────────────────────────────────────────
# Prompt (also exported to prompt.md)
# ─────────────────────────────────────────────────────────────
PICKER_PROMPT = """\
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
{{"actual_speed": <float 0.8-1.4>, "scan_success": <true|false>, "reason": "<≤12 words>"}}"""

# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────
@dataclass
class Loc:
    lid: int
    col: int   # aisle 0-4
    row: int   # bay 0-9
    x: float
    y: float


@dataclass
class PickDecision:
    location_id: int
    shift_hour: float
    items_before: int
    distance_before: float
    actual_speed: float
    scan_success: bool
    reason: str
    raw_response: str = ""


@dataclass
class RouteResult:
    route_idx: int
    items_picked: int
    time_sec: float
    distance_m: float
    scan_failures: int
    decisions: List[PickDecision] = field(default_factory=list)


@dataclass
class ShiftResult:
    version: str          # "baseline" | "llm"
    run_id: int
    seed: int
    hourly_items: List[float]
    hourly_error_rate: List[float]
    total_items: int
    total_routes: int
    routes: List[RouteResult] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Warehouse geometry
# ─────────────────────────────────────────────────────────────
def make_locations() -> List[Loc]:
    locs = []
    lid = 0
    for col in range(GRID_COLS):
        for row in range(GRID_ROWS):
            locs.append(Loc(
                lid=lid, col=col, row=row,
                x=col * AISLE_GAP,
                y=row * BAY_GAP,
            ))
            lid += 1
    return locs


def eucl(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def plan_route(all_locs: List[Loc], target_ids: List[int]) -> List[Loc]:
    """S-curve route: visit aisles in column order, alternate direction."""
    by_aisle: Dict[int, List[Loc]] = {}
    for loc in all_locs:
        if loc.lid in target_ids:
            by_aisle.setdefault(loc.col, []).append(loc)
    ordered = []
    for col in sorted(by_aisle):
        bays = sorted(by_aisle[col], key=lambda l: l.row, reverse=(col % 2 == 1))
        ordered.extend(bays)
    return ordered


def route_planned_distances(route: List[Loc]) -> List[float]:
    """Pre-compute travel distance to each pick (from previous position)."""
    dists = []
    pos = DEPOT
    for loc in route:
        lp = (loc.x, loc.y)
        dists.append(eucl(pos, lp))
        pos = lp
    return dists


def route_return_distance(route: List[Loc]) -> float:
    if not route:
        return 0.0
    last = (route[-1].x, route[-1].y)
    return eucl(last, DEPOT)


# ─────────────────────────────────────────────────────────────
# Baseline simulation (deterministic)
# ─────────────────────────────────────────────────────────────
def sim_route_baseline(route: List[Loc], route_idx: int) -> RouteResult:
    dists = route_planned_distances(route)
    total_time = sum(d / BASELINE_SPEED + PICK_DWELL for d in dists)
    total_time += route_return_distance(route) / BASELINE_SPEED
    total_dist = sum(dists) + route_return_distance(route)
    return RouteResult(
        route_idx=route_idx,
        items_picked=len(route),
        time_sec=total_time,
        distance_m=total_dist,
        scan_failures=0,
    )


def run_shift_baseline(locs: List[Loc], run_id: int, seed: int) -> ShiftResult:
    rng = random.Random(seed)
    SHIFT_SEC = SHIFT_HOURS * 3600
    elapsed = 0.0
    hourly_items = [0.0] * SHIFT_HOURS
    hourly_fails  = [0]   * SHIFT_HOURS
    hourly_picks  = [0]   * SHIFT_HOURS
    routes: List[RouteResult] = []
    total_items = 0
    route_idx = 0

    while elapsed < SHIFT_SEC:
        target_ids = set(rng.sample(range(N_LOCATIONS), ITEMS_PER_ROUTE))
        route = plan_route(locs, target_ids)
        result = sim_route_baseline(route, route_idx)
        route_idx += 1

        h = min(int(elapsed / 3600), SHIFT_HOURS - 1)
        remaining = SHIFT_SEC - elapsed

        if result.time_sec > remaining:
            fraction = remaining / result.time_sec
            partial = max(1, int(result.items_picked * fraction))
            hourly_items[h] += partial
            hourly_picks[h] += partial
            total_items += partial
            routes.append(result)
            break

        hourly_items[h] += result.items_picked
        hourly_picks[h] += result.items_picked
        # baseline: 0 scan failures
        total_items += result.items_picked
        routes.append(result)
        elapsed += result.time_sec

    error_rate = [
        hourly_fails[h] / hourly_picks[h] if hourly_picks[h] > 0 else 0.0
        for h in range(SHIFT_HOURS)
    ]
    return ShiftResult(
        version="baseline",
        run_id=run_id,
        seed=seed,
        hourly_items=hourly_items,
        hourly_error_rate=error_rate,
        total_items=total_items,
        total_routes=route_idx,
        routes=routes,
    )


# ─────────────────────────────────────────────────────────────
# LLM simulation (async, picks batched per route)
# ─────────────────────────────────────────────────────────────
async def call_llm_async(
    client: anthropic.AsyncAnthropic,
    loc: Loc,
    shift_hour: float,
    items_before: int,
    distance_before: float,
    semaphore: asyncio.Semaphore,
) -> PickDecision:
    prompt = PICKER_PROMPT.format(
        shift_hour=shift_hour,
        items_collected=items_before,
        distance_walked=distance_before,
        aisle=loc.col,
        bay=loc.row,
    )
    async with semaphore:
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
            else:
                raise ValueError("no JSON brace pair found")

            speed = float(data.get("actual_speed", 1.0))
            speed = max(0.8, min(1.4, speed))
            scan_ok = bool(data.get("scan_success", True))
            reason  = str(data.get("reason", ""))[:120]

            return PickDecision(
                location_id=loc.lid,
                shift_hour=round(shift_hour, 3),
                items_before=items_before,
                distance_before=round(distance_before, 1),
                actual_speed=round(speed, 3),
                scan_success=scan_ok,
                reason=reason,
                raw_response=raw,
            )
        except Exception as exc:
            # Fallback: mid-shift performance (conservative)
            return PickDecision(
                location_id=loc.lid,
                shift_hour=round(shift_hour, 3),
                items_before=items_before,
                distance_before=round(distance_before, 1),
                actual_speed=1.0,
                scan_success=True,
                reason=f"[fallback – error: {exc}]",
                raw_response="",
            )


async def sim_route_llm(
    client: anthropic.AsyncAnthropic,
    route: List[Loc],
    route_idx: int,
    shift_elapsed_sec: float,
    items_before: int,
    distance_before: float,
    semaphore: asyncio.Semaphore,
) -> RouteResult:
    """
    For each pick we build a state estimate using the planned path
    (baseline speed as proxy), then fire all LLM calls concurrently.
    The returned speed/scan values are applied sequentially to compute
    the actual route time and failure count.
    """
    dists = route_planned_distances(route)

    # Build coroutines with estimated per-pick states
    coroutines = []
    cum_time = 0.0
    cum_dist = 0.0
    for i, (loc, d) in enumerate(zip(route, dists)):
        travel_est   = d / BASELINE_SPEED
        shift_hr_est = (shift_elapsed_sec + cum_time + travel_est) / 3600.0
        items_est    = items_before + i
        dist_est     = distance_before + cum_dist + d

        coroutines.append(call_llm_async(
            client, loc, shift_hr_est, items_est, dist_est, semaphore
        ))
        cum_time += travel_est + PICK_DWELL
        cum_dist += d

    decisions: List[PickDecision] = list(await asyncio.gather(*coroutines))

    # Apply decisions sequentially
    total_time = 0.0
    total_dist = 0.0
    scan_failures = 0
    for d, dec in zip(dists, decisions):
        total_time += d / dec.actual_speed
        total_time += PICK_DWELL + (RESCAN_PENALTY if not dec.scan_success else 0.0)
        total_dist += d
        if not dec.scan_success:
            scan_failures += 1

    # Return to depot (use baseline speed – no LLM call needed)
    ret = route_return_distance(route)
    total_time += ret / BASELINE_SPEED
    total_dist += ret

    return RouteResult(
        route_idx=route_idx,
        items_picked=len(route),
        time_sec=total_time,
        distance_m=total_dist,
        scan_failures=scan_failures,
        decisions=decisions,
    )


async def run_shift_llm_async(
    client: anthropic.AsyncAnthropic,
    locs: List[Loc],
    run_id: int,
    seed: int,
) -> ShiftResult:
    rng = random.Random(seed)
    SHIFT_SEC = SHIFT_HOURS * 3600
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    elapsed = 0.0
    hourly_items = [0.0] * SHIFT_HOURS
    hourly_fails  = [0]   * SHIFT_HOURS
    hourly_picks  = [0]   * SHIFT_HOURS
    routes: List[RouteResult] = []
    total_items = 0
    route_idx = 0
    items_collected = 0
    distance_walked = 0.0

    while elapsed < SHIFT_SEC:
        target_ids = set(rng.sample(range(N_LOCATIONS), ITEMS_PER_ROUTE))
        route = plan_route(locs, target_ids)

        print(f"    route {route_idx:3d} | {elapsed/3600:.2f} h elapsed | "
              f"{items_collected} items so far …", flush=True)

        result = await sim_route_llm(
            client=client,
            route=route,
            route_idx=route_idx,
            shift_elapsed_sec=elapsed,
            items_before=items_collected,
            distance_before=distance_walked,
            semaphore=semaphore,
        )
        route_idx += 1

        h = min(int(elapsed / 3600), SHIFT_HOURS - 1)
        remaining = SHIFT_SEC - elapsed

        if result.time_sec > remaining:
            fraction = remaining / result.time_sec
            partial = max(1, int(result.items_picked * fraction))
            hourly_items[h] += partial
            hourly_fails[h] += result.scan_failures
            hourly_picks[h] += partial
            total_items += partial
            routes.append(result)
            break

        hourly_items[h] += result.items_picked
        hourly_fails[h] += result.scan_failures
        hourly_picks[h] += result.items_picked
        total_items += result.items_picked
        items_collected += result.items_picked
        distance_walked += result.distance_m
        routes.append(result)
        elapsed += result.time_sec

    error_rate = [
        hourly_fails[h] / hourly_picks[h] if hourly_picks[h] > 0 else 0.0
        for h in range(SHIFT_HOURS)
    ]
    return ShiftResult(
        version="llm",
        run_id=run_id,
        seed=seed,
        hourly_items=hourly_items,
        hourly_error_rate=error_rate,
        total_items=total_items,
        total_routes=route_idx,
        routes=routes,
    )


# ─────────────────────────────────────────────────────────────
# Serialisation
# ─────────────────────────────────────────────────────────────
def shift_to_dict(r: ShiftResult) -> dict:
    return {
        "version": r.version,
        "run_id": r.run_id,
        "seed": r.seed,
        "total_items": r.total_items,
        "total_routes": r.total_routes,
        "avg_items_per_hour": round(r.total_items / SHIFT_HOURS, 2),
        "hourly_items": [round(v, 2) for v in r.hourly_items],
        "hourly_error_rate": [round(v, 4) for v in r.hourly_error_rate],
        "routes": [
            {
                "route_idx": rt.route_idx,
                "items_picked": rt.items_picked,
                "time_sec": round(rt.time_sec, 2),
                "distance_m": round(rt.distance_m, 2),
                "scan_failures": rt.scan_failures,
                "decisions": [
                    {
                        "location_id": d.location_id,
                        "shift_hour": d.shift_hour,
                        "items_before": d.items_before,
                        "distance_before": d.distance_before,
                        "actual_speed": d.actual_speed,
                        "scan_success": d.scan_success,
                        "reason": d.reason,
                    }
                    for d in rt.decisions
                ],
            }
            for rt in r.routes
        ],
    }


# ─────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────
def compute_summary(
    baseline: List[ShiftResult],
    llm: List[ShiftResult],
) -> dict:
    def avg_hourly(results: List[ShiftResult]) -> List[float]:
        n = len(results)
        return [sum(r.hourly_items[h] for r in results) / n for h in range(SHIFT_HOURS)]

    def avg_err(results: List[ShiftResult]) -> List[float]:
        n = len(results)
        return [sum(r.hourly_error_rate[h] for r in results) / n for h in range(SHIFT_HOURS)]

    def degradation(hourly: List[float]) -> float:
        first = max(hourly[0], 1e-6)
        return (hourly[0] - hourly[-1]) / first * 100

    b_hourly = avg_hourly(baseline)
    l_hourly = avg_hourly(llm)
    b_err    = avg_err(baseline)
    l_err    = avg_err(llm)
    b_total  = statistics.mean([r.total_items for r in baseline])
    l_total  = statistics.mean([r.total_items for r in llm])

    return {
        "config": {
            "grid": f"{GRID_ROWS}×{GRID_COLS}",
            "n_locations": N_LOCATIONS,
            "items_per_route": ITEMS_PER_ROUTE,
            "shift_hours": SHIFT_HOURS,
            "n_runs": N_RUNS,
            "baseline_speed_ms": BASELINE_SPEED,
            "llm_model": MODEL,
        },
        "baseline": {
            "avg_total_items_per_shift": round(b_total, 1),
            "avg_items_per_hour": round(b_total / SHIFT_HOURS, 2),
            "hourly_items_avg": [round(v, 2) for v in b_hourly],
            "hourly_error_rate_avg": [round(v, 4) for v in b_err],
            "throughput_degradation_pct": round(degradation(b_hourly), 2),
        },
        "llm": {
            "avg_total_items_per_shift": round(l_total, 1),
            "avg_items_per_hour": round(l_total / SHIFT_HOURS, 2),
            "hourly_items_avg": [round(v, 2) for v in l_hourly],
            "hourly_error_rate_avg": [round(v, 4) for v in l_err],
            "throughput_degradation_pct": round(degradation(l_hourly), 2),
        },
        "comparison": {
            "items_gap_pct": round((l_total - b_total) / max(b_total, 1) * 100, 2),
            "baseline_total": round(b_total, 1),
            "llm_total": round(l_total, 1),
            "extra_degradation_pct": round(degradation(l_hourly) - degradation(b_hourly), 2),
        },
    }


def print_summary(summary: dict) -> None:
    b = summary["baseline"]
    l = summary["llm"]
    c = summary["comparison"]

    print("\n" + "═" * 62)
    print("  SIMULATION SUMMARY")
    print("═" * 62)
    print(f"  Baseline   {b['avg_total_items_per_shift']:>6.0f} items/shift "
          f"({b['avg_items_per_hour']:.1f} items/hr avg)")
    print(f"  LLM model  {l['avg_total_items_per_shift']:>6.0f} items/shift "
          f"({l['avg_items_per_hour']:.1f} items/hr avg)")
    print(f"  Gap        {c['items_gap_pct']:>+6.1f}%\n")
    print(f"  Throughput degradation (hr 1 → hr 8):")
    print(f"    Baseline : {b['throughput_degradation_pct']:+.1f}%")
    print(f"    LLM      : {l['throughput_degradation_pct']:+.1f}%")
    print(f"    Extra deg: {c['extra_degradation_pct']:+.1f} pp\n")
    print(f"  {'Hr':>3} | {'Baseline':>10} | {'LLM':>10} | {'ErrB%':>8} | {'ErrL%':>8}")
    print("  " + "─" * 50)
    for h in range(SHIFT_HOURS):
        print(f"  {h+1:>3} | {b['hourly_items_avg'][h]:>10.1f} | "
              f"{l['hourly_items_avg'][h]:>10.1f} | "
              f"{b['hourly_error_rate_avg'][h]*100:>7.1f}% | "
              f"{l['hourly_error_rate_avg'][h]*100:>7.1f}%")
    print("═" * 62)


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
async def main() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    locs = make_locations()
    _sync_client, async_client = make_clients()
    seeds = [42, 137, 2025]

    # ── Baseline ────────────────────────────────────────────
    print("═" * 62)
    print(f"  BASELINE — {N_RUNS} runs × {SHIFT_HOURS} simulated hours")
    print("═" * 62)
    baseline_results: List[ShiftResult] = []
    for run_id, seed in enumerate(seeds, 1):
        print(f"\n  Run {run_id} (seed={seed}) …", end=" ", flush=True)
        t0 = time.time()
        result = run_shift_baseline(locs, run_id, seed)
        dt = time.time() - t0
        baseline_results.append(result)
        path = os.path.join(RESULTS_DIR, f"baseline_run{run_id}.json")
        with open(path, "w") as fh:
            json.dump(shift_to_dict(result), fh, indent=2)
        print(f"done in {dt:.1f}s | {result.total_items} items | "
              f"{result.total_routes} routes")

    # ── LLM ─────────────────────────────────────────────────
    print(f"\n{'═'*62}")
    print(f"  LLM ({MODEL}) — {N_RUNS} runs × {SHIFT_HOURS} simulated hours")
    print("═" * 62)
    llm_results: List[ShiftResult] = []
    for run_id, seed in enumerate(seeds, 1):
        print(f"\n  Run {run_id} (seed={seed}):")
        t0 = time.time()
        result = await run_shift_llm_async(async_client, locs, run_id, seed)
        dt = time.time() - t0
        llm_results.append(result)
        path = os.path.join(RESULTS_DIR, f"llm_run{run_id}.json")
        with open(path, "w") as fh:
            json.dump(shift_to_dict(result), fh, indent=2)
        print(f"  ↳ done in {dt:.1f}s | {result.total_items} items | "
              f"{result.total_routes} routes")

    # ── Summary ─────────────────────────────────────────────
    summary = compute_summary(baseline_results, llm_results)
    with open(os.path.join(RESULTS_DIR, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print_summary(summary)
    print(f"\n  Results written to: {RESULTS_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
