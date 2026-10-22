#!/usr/bin/env python3
"""
Manutenção do chatstorage.db do GOWA.

  python3 cleanup.py                     # relatório (somente leitura)
  python3 cleanup.py --apply             # backup + remove linhas de device órfão + VACUUM
  python3 cleanup.py --prune-media-days N --apply
                                         # além disso, apaga mídia mais antiga que N dias

Sempre faz backup antes de escrever e valida com integrity_check no fim.

ATENÇÃO ao mapeamento de colunas:
  devices.device_id        -> nome lógico ("WhatsApp-MS")
  chats/messages.device_id -> JID          ("556992518455@s.whatsapp.net")
Por isso o conjunto de devices vivos usa devices.jid, não devices.device_id.

Sobre mídia: os arquivos <epoch>-<uuid>.<ext> na raiz de storages/ NÃO são
registrados no chatstorage.db (a coluna `filename` guarda o nome original do
arquivo enviado). Não há como saber pelo banco quais ainda são usados, então a
remoção de mídia é por idade e só com --prune-media-days explícito.
"""
import json
import os
import socket
import struct
import sys
import time

SOCK = "/run/docker.sock"
VOLUME = "ms-automatizar-whatsapp-data"
# Caminho do HOST (o daemon Docker resolve binds no host, não no container
# do gateway). /home/node no gateway corresponde a /home/alefsander no host.
BACKUP_DIR = "/home/alefsander/gowa-backups"
CNAME = "gowa-cleanup"
APPLY = "--apply" in sys.argv

PRUNE_DAYS = None
if "--prune-media-days" in sys.argv:
    i = sys.argv.index("--prune-media-days")
    try:
        PRUNE_DAYS = int(sys.argv[i + 1])
    except (IndexError, ValueError):
        sys.exit("--prune-media-days exige um número de dias")

