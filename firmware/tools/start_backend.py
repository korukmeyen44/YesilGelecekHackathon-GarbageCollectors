"""Start the backend with the gateway's matching API token. No credentials in argv."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit


def main():
    root=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=root/"firmware/config/calibration.local.json")
    args=parser.parse_args()
    network=root/"firmware/config/network.local.json"
    if not network.is_file():parser.error("Önce configure_gateway.py ile yerel ağ ayarlarını hazırlayın.")
    config=json.loads(network.read_text(encoding="utf-8"))
    url=urlsplit(config["api_url"])
    if url.scheme!="http":parser.error("HTTPS için sertifikalı ters proxy gerekir; bu başlatıcı doğrudan LAN HTTP içindir.")
    env={**os.environ,"GC_API_TOKEN":config["api_token"]}
    command=[sys.executable,"-m","app.server","--host","0.0.0.0","--port",str(url.port or 80)]
    if args.config.is_file():command += ["--config",str(args.config)]
    else:print("Kalibrasyon dosyası yok: ham mesafe alınır, doluluk kalibrasyona kadar belirsiz kalır.",flush=True)
    raise SystemExit(subprocess.call(command,cwd=root,env=env))


if __name__=="__main__":main()
