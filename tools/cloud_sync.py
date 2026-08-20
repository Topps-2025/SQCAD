"""AutoDL batch helper: recursive push/pull + exec (33- reproducibility).

Same credentials as ssh_remote.py (env SQCAD_AUTODL_* or tools/.autodl_pw).
All payloads live on the DATA disk /root/autodl-tmp only.

Usage:
  python tools/cloud_sync.py push <local-dir> <remote-abs-dir>
  python tools/cloud_sync.py push-file <local-file> <remote-abs-file>
  python tools/cloud_sync.py pull <remote-abs-dir> <local-dir>
  python tools/cloud_sync.py pull-file <remote-abs-file> <local-file>
  python tools/cloud_sync.py exec "<shell command>"
"""

from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("SQCAD_AUTODL_HOST", "connect.westd.seetacloud.com")
PORT = int(os.environ.get("SQCAD_AUTODL_PORT", "11492"))
USER = os.environ.get("SQCAD_AUTODL_USER", "root")


def _password() -> str:
    pw = os.environ.get("SQCAD_AUTODL_PW")
    if pw:
        return pw
    pwfile = Path(__file__).parent / ".autodl_pw"
    if pwfile.exists():
        return pwfile.read_text(encoding="utf-8").strip()
    raise SystemExit("no password: set SQCAD_AUTODL_PW or tools/.autodl_pw")


def connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=_password(),
              look_for_keys=False, allow_agent=False, timeout=30)
    return c


def _mkdirs(sftp, remote: str) -> None:
    parts = remote.replace("\\", "/").split("/")
    cur = "/"
    for p in parts:
        if not p:
            continue
        cur = cur.rstrip("/") + "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def _put_retry(sftp, local: str, remote: str) -> None:
    """AutoDL SFTP servers can race mkdir/put: CMD_OPEN right after a mkdir
    may return ENOENT.  Re-ensure the parent and retry before giving up."""
    for attempt in range(3):
        try:
            sftp.put(local, remote)
            return
        except FileNotFoundError:
            if attempt == 2:
                print(f"FAILED {local} -> {remote}", file=sys.stderr)
                raise
            _mkdirs(sftp, os.path.dirname(remote))
            time.sleep(0.5 * (attempt + 1))


def push_dir(local: str, remote: str) -> None:
    local = os.path.abspath(local)
    c = connect()
    try:
        sftp = c.open_sftp()
        n = 0
        for root, dirs, files in os.walk(local):
            rel = os.path.relpath(root, local)
            rdir = remote if rel == "." else remote.rstrip("/") + "/" + \
                rel.replace("\\", "/")
            _mkdirs(sftp, rdir)
            for f in files:
                lp = os.path.join(root, f)
                rp = rdir.rstrip("/") + "/" + f
                st = os.stat(lp)
                try:
                    rst = sftp.stat(rp)
                    if rst.st_size == st.st_size and \
                            int(rst.st_mtime) == int(st.st_mtime):
                        continue
                except FileNotFoundError:
                    pass
                _put_retry(sftp, lp, rp)
                n += 1
                print(f"  ↑ {os.path.relpath(lp, local)}", flush=True)
        sftp.close()
        print(f"pushed {n} files -> {remote}")
    finally:
        c.close()


def pull_dir(remote: str, local: str) -> None:
    local = os.path.abspath(local)
    c = connect()
    try:
        sftp = c.open_sftp()

        def walk(rd: str, ld: str) -> None:
            os.makedirs(ld, exist_ok=True)
            for entry in sftp.listdir_attr(rd):
                rp = rd.rstrip("/") + "/" + entry.filename
                lp = os.path.join(ld, entry.filename)
                if stat.S_ISDIR(entry.st_mode):
                    walk(rp, lp)
                else:
                    sftp.get(rp, lp)
                    print(f"  ↓ {entry.filename}", flush=True)

        walk(remote, local)
        print(f"pulled <- {remote}")
    finally:
        c.close()


def push_file(local: str, remote: str) -> None:
    c = connect()
    try:
        sftp = c.open_sftp()
        _mkdirs(sftp, os.path.dirname(remote))
        _put_retry(sftp, local, remote)
        sftp.close()
        print(f"pushed {local} -> {remote}")
    finally:
        c.close()


def pull_file(remote: str, local: str) -> None:
    c = connect()
    try:
        sftp = c.open_sftp()
        os.makedirs(os.path.dirname(os.path.abspath(local)), exist_ok=True)
        sftp.get(remote, local)
        sftp.close()
        print(f"pulled {remote} -> {local}")
    finally:
        c.close()


def exec_remote(cmd: str) -> None:
    c = connect()
    try:
        _, out, err = c.exec_command(cmd, timeout=7200)
        sys.stdout.write(out.read().decode("utf-8", "replace"))
        e = err.read().decode("utf-8", "replace")
        if e:
            sys.stderr.write(e)
    finally:
        c.close()


def main() -> None:
    mode = sys.argv[1]
    if mode == "push":
        push_dir(sys.argv[2], sys.argv[3])
    elif mode == "push-file":
        push_file(sys.argv[2], sys.argv[3])
    elif mode == "pull":
        pull_dir(sys.argv[2], sys.argv[3])
    elif mode == "pull-file":
        pull_file(sys.argv[2], sys.argv[3])
    elif mode == "exec":
        exec_remote(sys.argv[2])
    else:
        raise SystemExit("unknown mode: " + mode)


if __name__ == "__main__":
    main()
