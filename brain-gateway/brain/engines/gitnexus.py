import httpx
from brain.config import GITNEXUS_URL

# GitNexus serve API: GET /api/repos, POST /api/search, POST /api/query (cypher)

async def _post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{GITNEXUS_URL}{path}", json=body, timeout=30)
        r.raise_for_status()
        return r.json()


async def _get(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{GITNEXUS_URL}{path}", timeout=10)
        r.raise_for_status()
        return r.json()


async def query(search_query: str, repo: str = None) -> dict:
    body = {"query": search_query}
    if repo:
        body["repo"] = repo
    return await _post("/api/search", body)


async def context(name: str, repo: str = None) -> dict:
    where = f'n.name = "{name}"'
    if repo:
        where += f' AND n.repo = "{repo}"'
    cypher = f"""
        MATCH (n) WHERE {where}
        OPTIONAL MATCH (caller)-[:CALLS]->(n)
        OPTIONAL MATCH (n)-[:CALLS]->(callee)
        OPTIONAL MATCH (n)-[:IMPORTS]->(dep)
        RETURN n, collect(DISTINCT caller) AS callers,
               collect(DISTINCT callee) AS callees,
               collect(DISTINCT dep) AS deps
        LIMIT 1
    """
    result = await _post("/api/query", {"cypher": cypher, "repo": repo or ""})
    return result


async def impact(target: str, direction: str = "downstream", repo: str = None) -> dict:
    if direction == "downstream":
        # who calls this target?
        cypher = f'MATCH (caller)-[r]->(n) WHERE n.name = "{target}" AND r.type = "CALLS" RETURN DISTINCT caller.name AS name, caller.filePath AS filePath LIMIT 30'
    else:
        # what does this target call?
        cypher = f'MATCH (n)-[r]->(callee) WHERE n.name = "{target}" AND r.type = "CALLS" RETURN DISTINCT callee.name AS name, callee.filePath AS filePath LIMIT 30'
    result = await _post("/api/query", {"cypher": cypher})
    return {"target": target, "direction": direction, "affected": result.get("result", [])}


async def list_repos() -> list:
    return await _get("/api/repos")
