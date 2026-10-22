#!/usr/bin/env python3
"""Checagem rápida de saúde do GOWA: versão, UI, devices, nomes."""
import base64, hashlib, json, os, ssl, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(HERE, "..", ".env")
BASE = "https://gowa.alefsander.dev"

auth = None
if os.path.exists(ENV_FILE):
    for line in open(ENV_FILE, encoding="utf-8"):
        if line.strip().startswith("WHATSAPP_BASIC_AUTH="):
            auth = line.strip().split("=", 1)[1].strip()
if not auth:
    sys.exit("WHATSAPP_BASIC_AUTH não encontrado")

token = base64.b64encode(auth.encode()).decode()
ctx = ssl.create_default_context()


def get(path, device="", raw=False):
    req = urllib.request.Request(BASE + path, headers={
        "Authorization": "Basic " + token, "X-Device-Id": device})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        body = r.read()
        return body if raw else json.loads(body.decode())


info = get("/app/info")["results"]
print("versão backend :", info.get("version"))
print("base_path      :", info.get("base_path") or "/")
print("scheduled_sends:", info.get("scheduled_sends"))

ui = get("/", raw=True)
print("UI bytes       :", len(ui))
print("UI sha256      :", hashlib.sha256(ui).hexdigest())

for d in get("/devices")["results"]:
    print(f"device         : {d['id']} | {d.get('display_name','')} | {d.get('state')} | {d.get('jid','')}")

for dev in ["WhatsApp-MS", "WhatsApp-MD"]:
    chats = get("/chats?limit=100", dev).get("results", {}).get("data") or []
    groups = [c for c in chats if str(c.get("jid","")).endswith(("@g.us","@newsletter"))]
    ph = [c for c in groups if str(c.get("name","")).startswith(("Group ","Newsletter "))]
    print(f"chats {dev}: {len(groups)} grupos/canais, {len(ph)} placeholders")
