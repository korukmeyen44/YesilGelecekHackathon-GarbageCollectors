"""Save physically measured references; never invent a calibrated fill percentage."""
import argparse
import copy
import json
from pathlib import Path
import uuid

from collector import load_calibration, ValidationError

ROOT = Path(__file__).resolve().parents[1]


def calibrated_config(config, node, empty_mm, full_mm):
    if type(node) is not int or str(node) not in config["nodes"]:
        raise ValueError("Kayıtlı bir kutu seçin: 1, 2 veya 3.")
    if type(empty_mm) is not int or type(full_mm) is not int or not 20 <= full_mm < empty_mm <= 4000:
        raise ValueError("Ölçüler mm cinsinden tam sayı olmalı: 20 <= dolu < boş <= 4000.")
    result = copy.deepcopy(config)
    result["nodes"][str(node)]["measurement"].update(empty_mm=empty_mm,full_mm=full_mm)
    result["nodes"][str(node)]["calibrated"] = True
    result["calibration_id"] = "measured-mean-" + uuid.uuid4().hex[:12]
    result["purpose"] = "Physical references entered by the operator for the combined sensor mean"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", type=int, default=1)
    parser.add_argument("--empty-mm", type=int)
    parser.add_argument("--full-mm", type=int)
    args = parser.parse_args()
    target = ROOT / "config/calibration.local.json"
    try:
        empty = args.empty_mm if args.empty_mm is not None else int(input("Boş kutuda LCD ortalaması (mm): "))
        full = args.full_mm if args.full_mm is not None else int(input("Dolu kabul edilen seviyede LCD ortalaması (mm): "))
        config = load_calibration(target if target.exists() else ROOT/"config/calibration.example.json")
        config = calibrated_config(config,args.node,empty,full)
        temporary = target.with_suffix(target.suffix+".tmp")
        temporary.write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        load_calibration(temporary)
        if target.exists(): target.with_suffix(target.suffix+".bak").write_bytes(target.read_bytes())
        temporary.replace(target)
    except (OSError,ValueError,ValidationError) as error:
        parser.error(str(error))
    print("Fiziksel referanslar calibration.local.json dosyasına kaydedildi. Backend'i yeniden başlatın.")


if __name__ == "__main__":
    main()
