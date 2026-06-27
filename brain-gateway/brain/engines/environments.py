import yaml
from pathlib import Path
from brain.config import BRAIN_DIR

ENV_DIR = BRAIN_DIR / "environments"


def _load(name: str) -> dict:
    path = ENV_DIR / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Environment '{name}' not found at {path}")
    return yaml.safe_load(path.read_text())


def list_envs() -> list:
    index = ENV_DIR / "_index.yml"
    if index.exists():
        data = yaml.safe_load(index.read_text())
        return data.get("projects", [])
    return [{"name": p.stem} for p in ENV_DIR.glob("*.yml") if p.stem != "_index"]


def get_env(name: str) -> dict:
    return _load(name)


def resolve(name: str, resource: str = None) -> dict:
    env = _load(name)
    if resource is None:
        return env
    services = env.get("services", {})
    if resource in services:
        return services[resource]
    # fuzzy match: db → database
    for key, val in services.items():
        if resource in key or key in resource:
            return val
    return {"error": f"Resource '{resource}' not found in '{name}'", "available": list(services.keys())}
