#!/usr/bin/env python3
"""Password-auth SSH/SFTP helper for the SQCAD cloud GPU box.

Credentials are read from the environment only (G-16: no hardcoded secrets):
    SQCAD_SSH_HOST, SQCAD_SSH_PORT, SQCAD_SSH_USER, SQCAD_SSH_PASSWORD

Usage:
    python scripts/cloud_ssh.py run  "<remote shell command>"
    python scripts/cloud_ssh.py put  <local> <remote>
    python scripts/cloud_ssh.py get  <remote> <local>
    python scripts/cloud_ssh.py putb <local> <remote>   # exec-channel upload
    python scripts/cloud_ssh.py getb <remote> <local>   # exec-channel download
    python scripts/cloud_ssh.py ls   <remote dir>

`putb`/`getb` move bytes as base64 over the exec channel.  Use them when the
box's SFTP subsystem is unavailable: this host has been observed answering
ENOENT for every SFTP path including `/` while exec still works, so put/get
fail with a misleading "No such file" for files that demonstrably exist.
"""
from __future__ import annotations

import base64
import os
import shlex
import sys
from pathlib import Path

import paramiko


def _client() -> paramiko.SSHClient:
    host = os.environ.get("SQCAD_SSH_HOST", "connect.westb.seetacloud.com")
    port = int(os.environ.get("SQCAD_SSH_PORT", "16420"))
    user = os.environ.get("SQCAD_SSH_USER", "root")
    password = os.environ.get("SQCAD_SSH_PASSWORD")
    if not password:
        raise SystemExit("SQCAD_SSH_PASSWORD is not set in the environment")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(
        hostname=host,
        port=port,
        username=user,
        password=password,
        look_for_keys=False,
        allow_agent=False,
        timeout=30,
        banner_timeout=30,
        auth_timeout=30,
    )
    return cli


def run(cli: paramiko.SSHClient, command: str) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    chan = cli.get_transport().open_session()
    chan.settimeout(None)
    chan.get_pty()
    chan.exec_command(command)
    while True:
        data = chan.recv(65536)
        if not data:
            break
        sys.stdout.write(data.decode("utf-8", "replace"))
        sys.stdout.flush()
    return chan.recv_exit_status()


def _exec_capture(cli: paramiko.SSHClient, command: str) -> tuple[bytes, int]:
    """Run a command with NO pty and return raw stdout (pty mangles binary)."""
    chan = cli.get_transport().open_session()
    chan.settimeout(None)
    chan.exec_command(command)
    buf = bytearray()
    while True:
        data = chan.recv(1 << 20)
        if not data:
            break
        buf.extend(data)
    return bytes(buf), chan.recv_exit_status()


def get_b64(cli: paramiko.SSHClient, remote: str, local: str) -> int:
    """Fetch a file over the exec channel instead of SFTP.

    The box's SFTP subsystem answers ENOENT for every path including `/`, while
    exec works fine, so transfers cannot depend on it.  base64 keeps the stream
    ASCII-safe; the decoded size is checked against the remote stat so a
    truncated stream fails loudly rather than landing a short file.
    """
    q = shlex.quote(remote)
    out, rc = _exec_capture(cli, f"base64 -w0 {q} 2>/dev/null; echo; stat -c%s {q}")
    if rc != 0:
        raise SystemExit(f"remote read failed (rc={rc}): {remote}")
    # rstrip first: stat emits its own trailing newline, so splitting on the
    # last newline of the raw stream would put the size in `blob` and leave
    # `tail` empty, corrupting the payload instead of validating it.
    blob, _, tail = out.rstrip().rpartition(b"\n")
    expect = int(tail.strip() or -1)
    raw = base64.b64decode(blob.strip(), validate=False)
    if expect >= 0 and len(raw) != expect:
        raise SystemExit(f"size mismatch: got {len(raw)}, remote {expect}")
    Path(local).parent.mkdir(parents=True, exist_ok=True)
    Path(local).write_bytes(raw)
    print(f"GET(b64) ok: {remote} -> {local} ({len(raw)} bytes)")
    return 0


def put_b64(cli: paramiko.SSHClient, local: str, remote: str) -> int:
    """Upload over the exec channel (same SFTP-outage workaround as get_b64)."""
    raw = Path(local).read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    q = shlex.quote(remote)
    _, rc = _exec_capture(cli, f"mkdir -p $(dirname {q}) && : > {q}.b64")
    if rc != 0:
        raise SystemExit(f"remote prepare failed (rc={rc}): {remote}")
    step = 60000
    for i in range(0, len(b64), step):
        part = b64[i:i + step]
        _, rc = _exec_capture(cli, f"printf %s {shlex.quote(part)} >> {q}.b64")
        if rc != 0:
            raise SystemExit(f"chunk {i} failed (rc={rc})")
    out, rc = _exec_capture(
        cli, f"base64 -d {q}.b64 > {q} && rm -f {q}.b64 && stat -c%s {q}")
    if rc != 0:
        raise SystemExit(f"remote decode failed (rc={rc}): {out!r}")
    got = int(out.strip() or -1)
    if got != len(raw):
        raise SystemExit(f"size mismatch: local {len(raw)}, remote {got}")
    print(f"PUT(b64) ok: {local} -> {remote} ({len(raw)} bytes)")
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    action = sys.argv[1]
    cli = _client()
    try:
        if action == "run":
            return run(cli, sys.argv[2])
        if action == "getb":
            return get_b64(cli, sys.argv[2], sys.argv[3])
        if action == "putb":
            return put_b64(cli, sys.argv[2], sys.argv[3])
        sftp = cli.open_sftp()
        if action == "put":
            sftp.put(sys.argv[2], sys.argv[3])
            print(f"PUT ok: {sys.argv[2]} -> {sys.argv[3]}")
        elif action == "get":
            sftp.get(sys.argv[2], sys.argv[3])
            size = os.path.getsize(sys.argv[3])
            print(f"GET ok: {sys.argv[2]} -> {sys.argv[3]} ({size} bytes)")
        elif action == "ls":
            for entry in sorted(sftp.listdir(sys.argv[2])):
                print(entry)
        else:
            raise SystemExit(f"unknown action: {action}")
        sftp.close()
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    raise SystemExit(main())
