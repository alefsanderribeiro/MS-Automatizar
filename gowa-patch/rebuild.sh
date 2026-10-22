#!/usr/bin/env bash
# Reconstrói gowa-patched:9.6.0-groupnames = v9.6.0 + patch de nomes de grupo.
# Usa a API do Docker via socket unix (não exige CLI do docker instalado).
set -euo pipefail

GOWA_VERSION="${GOWA_VERSION:-v9.6.0}"
IMAGE_TAG="${IMAGE_TAG:-gowa-patched:9.6.0-groupnames}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${BUILD_DIR:-/home/node/gowa-build}"
SOCK=/run/docker.sock

[ -S "$SOCK" ] || { echo "socket $SOCK não encontrado" >&2; exit 1; }

if [ ! -d "$BUILD_DIR/.git" ]; then
  git clone --depth 1 --branch "$GOWA_VERSION" \
    https://github.com/aldinokemal/go-whatsapp-web-multidevice.git "$BUILD_DIR"
fi

cd "$BUILD_DIR"
git fetch --depth 1 origin "refs/tags/$GOWA_VERSION:refs/tags/$GOWA_VERSION" 2>/dev/null || true
git checkout --force "$GOWA_VERSION"
git clean -fdx -q
git apply "$HERE/0001-group-chat-names.patch"

tar -czf /tmp/gowa-build-ctx.tgz src docker

python3 - "$IMAGE_TAG" <<'PY'
import sys, json, socket
tag = sys.argv[1]
data = open('/tmp/gowa-build-ctx.tgz', 'rb').read()
s = socket.socket(socket.AF_UNIX); s.settimeout(1800); s.connect('/run/docker.sock')
head = (f"POST /build?t={tag}&dockerfile=docker/golang.Dockerfile&rm=1&forcerm=1 HTTP/1.1\r\n"
        f"Host: localhost\r\nConnection: close\r\nContent-Type: application/x-tar\r\n"
        f"Content-Length: {len(data)}\r\n\r\n")
s.sendall(head.encode())
mv, sent = memoryview(data), 0
while sent < len(data):
    sent += s.send(mv[sent:sent + (1 << 20)])
buf = b""
while True:
    b = s.recv(65536)
    if not b:
        break
    buf += b
s.close()
body = buf[buf.find(b"\r\n\r\n") + 4:]
if b"Transfer-Encoding: chunked" in buf:
    out, i = b"", 0
    while True:
        j = body.find(b"\r\n", i)
        if j < 0:
            break
        n = int(body[i:j].split(b";")[0], 16)
        if n == 0:
            break
        out += body[j + 2:j + 2 + n]
        i = j + 2 + n + 2
    body = out
ok = False
for line in body.decode(errors="replace").splitlines():
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get("error"):
        print("ERROR:", d["error"])
    stream = d.get("stream") or ""
    if "Successfully tagged" in stream or "Successfully built" in stream:
        print(stream.strip())
        ok = True
print("BUILD_OK" if ok else "BUILD_FAILED")
sys.exit(0 if ok else 1)
PY

echo "imagem pronta: $IMAGE_TAG"
