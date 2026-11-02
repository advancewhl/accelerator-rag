#!/usr/bin/env python3
"""Run one command on the GPU host through the documented zyf jump host.

Credentials are read at runtime from the existing credential loader and never
printed.  This script is for controlled maintenance; it does not store or log
the password, and it uses the system known-hosts policy with RejectPolicy.

Usage:
    python scripts/gpu_remote.py --command 'hostname; whoami'
    python scripts/gpu_remote.py --script /path/local-script.sh
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, "/home/whloong/projects/data_analysis/gpu-monitor")

import paramiko  # noqa: E402
from tunnel import connection_settings  # noqa: E402


def connect():
    jump_user, jump_host, jump_password, target_host, target_password = (
        connection_settings()
    )
    jump = paramiko.SSHClient()
    jump.load_system_host_keys()
    jump.set_missing_host_key_policy(paramiko.RejectPolicy())
    jump.connect(
        jump_host,
        username=jump_user,
        password=jump_password,
        timeout=20,
        banner_timeout=20,
        auth_timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    jump_transport = jump.get_transport()
    jump_transport.set_keepalive(30)
    hop = jump_transport.open_channel(
        "direct-tcpip", (target_host, 22), ("127.0.0.1", 0)
    )
    target = paramiko.SSHClient()
    target.load_system_host_keys()
    target.set_missing_host_key_policy(paramiko.RejectPolicy())
    target.connect(
        target_host,
        username="root",
        password=target_password,
        sock=hop,
        timeout=20,
        banner_timeout=20,
        auth_timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    target.get_transport().set_keepalive(30)
    return jump, target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--command", help="remote shell command")
    group.add_argument("--script", type=Path, help="local shell script to run remotely")
    group.add_argument("--put", nargs=2, metavar=("LOCAL", "REMOTE"))
    group.add_argument("--get", nargs=2, metavar=("REMOTE", "LOCAL"))
    group.add_argument("--mkdir", metavar="REMOTE")
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    if args.put or args.get or args.mkdir:
        command = None
    elif args.command:
        command = args.command
    elif args.script:
        command = "bash -s"
    else:
        command = sys.stdin.read()
    jump, target = connect()
    try:
        if args.put or args.get or args.mkdir:
            sftp = target.open_sftp()
            try:
                def ensure_dir(remote: str) -> None:
                    parts = [part for part in remote.split("/") if part]
                    current = ""
                    for part in parts:
                        current += "/" + part
                        try:
                            sftp.stat(current)
                        except OSError:
                            sftp.mkdir(current)

                if args.mkdir:
                    ensure_dir(args.mkdir)
                elif args.put:
                    local, remote = args.put
                    ensure_dir(remote.rsplit("/", 1)[0])
                    sftp.put(local, remote, confirm=True)
                else:
                    remote, local = args.get
                    sftp.get(remote, local)
            finally:
                sftp.close()
            return 0
        stdin, stdout, stderr = target.exec_command(
            command, timeout=args.timeout, get_pty=False
        )
        if args.script:
            stdin.write(args.script.read_text(encoding="utf-8"))
            stdin.channel.shutdown_write()
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        if output:
            sys.stdout.write(output)
        if error:
            sys.stderr.write(error)
        return status
    finally:
        target.close()
        jump.close()


if __name__ == "__main__":
    raise SystemExit(main())
