#!/usr/bin/env python3
"""Measure Decision Card API latency (plan budget: p95 < 500 ms metrics-only).

Writes docs/DECIDE_API_LATENCY.json
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.product.api_server import start_background  # noqa: E402
from wildfire_front.product.decide_service import decide_from_request  # noqa: E402

N = 40
P95_BUDGET_MS = 500.0


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=ROOT)
    base = f"http://127.0.0.1:{port}"
    try:
        # warm-up
        decide_from_request({"event_id": "warm", "use_ml_v34": True}, base=ROOT)
        _post(f"{base}/v1/decide", {"event_id": "warm", "use_ml_v34": True})

        direct_ms: list[float] = []
        http_ms: list[float] = []
        last_decision = None

        body = {
            "event_id": "latency_probe",
            "use_ml_v34": True,
            "open_pack": "outputs/open_if/emsr578",
            "require_ops_for_go": True,
            "channel": "latency_script",
        }
        # open pack may be missing in CI — still OK (HOLD/ABSTAIN)
        if not (ROOT / "outputs" / "open_if" / "emsr578" / "scorecard_pista_b.json").is_file():
            body.pop("open_pack", None)

        for _ in range(N):
            t0 = time.perf_counter()
            direct = decide_from_request(body, base=ROOT)
            direct_ms.append((time.perf_counter() - t0) * 1000.0)
            last_decision = direct.get("decision")

            t1 = time.perf_counter()
            http = _post(f"{base}/v1/decide", body)
            http_ms.append((time.perf_counter() - t1) * 1000.0)
            last_decision = http.get("decision")

        direct_ms.sort()
        http_ms.sort()
        report = {
            "schema": "decide_api_latency_v1",
            "measured_at_utc": datetime.now(UTC).isoformat(),
            "n": N,
            "scenario": "metrics_only_ml_v34_optional_open",
            "budget_p95_ms": P95_BUDGET_MS,
            "direct_service": {
                "p50_ms": round(_percentile(direct_ms, 50), 3),
                "p95_ms": round(_percentile(direct_ms, 95), 3),
                "max_ms": round(max(direct_ms), 3),
                "mean_ms": round(statistics.mean(direct_ms), 3),
            },
            "http_api": {
                "p50_ms": round(_percentile(http_ms, 50), 3),
                "p95_ms": round(_percentile(http_ms, 95), 3),
                "max_ms": round(max(http_ms), 3),
                "mean_ms": round(statistics.mean(http_ms), 3),
            },
            "last_decision": last_decision,
            "sla_pass": _percentile(http_ms, 95) < P95_BUDGET_MS,
            "dream_field_p95_s": 15.0,
            "note": (
                "Budget is for metrics-only Decision Card path (no GeoTIFF ingest). "
                "Field dream <15s inbox→card remains a separate measurement (incident SLA)."
            ),
            "port_used": port,
        }
        out = ROOT / "docs" / "DECIDE_API_LATENCY.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        print(f"wrote: {out}")
        return 0 if report["sla_pass"] else 1
    except urllib.error.URLError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        return 2
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
