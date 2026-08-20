"""Non-interactive SSH helper for the cloud GPU instance (seetacloud).

Usage:
  CLOUD_SSH_PW='<password>' python tools/cloud_ssh.py "shell command"
  CLOUD_SSH_PW='<password>' python tools/cloud_ssh.py --timeout 3600 "cmd"

The password is taken ONLY from the CLOUD_SSH_PW environment variable; it
must never be hardcoded in this file (credential hygiene).  Prints combined
stdout/stderr and exits with the remote command's exit code.
"""

from __future__ import annotations

import argparse
import os
import sys

import paramiko

HOST = "connect.westd.seetacloud.com"
PORT = 11492
USER = "root"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", help="remote command to run")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--user", default=USER)
    ap.add_argument("--timeout", type=int, default=600,
                    help="command execution timeout (s)")
    args = ap.parse_args()

    pw = os.environ.get("CLOUD_SSH_PW")
    if not pw:
        sys.stderr.write("error: CLOUD_SSH_PW environment variable required\n")
        sys.exit(2)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(args.host, port=args.port, username=args.user,
                       password=pw, timeout=30,
                       look_for_keys=False, allow_agent=False,
                       banner_timeout=30, auth_timeout=30)
        stdin, stdout, stderr = client.exec_command(args.cmd,
                                                    timeout=args.timeout,
                                                    get_pty=True)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        sys.stdout.write(out)
        if err.strip():
            sys.stdout.write("\n[stderr]\n" + err)
        rc = stdout.channel.recv_exit_status()
        sys.exit(rc if rc is not None else 1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
