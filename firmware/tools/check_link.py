"""Observe real node 1 through the backend; never inject synthetic telemetry."""
import argparse
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]


def usable_node(node, require_fill=False):
    m = node.get("measurement") or {}
    return (node.get("source") == "rf" and node.get("freshness") == "fresh" and
            type(m.get("distance_mm")) is int and m.get("attempted_pairs") == 5 and m.get("status") in ("ok","degraded") and
            (not require_fill or node.get("fill_percent") is not None and
             node.get("measurement_quality") in ("ok","degraded")))


def main():
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples",type=int,default=3)
    parser.add_argument("--timeout",type=float,default=60)
    parser.add_argument("--require-fill",action="store_true",help="Kalibrasyon sonrası geçerli doluluk da gerekli olsun.")
    args=parser.parse_args()
    if not 1<=args.samples<=100 or not 1<=args.timeout<=3600:parser.error("Geçerli örnek sayısı 1–100; süre 1–3600 saniye.")
    try:network=json.loads((ROOT/"config/network.local.json").read_text(encoding="utf-8"))
    except (OSError,ValueError):parser.error("Önce configure_gateway.py ile yerel ayarları hazırlayın.")
    url=network["api_url"].removesuffix("/api/telemetry")+"/api/latest"
    deadline=time.monotonic()+args.timeout
    identities=set();last_state=None
    while time.monotonic()<deadline:
        try:
            request=Request(url,headers={"Authorization":"Bearer "+network["api_token"]})
            with urlopen(request,timeout=min(3,max(.1,deadline-time.monotonic()))) as response:data=json.load(response)
            node=next((n for n in data.get("nodes",[]) if n.get("node_id")==1 and n.get("source")=="rf"),None)
            if node:
                m=node.get("measurement") or {}
                state=(node["boot_id"],node["sequence"],node["freshness"],node["measurement_quality"])
                if state!=last_state:
                    distance = str(m['distance_mm'])+"mm" if m.get('distance_mm') is not None else "alınamadı"
                    print(f"K1 seq={node['sequence']} mesafe={distance} kalite={node['measurement_quality']} güncellik={node['freshness']} doluluk={node['fill_percent']}",flush=True)
                    last_state=state
                if usable_node(node,args.require_fill):
                    identities.add((node["boot_id"],node["sequence"]))
                    if len(identities)>=args.samples:
                        print(f"PASS: backend'de {len(identities)} farklı, güncel ve geçerli v3 RF ortalaması gözlendi. Sensörün fiziksel doğruluğu ayrıca kontrol edilmeli.")
                        if node["measurement_quality"]=="uncalibrated":print("Ham mesafe akıyor; doluluk için fiziksel kalibrasyon eksik.")
                        return
            elif last_state!="waiting":
                print("Backend erişilebilir; gerçek kutu 1 ölçümü bekleniyor.",flush=True);last_state="waiting"
        except HTTPError as error:
            parser.exit(1,f"HTTP {error.code}: backend adresi ve yerel erişim anahtarını kontrol edin.\n")
        except (URLError,OSError,ValueError):
            if last_state!="unreachable":
                print("Backend'e erişilemiyor; sunucu, IP, aynı Wi-Fi ve güvenlik duvarını kontrol edin.",flush=True)
                last_state="unreachable"
        time.sleep(min(2,max(0,deadline-time.monotonic())))
    parser.exit(1,"FAIL: süre içinde yeterli farklı güncel ölçüm alınamadı. Gateway seri logunda wifi/http/delivered alanlarını inceleyin.\n")


if __name__=="__main__":main()
