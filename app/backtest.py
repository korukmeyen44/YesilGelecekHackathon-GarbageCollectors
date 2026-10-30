"""Rolling-origin evaluation on synthetic history only. python -m app.backtest"""
import argparse
import json
from pathlib import Path
import statistics
import sys

from app.domain import forecast
from app.storage import Operations


def evaluate(ops):
    now=ops.get("demo_now")
    errors, baseline_errors, eta_errors = [], [], []
    tp=fp=fn=0
    skipped_resets=0
    for b in ops.demo_bins():
        rows=ops.history(b["id"])
        stamps={round(t):f for t,f in rows}
        for t,current in rows:
            if not now-3*86400 <= t <= now-4*3600 or round((now-t)/900)%4:
                continue
            past=[r for r in rows if t-6*3600 <= r[0] <= t]
            future=[r for r in rows if t < r[0] <= t+4*3600]
            if not future:continue
            boundary=ops.db.execute("SELECT MAX(ts) FROM events WHERE bin_id=? AND kind='collection' AND ts<=?",(b["id"],t)).fetchone()[0]
            f=forecast(past,t,80,boundary)
            if not f["available"]:continue
            next_hour=stamps.get(round(t+3600))
            first_hour=[current]+[v for stamp,v in future if stamp<=t+3600]
            reset=any(y<x-20 for x,y in zip(first_hour,first_hour[1:]))
            if next_hour is not None and not reset:
                prediction=min(100,current+f["rate_pph"])
                errors.append(abs(prediction-next_hour))
                baseline_errors.append(abs(current-next_hour))
            elif reset:skipped_resets+=1
            if current<80:
                crossing=next((stamp for stamp,v in future if v>=80),None)
                alert=f["hours_to_threshold"]<=4
                actual=crossing is not None
                tp+=int(alert and actual);fp+=int(alert and not actual);fn+=int(not alert and actual)
                if actual:eta_errors.append(abs(f["hours_to_threshold"]-(crossing-t)/3600))
    return {"scope":"Yalnız 14 günlük sentetik geçmişin son 3 gününde saatlik rolling-origin test. Gerçek saha doğruluğu değildir.",
            "method":"Her tahminde yalnız o ana kadarki son 6 saat ve geçmişte bilinen son boşaltma kullanılır.",
            "evaluated_one_hour_forecasts":len(errors),
            "one_hour_fill_mae_percentage_points":round(statistics.mean(errors),3) if errors else None,
            "persistence_baseline_mae_percentage_points":round(statistics.mean(baseline_errors),3) if baseline_errors else None,
            "threshold_eta_mae_hours_on_observed_crossings":round(statistics.mean(eta_errors),3) if eta_errors else None,
            "four_hour_alert_true_positive":tp,"four_hour_alert_false_positive":fp,"four_hour_alert_missed":fn,
            "excluded_one_hour_emptying_intervals":skipped_resets,
            "limitation":"Üretim süreci ile model benzer doğrusal eğilimler içerir; sentetik sonuçlar iyimser olabilir. Eşik zamanı 15 dakikalık örnekleme çözünürlüğündedir."}


if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,default=Path(__file__).parent/".data")
    args=parser.parse_args()
    args.data_dir.mkdir(parents=True,exist_ok=True)
    ops=Operations(args.data_dir/"operations.sqlite3")
    try:print(json.dumps(evaluate(ops),ensure_ascii=False,indent=2))
    finally:ops.close()
