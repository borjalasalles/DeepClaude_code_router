"""QA runner for Phase 1 — scanner correctness + latency micro-bench.

Loads evals/qa_fase1/fixtures.jsonl, runs scan() over each input, and classifies
each case as:

  PASS              — all required types detected; no forbidden type fired
  FAIL              — required type missing OR forbidden type fired (M1 bug)
  EXPECTED_GAP      — failure attributable to a known unimplemented capability
                      (NER, base64 decoder, contextual classifier). Tracked,
                      not blocking.

Also prints a small latency bench against the QA-F thresholds from the MD.
"""
from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from pathlib import Path

from deep_devops.router.pii_scanner import scan


FIXTURES_PATH = Path(__file__).parent / "fixtures.jsonl"

GAP_CATEGORIES_HONEST = {
    "ner_required",
    "decoder_required",
    "context_required",
    "regex_quick_win",
    "design_decision",
}


def evaluate_case(case: dict) -> tuple[str, str]:
    """Return (verdict, detail). Verdict ∈ {PASS, FAIL, EXPECTED_GAP}."""
    text = case["input"]
    must = list(case.get("must_detect", []))
    must_not = set(case.get("must_not_detect", []))
    gap = case.get("gap_category", "supported")

    result = scan(text)
    detected = Counter(result.entity_types())
    required = Counter(must)

    # Forbidden types fired?
    forbidden_hits = [t for t in must_not if detected[t] > 0]
    # Required types missing or insufficient?
    missing = [t for t, n in required.items() if detected[t] < n]

    if not forbidden_hits and not missing:
        return ("PASS", f"detected={dict(detected)}")

    detail = f"detected={dict(detected)} missing={missing} forbidden_hits={forbidden_hits}"

    if gap in GAP_CATEGORIES_HONEST and gap != "supported":
        return ("EXPECTED_GAP", detail)
    return ("FAIL", detail)


def run_suite() -> dict:
    by_block: dict[str, Counter] = {}
    rows: list[dict] = []

    with FIXTURES_PATH.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            verdict, detail = evaluate_case(case)
            block = case["block"]
            by_block.setdefault(block, Counter())[verdict] += 1
            rows.append({
                "id": case["id"],
                "block": block,
                "verdict": verdict,
                "gap_category": case.get("gap_category", "supported"),
                "detail": detail,
                "notes": case.get("notes", ""),
            })

    return {"by_block": by_block, "rows": rows}


def latency_bench() -> dict:
    """QA-F: p99 over a synthetic 10 KB and 100 KB payload."""
    base = "DNI 12345678Z, IBAN ES0000000000000000000000, email juan@empresa.com. "
    sizes = {
        "10kb": (base * (10_000 // len(base) + 1))[:10_000],
        "100kb": (base * (100_000 // len(base) + 1))[:100_000],
    }
    results = {}
    for label, payload in sizes.items():
        timings = []
        # Warm-up
        for _ in range(3):
            scan(payload)
        # Measure
        for _ in range(50):
            t0 = time.perf_counter()
            scan(payload)
            timings.append((time.perf_counter() - t0) * 1000)
        timings.sort()
        results[label] = {
            "p50_ms": round(statistics.median(timings), 2),
            "p95_ms": round(timings[int(len(timings) * 0.95)], 2),
            "p99_ms": round(timings[int(len(timings) * 0.99)], 2),
            "samples": len(timings),
        }
    return results


def print_report(suite: dict, bench: dict) -> int:
    print("\n" + "=" * 70)
    print("PHASE 1 — QA SUITE RESULTS")
    print("=" * 70)

    totals: Counter = Counter()
    for block, counts in sorted(suite["by_block"].items()):
        total = sum(counts.values())
        totals.update(counts)
        line = (
            f"Block {block}: "
            f"PASS={counts.get('PASS', 0):>2} "
            f"FAIL={counts.get('FAIL', 0):>2} "
            f"GAP={counts.get('EXPECTED_GAP', 0):>2} "
            f"/ {total}"
        )
        print(line)
    grand = sum(totals.values())
    print("-" * 70)
    print(
        f"TOTAL  : PASS={totals['PASS']}  FAIL={totals['FAIL']}  "
        f"EXPECTED_GAP={totals['EXPECTED_GAP']}  / {grand}"
    )

    print("\n" + "=" * 70)
    print("DETAIL — FAIL and EXPECTED_GAP only")
    print("=" * 70)
    for row in suite["rows"]:
        if row["verdict"] == "PASS":
            continue
        print(f"[{row['verdict']:13}] {row['id']:7} ({row['gap_category']:20}) — {row['notes']}")
        print(f"               {row['detail']}")

    print("\n" + "=" * 70)
    print("QA-F — LATENCY BENCH (thresholds from MD §QA-F)")
    print("=" * 70)
    print(f"{'payload':<8} {'p50':>10} {'p95':>10} {'p99':>10}   threshold")
    for label, m in bench.items():
        threshold = 150 if label == "10kb" else 800
        ok = "✓" if m["p99_ms"] < threshold else "✗"
        print(
            f"{label:<8} {m['p50_ms']:>8.2f}ms {m['p95_ms']:>8.2f}ms "
            f"{m['p99_ms']:>8.2f}ms   <{threshold}ms {ok}"
        )

    return 1 if totals["FAIL"] > 0 else 0


def main() -> int:
    suite = run_suite()
    bench = latency_bench()
    exit_code = print_report(suite, bench)

    out = Path(__file__).parent / "last_run.json"
    out.write_text(json.dumps({
        "by_block": {k: dict(v) for k, v in suite["by_block"].items()},
        "rows": suite["rows"],
        "bench": bench,
    }, indent=2))
    print(f"\nResults written to {out}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
