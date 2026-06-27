import subprocess
from pathlib import Path
from brain.config import WORKSPACE_ROOT


def _tmux(args: list) -> tuple[int, str]:
    r = subprocess.run(["tmux"] + args, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def list_sessions() -> dict:
    code, out = _tmux(["list-sessions", "-F", "#{session_name}|#{session_activity}|#{session_windows}"])
    if code != 0:
        return {}
    sessions = {}
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            sessions[parts[0]] = {"last_activity": parts[1], "windows": parts[2]}
    return sessions


def connect(repo: str) -> dict:
    repo_path = WORKSPACE_ROOT / repo
    if not repo_path.exists():
        return {"error": f"Repo '{repo}' not found at {repo_path}"}

    session = f"brain-{repo}"
    existing = list_sessions()

    if session in existing:
        return {"status": "attached", "session": session, "note": f"tmux attach -t {session}"}

    # create new session detached, cd to repo
    code, _ = _tmux(["new-session", "-d", "-s", session, "-c", str(repo_path)])
    if code != 0:
        return {"error": "Failed to create tmux session"}

    return {
        "status": "created",
        "session": session,
        "repo": str(repo_path),
        "note": f"tmux attach -t {session}",
    }


def disconnect(repo: str) -> dict:
    session = f"brain-{repo}"
    existing = list_sessions()
    if session not in existing:
        return {"error": f"No active session for '{repo}'"}

    code, _ = _tmux(["kill-session", "-t", session])
    return {"status": "killed", "session": session} if code == 0 else {"error": "Failed to kill session"}
