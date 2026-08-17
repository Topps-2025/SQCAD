"""AutoDL remote helper: exec / push / pull / shutdown over SSH.

Password source (first match): env SQCAD_AUTODL_PW, or tools/.autodl_pw
(gitignored).  All payloads live on the DATA disk /root/autodl-tmp only.

Usage:
  python tools/ssh_remote.py exec "<shell command>"
  python tools/ssh_remote.py push <local> <remote-abs>
  python tools/ssh_remote.py pull <remote-abs> <local>
  python tools/ssh_remote.py shutdown
"""

import os
import stat
import sys

import paramiko

HOST = "connect.westc.seetacloud.com"
PORT = 54834
USER = "root"


def _password() -> str:
    pw = os.environ.get("SQCAD_AUTODL_PW")
    if pw:
        return pw
    here = os.path.dirname(os.path.abspath(__file__))
    pwfile = os.path.join(here, ".autodl_pw")
    if os.path.exists(pwfile):
        with open(pwfile, encoding="utf-8") as f:
            return f.read().strip()
    raise SystemExit("no password: set SQCAD_AUTODL_PW or tools/.autodl_pw")


def connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=_password(),
              look_for_keys=False, allow_agent=False, timeout=30)
    return c


def exec_remote(cmd: str) -> None:
    c = connect()
    try:
        _, out, err = c.exec_command(cmd, timeout=3600)
        sys.stdout.write(out.read().decode("utf-8", "replace"))
        e = err.read().decode("utf-8", "replace")
        if e:
            sys.stderr.write(e)
    finally:
        c.close()


def sftp_put(local: str, remote: str) -> None:
    c = connect()
    try:
        sftp = c.open_sftp()
        sftp.put(local, remote)
        sftp.close()
    finally:
        c.close()


def sftp_get(remote: str, local: str) -> None:
    c = connect()
    try:
        sftp = c.open_sftp()
        sftp.get(remote, local)
        sftp.close()
    finally:
        c.close()


def shutdown() -> None:
    c = connect()
    try:
        _, out, err = c.exec_command("shutdown -h now", timeout=30)
        print(out.read().decode("utf-8", "replace"))
        e = err.read().decode("utf-8", "replace")
        if e:
            print(e, file=sys.stderr)
    finally:
        c.close()


def main() -> None:
    mode = sys.argv[1]
    if mode == "exec":
        exec_remote(sys.argv[2])
    elif mode == "push":
        sftp_put(sys.argv[2], sys.argv[3])
    elif mode == "pull":
        sftp_get(sys.argv[2], sys.argv[3])
    elif mode == "shutdown":
        shutdown()
    else:
        raise SystemExit("unknown mode: " + mode)


if __name__ == "__main__":
    main()
