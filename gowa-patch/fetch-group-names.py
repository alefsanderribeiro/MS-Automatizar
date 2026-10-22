#!/usr/bin/env python3
"""
Puxa os nomes reais de grupos e canais do GOWA rodando e grava group-names.json
no mesmo diretório, no formato { deviceId: { jid: nome } }.

Lê WHATSAPP_BASIC_AUTH de ~/ms_automatizar/.env. Só usa stdlib.
"""
import base64
import json
import os
import ssl
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.environ.get("GOWA_ENV", os.path.join(HERE, "..", ".env"))
BASE = os.environ.get("GOWA_BASE_URL", "https://gowa.alefsander.dev")
OUT = os.path.join(HERE, "group-names.json")

auth = None
if os.path.exists(ENV_FILE):
    for line in open(ENV_FILE, encoding="utf-8"):
        line = line.strip()
        if line.startswith("WHATSAPP_BASIC_AUTH="):
            auth = line.split("=", 1)[1].strip()
auth = os.environ.get("WHATSAPP_BASIC_AUTH") or auth
if not auth:
    sys.exit(f"WHATSAPP_BASIC_AUTH não encontrado em {ENV_FILE}")

token = base64.b64encode(auth.encode()).decode()
ctx = ssl.create_default_context()


def api(path, device):
    req = urllib.request.Request(BASE + path, headers={
        "Authorization": "Basic " + token,
        "X-Device-Id": device,
    })
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read().decode())


devices = [d.get("id") for d in
           (api("/devices", "").get("results") or []) if d.get("id")]
if not devices:
    sys.exit("nenhum device retornado por /devices")

out = {}
for dev in devices:
    devmap = {}
    for path in ("/user/my/groups", "/user/my/newsletters"):
        try:
            data = api(path, dev).get("results", {}).get("data") or []
        except Exception as e:
            print(f"{dev} {path}: erro {e}")
            continue
        for item in data:
            jid = item.get("JID") or item.get("id")
            name = (item.get("Name") or item.get("name") or "").strip()
            if jid and name:
                devmap[jid] = name
    out[dev] = devmap
    print(f"{dev}: {len(devmap)} nomes")

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("gravado", OUT, os.path.getsize(OUT), "bytes")