NODE_SRC = r"""
const { DatabaseSync } = require('node:sqlite');
const fs = require('fs');
const path = require('path');

const apply = process.argv[1] === 'apply';
const pruneDays = process.argv[2] === 'none' ? null : parseInt(process.argv[2], 10);
const db = new DatabaseSync('/data/chatstorage.db');

// devices vivos: comparar por JID, que é o que chats/messages guardam
const live = db.prepare('SELECT device_id, jid FROM devices').all();
const liveJids = new Set(live.map(r => r.jid));
console.log('devices ativos:');
for (const r of live) console.log('  ' + r.device_id + ' -> ' + r.jid);

const seenJids = db.prepare('SELECT DISTINCT device_id FROM chats').all().map(r => r.device_id);
const orphanJids = seenJids.filter(j => !liveJids.has(j));
console.log('device_ids em chats:', JSON.stringify(seenJids));
console.log('órfãos (sem device correspondente):', JSON.stringify(orphanJids));

const one = (sql, ...p) => db.prepare(sql).get(...p).c;
const report = [];
for (const d of orphanJids) {
  report.push({
    device: d,
    chats:     one('SELECT COUNT(*) c FROM chats WHERE device_id = ?', d),
    messages:  one('SELECT COUNT(*) c FROM messages WHERE device_id = ?', d),
    reactions: one('SELECT COUNT(*) c FROM message_reactions WHERE device_id = ?', d),
    edits:     one('SELECT COUNT(*) c FROM message_edits WHERE device_id = ?', d),
    polls:     one('SELECT COUNT(*) c FROM poll_definitions WHERE device_id = ?', d),
    scheduled: one('SELECT COUNT(*) c FROM scheduled_sends WHERE device_id = ?', d),
    maxMsg:    db.prepare('SELECT MAX(timestamp) m FROM messages WHERE device_id = ?').get(d).m,
  });
}
console.log('=== linhas por device órfão ===');
for (const r of report) console.log('  ' + JSON.stringify(r));

// ---------- mídia: buckets por idade ----------
const now = Date.now() / 1000;
const re = /^(\d{10})-[0-9a-f-]{36}\.[a-z0-9]+$/i;
const buckets = { '0-7d': [0, 0], '7-30d': [0, 0], '30-90d': [0, 0], '90-180d': [0, 0], '180d+': [0, 0] };
let total = 0, totalBytes = 0;
const pruneList = [];
for (const f of fs.readdirSync('/data')) {
  const full = path.join('/data', f);
  let st;
  try { st = fs.statSync(full); } catch (e) { continue; }
  if (!st.isFile()) continue;
  const m = f.match(re);
  if (!m) continue;
  total++; totalBytes += st.size;
  const ageDays = (now - parseInt(m[1], 10)) / 86400;
  const key = ageDays < 7 ? '0-7d' : ageDays < 30 ? '7-30d' : ageDays < 90 ? '30-90d'
            : ageDays < 180 ? '90-180d' : '180d+';
  buckets[key][0]++; buckets[key][1] += st.size;
  if (pruneDays !== null && ageDays > pruneDays) pruneList.push([f, st.size]);
}
console.log('=== mídia no volume (por idade) ===');
console.log('  total: ' + total + ' arquivos, ' + (totalBytes / 1048576).toFixed(1) + ' MB');
for (const [k, v] of Object.entries(buckets)) {
  if (v[0]) console.log('  ' + k + ': ' + v[0] + ' arquivos, ' + (v[1] / 1048576).toFixed(1) + ' MB');
}
if (pruneDays !== null) {
  const b = pruneList.reduce((a, [, s]) => a + s, 0);
  console.log('  a apagar (>' + pruneDays + 'd): ' + pruneList.length + ' arquivos, ' + (b / 1048576).toFixed(1) + ' MB');
}

if (!apply) {
  console.log('MODO: DRY-RUN (nada foi alterado)');
  process.exit(0);
}
if (orphanJids.length === 0 && pruneList.length === 0) {
  console.log('nada a fazer');
  process.exit(0);
}

// ---------- backup ----------
if (!fs.existsSync('/backup')) fs.mkdirSync('/backup', { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const backup = '/backup/chatstorage-pre-cleanup-' + stamp + '.db';
db.exec("VACUUM INTO '" + backup + "'");
console.log('backup: ' + backup + ' (' + fs.statSync(backup).size + ' bytes)');

// ---------- remoção de órfãos ----------
if (orphanJids.length) {
  db.exec('BEGIN IMMEDIATE');
  for (const d of orphanJids) {
    const r = {
      messages:  db.prepare('DELETE FROM messages WHERE device_id = ?').run(d).changes,
      reactions: db.prepare('DELETE FROM message_reactions WHERE device_id = ?').run(d).changes,
      edits:     db.prepare('DELETE FROM message_edits WHERE device_id = ?').run(d).changes,
      polls:     db.prepare('DELETE FROM poll_definitions WHERE device_id = ?').run(d).changes,
      scheduled: db.prepare('DELETE FROM scheduled_sends WHERE device_id = ?').run(d).changes,
      chats:     db.prepare('DELETE FROM chats WHERE device_id = ?').run(d).changes,
    };
    console.log('removido ' + d + ': ' + JSON.stringify(r));
  }
  db.exec('COMMIT');
  db.exec('VACUUM');
}

// ---------- remoção de mídia por idade ----------
if (pruneList.length) {
  let n = 0, b = 0;
  for (const [f, s] of pruneList) {
    try { fs.unlinkSync(path.join('/data', f)); n++; b += s; } catch (e) {}
  }
  console.log('mídia removida: ' + n + ' arquivos, ' + (b / 1048576).toFixed(1) + ' MB');
}

console.log('integrity_check :', db.prepare('PRAGMA integrity_check').get().integrity_check);
console.log('chats restantes :', db.prepare('SELECT COUNT(*) c FROM chats').get().c);
console.log('msgs restantes  :', db.prepare('SELECT COUNT(*) c FROM messages').get().c);
for (const r of live) {
  const c = db.prepare('SELECT COUNT(*) c FROM chats WHERE device_id = ?').get(r.jid).c;
  const m = db.prepare('SELECT COUNT(*) c FROM messages WHERE device_id = ?').get(r.jid).c;
  console.log('  ' + r.device_id + ': ' + c + ' chats, ' + m + ' mensagens');
}
console.log('db bytes        :', fs.statSync('/data/chatstorage.db').size);
"""


def req(method, path, body=None):
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(1800)
    try:
        s.connect(SOCK)
    except PermissionError:
        sys.exit("sem permissão no socket docker — rode com sudo")
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
            b = s.recv(1 << 16)
        except socket.timeout:
            break
        if not b:
            break
        buf += b
    s.close()
    sep = buf.find(b"\r\n\r\n")
    hdr, raw = buf[:sep], buf[sep + 4:]
    parts = hdr.split()
    status = int(parts[1]) if len(parts) > 1 else 0
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


st, _ = jreq("GET", f"/containers/{CNAME}/json")
if st == 200:
    jreq("DELETE", f"/containers/{CNAME}?force=true")
    time.sleep(1)

binds = [f"{VOLUME}:/data" + ("" if APPLY else ":ro")]
if APPLY:
    binds.append(f"{BACKUP_DIR}:/backup")

body = {
    "Image": "node:24-alpine",
    "Cmd": ["node", "-e", NODE_SRC,
            "apply" if APPLY else "dry",
            "none" if PRUNE_DAYS is None else str(PRUNE_DAYS)],
    "HostConfig": {"Binds": binds, "NetworkMode": "none"},
}
st, c = jreq("POST", "/containers/create?name=" + CNAME, body)
if st != 201:
    sys.exit(f"create falhou ({st}): {c}")
cid = c["Id"]
jreq("POST", f"/containers/{cid}/start")
req("POST", f"/containers/{cid}/wait")
st, raw = req("GET", f"/containers/{cid}/logs?stdout=1&stderr=1")
print(demux(raw)[:10000])
jreq("DELETE", f"/containers/{cid}?force=true")
