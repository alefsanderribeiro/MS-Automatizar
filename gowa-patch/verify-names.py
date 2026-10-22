#!/usr/bin/env python3
"""
Verifica pela API do GOWA se os nomes de grupo/canal já não estão em placeholder.

  python3 verify-names.py            # mostra amostra por device
  python3 verify-names.py --all      # varre todas as páginas de /chats

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
ALL = "--all" in sys.argv

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


def api(path, device=""):
    req = urllib.request.Request(BASE + path, headers={
        "Authorization": "Basic " + token,
        "X-Device-Id": device,
    })
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read().decode())


devices = [d.get("id") for d in (api("/devices").get("results") or []) if d.get("id")]

for dev in devices:
    chats, offset = [], 0
    while True:
        page = api(f"/chats?limit=100&offset={offset}", dev).get("results", {}).get("data") or []
        chats += page
        offset += 100
        if not ALL or len(page) < 100:
            break
    groups = [c for c in chats if str(c.get("jid", "")).endswith(("@g.us", "@newsletter"))]
    placeholders = [c for c in groups
                    if str(c.get("name", "")).startswith(("Group ", "Newsletter "))
                    and str(c.get("name", "")).split(" ", 1)[1].isdigit() is False
                    and " " not in str(c.get("name", "")).split(" ", 1)[1]]
    print(f"== {dev}: {len(groups)} grupos/canais, {len(placeholders)} placeholders")
    for c in groups[:10]:
        print("   ", c.get("name"))
