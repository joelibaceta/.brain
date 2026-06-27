import subprocess
import yaml
from pathlib import Path
from jinja2 import Template
from brain.config import BRAIN_DIR


def _playbook_dirs():
    shared = BRAIN_DIR / "playbooks" / "shared"
    repos = BRAIN_DIR / "playbooks" / "repos"
    return shared, repos


def list_playbooks(scope: str = "all") -> list:
    shared, repos_dir = _playbook_dirs()
    results = []

    if scope in ("all", "shared") and shared.exists():
        for f in shared.glob("*.yaml"):
            pb = yaml.safe_load(f.read_text())
            results.append({"file": str(f), **pb})

    if scope == "all" or scope.startswith("repo:"):
        repo_name = scope.split(":", 1)[1] if ":" in scope else None
        if repos_dir.exists():
            for repo_dir in repos_dir.iterdir():
                if repo_dir.is_dir() and (not repo_name or repo_dir.name == repo_name):
                    for f in repo_dir.glob("*.yaml"):
                        pb = yaml.safe_load(f.read_text())
                        results.append({"file": str(f), **pb})

    return results


def get_playbook(name: str) -> dict | None:
    for pb in list_playbooks():
        if pb.get("name") == name:
            return pb
    return None


def run_playbook(name: str, params: dict = None) -> dict:
    params = params or {}
    pb = get_playbook(name)
    if not pb:
        return {"error": f"Playbook '{name}' not found"}

    # auto-resolve env: param → inject service connection params
    if "env" in params:
        from brain.engines.environments import resolve
        env_name = params.pop("env")
        resource = params.pop("resource", None) or "database"
        resolved = resolve(env_name, resource)
        if "error" not in resolved:
            params.update({k: v for k, v in resolved.items() if k not in params})

    # validate required params
    for p in pb.get("parameters", []):
        if p.get("required") and p["name"] not in params:
            default = p.get("default", "")
            if default:
                params[p["name"]] = default
            else:
                return {"error": f"Missing required parameter: {p['name']}"}

    # fill defaults
    for p in pb.get("parameters", []):
        if p["name"] not in params and "default" in p:
            params[p["name"]] = p["default"]

    outputs = []
    for step in pb.get("steps", []):
        if step["type"] == "shell":
            cmd = Template(step["run"]).render(**params)
            working_dir = step.get("working_dir")
            cwd = str(BRAIN_DIR.parent / working_dir) if working_dir else None
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, cwd=cwd
            )
            outputs.append({
                "cmd": cmd,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            })
            if result.returncode != 0:
                break

    return {"playbook": name, "params": params, "steps": outputs}


def search_playbooks(query: str) -> list:
    q = query.lower()
    return [
        pb for pb in list_playbooks()
        if q in pb.get("description", "").lower()
        or q in pb.get("name", "").lower()
        or any(q in t for t in pb.get("tags", []))
    ]
