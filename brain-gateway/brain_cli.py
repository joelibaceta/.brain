#!/usr/bin/env python3
"""
brain connect <repo>    — create/attach tmux session for a repo
brain disconnect <repo> — kill the session
brain sessions          — list active sessions
"""
import sys
import os
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain.engines.sessions import connect, disconnect, list_sessions


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "sessions":
        s = list_sessions()
        if not s:
            print("No active sessions.")
        for name, info in s.items():
            print(f"  {name}  (last activity: {info['last_activity']})")

    elif cmd == "connect":
        if len(args) < 2:
            print("Usage: brain connect <repo>")
            sys.exit(1)
        result = connect(args[1])
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        print(f"[{result['status']}] {result['session']}")
        print(f"  cd: {result.get('repo', '')}")
        # attach interactively
        os.execlp("tmux", "tmux", "attach", "-t", result["session"])

    elif cmd == "disconnect":
        if len(args) < 2:
            print("Usage: brain disconnect <repo>")
            sys.exit(1)
        result = disconnect(args[1])
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        print(f"[killed] {result['session']}")

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
