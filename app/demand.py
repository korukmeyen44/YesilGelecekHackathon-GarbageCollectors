"""Historical capacity pressure, independent of current fill and forecast parameters."""
import math
import statistics

WINDOW_DAYS = 14
REFERENCE_PPH = 8  # Fixed presentation scale; 8 percentage points/hour is red.


def historical_demand(samples, now, collections=()):
    """Net growth over continuous observed filling segments, not sum of noisy upticks.

    Input is quality-filtered (timestamp, fill-or-None). Fifteen-minute buckets
    prevent a high packet frequency from increasing the demand score.
    """
    start = now - WINDOW_DAYS * 86400
    buckets = {}
    for stamp, fill in samples:
        if not math.isfinite(stamp) or not start <= stamp <= now:
            continue
        bucket = buckets.setdefault(int(stamp // 900), [])
        if type(fill) in (int, float) and math.isfinite(fill) and 0 <= fill <= 100:
            bucket.append((stamp, fill))
    rows = [(statistics.median(t for t, _ in values), statistics.median(f for _, f in values))
            if values else (key * 900, None) for key, values in sorted(buckets.items())]
    boundaries = sorted(t for t in collections if start <= t <= now)
    hours = gain = saturated_hours = 0.0
    accepted = []
    segment = []

    def flush():
        nonlocal hours, gain, saturated_hours
        if len(segment) < 4 or segment[-1][0] - segment[0][0] < 2700:
            return
        duration = (segment[-1][0] - segment[0][0]) / 3600
        hours += duration
        gain += max(0, segment[-1][1] - segment[0][1])
        saturated_hours += sum((b[0] - a[0]) / 3600 for a, b in zip(segment, segment[1:])
                               if a[1] >= 95 and b[1] >= 95)
        accepted.extend(segment)

    boundary_index = 0
    for row in rows:
        if row[1] is None:
            flush()
            segment = []
            continue
        if segment:
            previous = segment[-1]
            while boundary_index < len(boundaries) and boundaries[boundary_index] <= previous[0]:
                boundary_index += 1
            crossed = boundary_index < len(boundaries) and boundaries[boundary_index] <= row[0]
            if row[0] - previous[0] > 1800 or row[1] < previous[1] - 20 or crossed:
                flush()
                segment = []
        segment.append(row)
    flush()
    span = 0 if not accepted else (accepted[-1][0] - accepted[0][0]) / 3600
    coverage = hours / span if span else 0
    reason = None
    if span < 24 or hours < 12 or coverage < .4:
        reason = "En az 24 saate yayılan 12 saat güvenilir gözlem ve %40 zaman kapsamı gerekli."
    elif now - accepted[-1][0] > 48 * 3600:
        reason = "Son güvenilir tarihsel ölçüm 48 saatten eski."
    rate = gain / hours if hours and reason is None else None
    return {
        "available": reason is None, "window_days": WINDOW_DAYS,
        "window_start": start, "window_end": now,
        "observed_hours": round(hours, 1), "coverage_percent": round(coverage * 100, 1),
        "last_observed_at": accepted[-1][0] if accepted else None,
        "rate_pph": None if rate is None else round(rate, 3),
        "pressure": None if rate is None else round(min(1, rate / REFERENCE_PPH), 4),
        "saturated_hours": round(saturated_hours, 1),
        "reason": reason or "Boşaltmalar ve kesintiler ayrılarak geçmiş dolum dönemlerinin net artışı / gözlenen süre.",
    }
