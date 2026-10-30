"""Synthetic smoke demo; never evidence of physical sensor accuracy."""
import argparse
import json
import os
import time
from urllib.request import Request, urlopen


def measurement(distance, status="ok"):
    partial = status == "degraded"
    valid_pairs = 8 if partial else (10 if status == "ok" else 0)
    return {"distance_mm": distance, "spread_mm": 4 if valid_pairs else None,
            "attempted_pairs": 10, "valid_pairs": valid_pairs,
            "valid_samples": [valid_pairs, 10] if partial else [valid_pairs, valid_pairs],
            "status": status, "error_masks": [1, 0] if partial else ([0, 0] if valid_pairs else [1, 1]),
            "window_duration_ms": 10000}


def scenario(boot_id):
    values = [(400, "ok"), (220, "ok"), (220, "ok"), (220, "ok"),
              (220, "degraded"), (None, "too_few"), (None, "unstable"),
              (40, "ok"), (40, "ok"), (40, "ok"),
              (400, "ok"), (400, "ok"), (400, "ok")]
    for sequence, (distance, status) in enumerate(values, 1):
        summary = measurement(distance, status)
        if status == "unstable":
            summary.update(spread_mm=200, valid_pairs=10, valid_samples=[10, 10], error_masks=[0, 0])
        yield {"version": 2, "source": "simulator", "node_id": 1, "boot_id": boot_id,
               "sequence": sequence, "measured_uptime_ms": sequence * 10000,
               "gateway_id": 1, "gateway_boot_id": boot_id,
               "received_gateway_ms": sequence * 10000, "age_ms": 0,
               "measurement": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080/api/telemetry")
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--jsonl", action="store_true", help="Print records; do not POST")
    args = parser.parse_args()
    # Persistently increasing wall-time seconds helps repeat runs preserve boot ordering.
    boot = int(time.time()) & 0xFFFFFFFF or 1
    headers = {"Content-Type": "application/json"}
    if os.environ.get("GC_API_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GC_API_TOKEN"]
    for payload in scenario(boot):
        data = json.dumps(payload)
        if args.jsonl:
            print(data)
        else:
            request = Request(args.url, data=data.encode(), headers=headers, method="POST")
            with urlopen(request, timeout=3) as response:
                print(response.read().decode())
            time.sleep(max(0, args.interval))


if __name__ == "__main__":
    main()

