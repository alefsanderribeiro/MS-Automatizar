#!/usr/bin/env python3
"""
Executa a manutenção completa em uma passada:
  stop container -> cleanup.py --apply -> start container -> healthcheck

Uso: sudo python3 maintenance.py [--prune-media-days N]
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, "/tmp")
import dk  # noqa: E402

CONTAINER = "ms-automatizar-whatsapp"
HERE = os.path.dirname(os.path.abspath(__file__))


def state():
    st, c = dk.j("GET", f"/containers/{CONTAINER}/json")
    return c["State"]["Status"], c["State"].get("Health", {}).get("Status")


def wait_healthy(timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        s, h = state()
        if s == "running" and h == "healthy":
            return True
        time.sleep(3)
    return False


print("=== estado inicial ===")
print(state())

print("=== parando container ===")
print("stop:", dk.j("POST", f"/containers/{CONTAINER}/stop?t=30")[0])
time.sleep(3)
print("estado:", state())

print("=== cleanup --apply ===")
cmd = [sys.executable, f"{HERE}/cleanup.py", "--apply"] + sys.argv[1:]
p = subprocess.run(cmd, capture_output=True, text=True)
print(p.stdout[-6000:])
if p.returncode != 0:
    print("STDERR:", p.stderr[-2000:])

print("=== iniciando container ===")
print("start:", dk.j("POST", f"/containers/{CONTAINER}/start")[0])
ok = wait_healthy()
print("healthy:", ok)
print("estado:", state())
if not ok:
    sys.exit(1)
