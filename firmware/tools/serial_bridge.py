"""Forward ESP32 USB JSON lines to the local receiver (optional pyserial)."""
import argparse
import json
import os
import queue
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from collector import MAX_BODY, ValidationError, loads, validate_payload


class LineFramer:
    """Drop an entire oversized line, including fragments across serial timeouts."""
    def __init__(self):
        self.buffer = bytearray()
        self.discarding = False
        self.dropped = 0

    def feed(self, chunk):
        lines = []
        for byte in chunk:
            if byte == 10:
                if not self.discarding:
                    lines.append(bytes(self.buffer))
                else:
                    self.dropped += 1
                self.buffer.clear()
                self.discarding = False
            elif not self.discarding:
                self.buffer.append(byte)
                if len(self.buffer) > MAX_BODY:
                    self.discarding = True
                    self.buffer.clear()
        return lines


def serial_reader(port, pending, stop):
    framer = LineFramer()
    try:
        while not stop.is_set():
            chunk = port.read(min(max(port.in_waiting, 1), 1024))
            for line in framer.feed(chunk):
                if not line.strip() or line.startswith(b"#"):
                    continue
                try:
                    payload = validate_payload(loads(line))
                except ValidationError as exc:
                    print(f"Rejected serial line: {exc}", file=sys.stderr)
                    continue
                item = (payload, time.monotonic())
                try:
                    pending.put_nowait(item)
                except queue.Full:
                    try:
                        pending.get_nowait()
                        print("Bridge queue full: dropped oldest measurement", file=sys.stderr)
                    except queue.Empty:
                        pass
                    pending.put_nowait(item)
    except OSError as exc:
        print(f"USB reader stopped: {exc}", file=sys.stderr)
        stop.set()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="For example COM5")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--url", default="http://127.0.0.1:8080/api/telemetry")
    args = parser.parse_args()
    try:
        import serial
    except ImportError:
        parser.error("Install pyserial: python -m pip install pyserial==3.5")
    token = os.environ.get("GC_API_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    print("USB bridge active; close other serial monitors. Opening port may reset ESP32.", file=sys.stderr)
    stop = threading.Event()
    pending = queue.Queue(maxsize=24)
    reader = None
    try:
        with serial.Serial(args.port, args.baud, timeout=1) as port:
            reader = threading.Thread(target=serial_reader, args=(port, pending, stop), daemon=True)
            reader.start()
            while not stop.is_set():
                try:
                    payload, started = pending.get(timeout=0.2)
                except queue.Empty:
                    continue
                initial_age = payload["age_ms"]
                for attempt in range(3):
                    payload["age_ms"] = initial_age + round((time.monotonic() - started) * 1000)
                    if payload["age_ms"] > 30000:
                        print("Dropped expired bridge measurement", file=sys.stderr)
                        break
                    request = Request(args.url, data=json.dumps(payload).encode(), headers=headers, method="POST")
                    try:
                        with urlopen(request, timeout=2) as response:
                            print(response.read().decode())
                        break
                    except HTTPError as exc:
                        print(f"HTTP {exc.code}", file=sys.stderr)
                        if 400 <= exc.code < 500 and exc.code not in (408, 429):
                            break
                    except (URLError, TimeoutError, OSError) as exc:
                        print(f"Delivery failed: {exc}", file=sys.stderr)
                    if attempt < 2:
                        time.sleep(0.5 * (attempt + 1))
                else:
                    print("Dropped measurement after three attempts", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if reader:
            reader.join(timeout=2)


if __name__ == "__main__":
    main()

