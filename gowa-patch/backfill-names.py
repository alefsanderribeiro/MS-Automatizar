#!/usr/bin/env python3
"""
Corrige nomes de grupo/canal gravados como placeholder ("Group <id>" /
"Newsletter <id>") no chatstorage.db do GOWA.

Self-contained: fala direto com a API do Docker pelo socket unix, então não
precisa da CLI do docker nem de venv. Roda um container node:24-alpine
descartável com o volume de dados montado.

  python3 backfill-names.py            # dry-run (volume em somente leitura)
  python3 backfill-names.py --apply    # grava (pare o container do GOWA antes)

O mapa de nomes vem de group-names.json no mesmo diretório; regenere com
fetch-group-names.py.
"""
import json
import os
import socket
import struct
import sys
import time

SOCK = "/run/docker.sock"
HERE = os.path.dirname(os.path.abspath(__file__))

# Os binds são resolvidos pelo daemon no host. Dentro do container do gateway o
# workspace aparece como /home/node; no host é /home/alefsander.
HOST_PREFIX = os.environ.get("GOWA_HOST_PREFIX", "/home/alefsander")
if HERE.startswith("/home/node"):
    HERE_HOST = HERE.replace("/home/node", HOST_PREFIX, 1)
else:
    HERE_HOST = HERE

MAP_FILE = os.path.join(HERE, "group-names.json")
VOLUME = os.environ.get("GOWA_VOLUME", "ms-automatizar-whatsapp-data")
APPLY = "--apply" in sys.argv
NAME = "gowa-backfill"


def req(method, path, body=None):
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(180)
    try:
        s.connect(SOCK)
    except PermissionError:
        sys.exit(f"sem permissão em {SOCK} — rode com sudo: sudo python3 {os.path.basename(__file__)}")
    headers = {"Host": "localhost", "Connection": "close"}
    payload = b""
    if body is not None:
        payload = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(payload))
    head = f"{method} {path} HTTP/1.1\r\n" + "".join(
        f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
    s.sendall(head.encode() + payload)
    buf = b""
    while True:
        try:
            b = s.recv(65536)
        except socket.timeout:
            break
        if not b:
            break
        buf += b
    s.close()
    sep = buf.find(b"\r\n\r\n")
    hdr, raw = buf[:sep], buf[sep + 4:]
    status = int(hdr.split()[1]) if hdr.split()[1:2] else 0
    if b"Transfer-Encoding: chunked" in hdr:
        out, i = b"", 0
        while True:
            j = raw.find(b"\r\n", i)
            if j < 0:
                break
            try:
                n = int(raw[i:j].split(b";")[0], 16)
            except ValueError:
                break
            if n == 0:
                break
            out += raw[j + 2:j + 2 + n]
            i = j + 2 + n + 2
        raw = out
    return status, raw


def jreq(method, path, body=None):
    st, raw = req(method, path, body)
    try:
        return st, json.loads(raw)
    except Exception:
        return st, raw.decode(errors="replace")


def demux(raw):
    out, i = b"", 0
    while i + 8 <= len(raw):
        if raw[i] in (0, 1, 2):
            n = struct.unpack(">I", raw[i + 4:i + 8])[0]
            out += raw[i + 8:i + 8 + n]
            i += 8 + n
        else:
            out += raw[i:]
            break
    return out.decode(errors="replace")


if not os.path.exists(MAP_FILE):
    sys.exit(f"faltando {MAP_FILE} — rode fetch-group-names.py primeiro")

st, _ = jreq("GET", f"/containers/{NAME}/json")
if st == 200:
    jreq("DELETE", f"/containers/{NAME}?force=true")
    time.sleep(1)

NODE_SRC = r"""
const { DatabaseSync } = require('node:sqlite');
const fs = require('fs');
const apply = process.argv[1] === 'apply';
const map = JSON.parse(fs.readFileSync('/work/group-names.json', 'utf8'));
const db = new DatabaseSync('/data/chatstorage.db');

const jidOf = {};
for (const d of db.prepare('SELECT device_id, jid FROM devices').all()) {
  jidOf[d.device_id] = d.jid;
}
const devIdOf = {};
for (const [devId, jid] of Object.entries(jidOf)) devIdOf[jid] = devId;

let planned = 0, changed = 0, skipped = 0, missing = 0;
const samples = [];
const rows = db.prepare("SELECT device_id, jid, name FROM chats WHERE jid LIKE '%@g.us' OR jid LIKE '%@newsletter'").all();
const upd = db.prepare('UPDATE chats SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE device_id = ? AND jid = ? AND name = ?');

db.exec('BEGIN IMMEDIATE');
for (const r of rows) {
  const devId = devIdOf[r.device_id];
  const names = (devId && map[devId]) || {};
  const want = names[r.jid];
  if (!want) { missing++; continue; }
  const user = r.jid.split('@')[0];
  const prefix = r.jid.endsWith('@g.us') ? 'Group ' : 'Newsletter ';
  if (r.name !== prefix + user) { skipped++; continue; }
  if (want === r.name) { skipped++; continue; }
  planned++;
  if (samples.length < 8) samples.push(`${devId} | ${r.jid} -> ${want}`);
  if (apply) changed += upd.run(want, r.device_id, r.jid, r.name).changes;
}
if (apply) db.exec('COMMIT'); else db.exec('ROLLBACK');

console.log('mode:', apply ? 'APPLY' : 'DRY-RUN');
console.log('rows_scanned:', rows.length);
console.log('would_update:', planned);
console.log('updated:', changed);
console.log('already_named:', skipped);
console.log('no_name_in_map:', missing);
for (const s of samples) console.log('  ' + s);
"""

body = {
    "Image": "node:24-alpine",
    "Cmd": ["node", "-e", NODE_SRC, "apply" if APPLY else "dry"],
    "HostConfig": {
        "Binds": [
            f"{VOLUME}:/data" + ("" if APPLY else ":ro"),
            f"{HERE_HOST}:/work:ro",
        ],
        "NetworkMode": "none",
    },
}
st, c = jreq("POST", "/containers/create?name=" + NAME, body)
if st != 201:
    sys.exit(f"create falhou ({st}): {c}")
cid = c["Id"]
jreq("POST", f"/containers/{cid}/start")
req("POST", f"/containers/{cid}/wait")
st, raw = req("GET", f"/containers/{cid}/logs?stdout=1&stderr=1")
print(demux(raw)[:4000])
jreq("DELETE", f"/containers/{cid}?force=true")
