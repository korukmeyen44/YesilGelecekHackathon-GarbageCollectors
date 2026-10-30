"""Prepare ignored local Wi-Fi settings without putting secrets on the command line."""
import argparse
import getpass
import json
from pathlib import Path
import secrets
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def validate(ssid, password, url, token, ca=""):
    if ssid=="YOUR_2_4_GHZ_WIFI" or password=="YOUR_WIFI_PASSWORD":
        raise ValueError("Örnek Wi-Fi değerlerini gerçek bilgilerle değiştirin.")
    if not isinstance(ssid,str) or not 1 <= len(ssid.encode("utf-8")) <= 32 or any(ord(c)<32 for c in ssid):
        raise ValueError("Wi-Fi adı 1–32 UTF-8 bayt olmalı.")
    if not 8 <= len(password) <= 63 or any(not 32 <= ord(c) <= 126 for c in password):
        raise ValueError("WPA2/WPA3 şifresi 8–63 ASCII karakter olmalı; açık ağ kullanılmaz.")
    p=urlsplit(url)
    if p.scheme not in ("http","https") or not p.hostname or p.hostname in ("localhost","0.0.0.0") or p.hostname.startswith("127.") or p.path!="/api/telemetry" or p.query or p.fragment or p.username or p.password or len(url)>192 or any(c.isspace() for c in url):
        raise ValueError("Bilgisayarın LAN IP'siyle http(s)://IP:8080/api/telemetry gerekli.")
    if p.port is not None and not 1<=p.port<=65535:
        raise ValueError("Geçersiz port.")
    if p.scheme=="https" and "-----BEGIN CERTIFICATE-----" not in ca:
        raise ValueError("HTTPS için güvenilir PEM kök sertifika dosyası gerekli.")
    if not 16<=len(token)<=256 or any(not 33<=ord(c)<=126 for c in token):
        raise ValueError("API anahtarı 16–256 boşluksuz ASCII karakter olmalı.")


def write_config(ssid,password,url,token,ca="",root=ROOT):
    validate(ssid,password,url,token,ca)
    values={"GC_ENABLE_HTTP":1,"GC_GATEWAY_ID":1,"GC_ACTIVE_NODE_ID":1,"GC_ENABLE_LCD":1,"GC_LCD_ADDRESS":0x27,
            "GC_WIFI_SSID":ssid,"GC_WIFI_PASSWORD":password,"GC_API_URL":url,"GC_API_TOKEN":token,"GC_TLS_ROOT_CA":ca}
    header="#pragma once\n// PRIVATE local configuration; excluded from Git.\n"
    header+="\n".join(f"#define {k} {json.dumps(v,ensure_ascii=False)}" for k,v in values.items())+"\n"
    (root/"include").mkdir(parents=True,exist_ok=True)
    (root/"config").mkdir(parents=True,exist_ok=True)
    # Each replacement is atomic; on interruption rerun before building either component.
    for path,text in ((root/"include/gateway_config.local.h",header),
                      (root/"config/network.local.json",json.dumps({"ssid":ssid,"api_url":url,"api_token":token},ensure_ascii=False,indent=2)+"\n")):
        temporary=path.with_suffix(path.suffix+".tmp")
        temporary.write_text(text,encoding="utf-8")
        temporary.replace(path)


def main():
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssid")
    parser.add_argument("--backend-url")
    parser.add_argument("--ca-file",type=Path)
    parser.add_argument("--check",action="store_true",help="Validate private settings before an ESP32 upload.")
    args=parser.parse_args()
    if args.check:
        try:
            text=(ROOT/"include/gateway_config.local.h").read_text(encoding="utf-8")
            def value(name,default=None):
                match=re.search(r"^#define\s+"+name+r"\s+(\".*\")\s*$",text,re.MULTILINE)
                if match:return json.loads(match.group(1))
                if default is not None:return default
                raise ValueError("Eksik yerel ayar: "+name)
            ssid,password,url,token,ca=[value("GC_"+name, "" if name=="TLS_ROOT_CA" else None) for name in ("WIFI_SSID","WIFI_PASSWORD","API_URL","API_TOKEN","TLS_ROOT_CA")]
            validate(ssid,password,url,token,ca)
            network=json.loads((ROOT/"config/network.local.json").read_text(encoding="utf-8"))
            if network!={"ssid":ssid,"api_url":url,"api_token":token}:
                raise ValueError("Gateway ve backend ayarları farklı; configure_gateway.py ile yeniden hazırlayın.")
        except (OSError,ValueError) as e:parser.error(str(e))
        print("Wi-Fi/backend yerel ayarları doğrulandı; gizli bilgiler gösterilmedi.")
        return
    if not args.ssid or not args.backend_url:parser.error("--ssid ve --backend-url gerekli.")
    password=getpass.getpass("Wi-Fi şifresi (ekranda gösterilmez): ")
    token=getpass.getpass("Backend anahtarı (en az 16 karakter; boş bırakırsanız üretilir): ") or secrets.token_urlsafe(24)
    ca=args.ca_file.read_text(encoding="ascii") if args.ca_file else ""
    try:write_config(args.ssid,password,args.backend_url,token,ca)
    except ValueError as e:parser.error(str(e))
    print("Yerel ayarlar hazır. Şifre/anahtar yazdırılmadı. Backend'i start_backend.py ile başlatın.")
    print("Panel erişim anahtarı firmware/config/network.local.json dosyasındaki api_token alanındadır.")
    print("Şimdi gateway'i yeniden derleyip yükleyin. Yerel dosyaları Git'e eklemeyin.")


if __name__=="__main__":main()
