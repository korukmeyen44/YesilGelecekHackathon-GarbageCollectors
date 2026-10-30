"""Synthetic smoke demo; never evidence of physical sensor accuracy."""
import argparse
import json
import os
import time
from urllib.request import Request, urlopen


def sensor(distance, status="ok"):
    return {"distance_mm": distance, "spread_mm": 4 if status == "ok" else None,
            "valid_samples": 5 if status == "ok" else 0, "status": status,
            "error_mask": 0 if status == "ok" else 1}


def scenario(boot_id):
    # Repeat persistent level changes three times to exercise confirmation.
    distances = [(400, 400), (220, 220), (220, 220), (220, 220),
                 (None, 220), (None, None), (50, 390),
                 (40, 40), (40, 40), (40, 40),
                 (400, 400), (400, 400), (400, 400)]
    for sequence, pair in enumerate(distances, 1):
        yield {"version": 1, "source": "simulator", "node_id": 1, "boot_id": boot_id,
               "sequence": sequence, "measured_uptime_ms": sequence * 4000,
               "gateway_id": 1, "gateway_boot_id": boot_id,
               "received_gateway_ms": sequence * 4000, "age_ms": 0,
               "sensors": [sensor(d, "ok" if d is not None else "too_few") for d in pair]}


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

