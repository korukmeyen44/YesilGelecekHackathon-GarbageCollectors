import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(REPO/"firmware/tools"))
from app.server import Application,make_server
from configure_gateway import validate,write_config


class GatewayConfigurationTests(unittest.TestCase):
    def test_private_settings_escape_strings_and_match_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_config('S24 "FE"',r'password\safe',"http://10.206.7.136:8080/api/telemetry","test-token-123456789",root=root)
            header=(root/"include/gateway_config.local.h").read_text(encoding="utf-8")
            self.assertIn(r'S24 \"FE\"',header)
            network=json.loads((root/"config/network.local.json").read_text(encoding="utf-8"))
            self.assertEqual(network["api_token"],"test-token-123456789")
            self.assertNotIn("password",network)

    def test_invalid_and_placeholder_settings_fail_closed(self):
        url="http://10.206.7.136:8080/api/telemetry"
        for ssid,password,target,token in (("S24 FE","YOUR_WIFI_PASSWORD",url,"long-secret-token"),
            ("S24 FE","short",url,"long-secret-token"),("S24 FE","password123","http://localhost:8080/api/telemetry","long-secret-token"),
            ("S24 FE","password123",url,"short"),("S24 FE","password123","https://example.org/api/telemetry","long-secret-token")):
            with self.subTest(target=target),self.assertRaises(ValueError):validate(ssid,password,target,token)


@unittest.skipUnless(os.environ.get("GC_CPP_JSON_FIXTURE"),"Run firmware/tools/run_tests.py for compiled gateway fixture")
class CompiledGatewayApplicationTests(unittest.TestCase):
    def test_cpp_json_to_application_to_cpp_durable_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,REPO/"firmware/config/calibration.demo.json",roads_enabled=False)
            server=make_server(app,port=0,token="integration-secret")
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f"http://127.0.0.1:{server.server_port}"
            payload=Path(os.environ["GC_CPP_JSON_FIXTURE"]).read_bytes()
            headers={"Content-Type":"application/json","Authorization":"Bearer integration-secret"}
            try:
                for status in (201,200):
                    with urlopen(Request(base+"/api/telemetry",data=payload,headers=headers),timeout=5) as response:
                        self.assertEqual(response.status,status)
                        receipt=response.read()
                    path=Path(directory)/"receipt.json";path.write_bytes(receipt)
                    binary=REPO/"firmware/.build"/("test_delivery.exe" if os.name=="nt" else "test_delivery")
                    subprocess.run([str(binary),str(path),str(status)],check=True,capture_output=True)
                with urlopen(Request(base+"/api/dashboard",headers=headers),timeout=5) as response:
                    bins=json.load(response)["bins"]
                live=[b for b in bins if b["source"]=="live"]
                self.assertEqual(len(live),1)
                self.assertEqual(live[0]["fill_percent"],50)
                wrong=json.loads(payload);wrong["node_id"]=2
                with self.assertRaises(HTTPError) as e:urlopen(Request(base+"/api/telemetry",data=json.dumps(wrong).encode(),headers=headers),timeout=5)
                self.assertEqual(e.exception.code,400)
                request=Request(base+"/api/settings",data=b'{}',headers={**headers,"Origin":"https://unrelated.example"})
                with self.assertRaises(HTTPError) as e:urlopen(request,timeout=5)
                self.assertEqual(e.exception.code,403)
            finally:
                server.shutdown();server.server_close();thread.join();app.close()
