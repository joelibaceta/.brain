import json
import subprocess
from aiohttp import web
from brain.config import HTTP_PORT, GITNEXUS_URL
from brain.engines import playbooks, sessions
import httpx


async def status(request):
    components = {}

    # GitNexus
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{GITNEXUS_URL}/api/repos", timeout=3)
            repos = r.json() if r.status_code == 200 else []
            components["gitnexus"] = f"ok ({len(repos)} repos indexed)"
    except Exception:
        components["gitnexus"] = "unreachable"

    components["gateway"] = "ok"
    return web.json_response({"status": "ok", "components": components})


async def sessions_list(request):
    return web.json_response({"sessions": sessions.list_sessions()})


async def session_connect(request):
    repo = request.match_info["repo"]
    return web.json_response(sessions.connect(repo))


async def session_disconnect(request):
    repo = request.match_info["repo"]
    return web.json_response(sessions.disconnect(repo))


async def index_status(request):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{GITNEXUS_URL}/repos", timeout=5)
            repos = r.json() if r.status_code == 200 else []
            return web.json_response({"indexed_repos": repos})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=503)


async def playbooks_list(request):
    scope = request.query.get("scope", "all")
    return web.json_response(playbooks.list_playbooks(scope))


def create_app():
    app = web.Application()
    app.router.add_get("/status", status)
    app.router.add_get("/sessions", sessions_list)
    app.router.add_post("/sessions/{repo}/connect", session_connect)
    app.router.add_post("/sessions/{repo}/disconnect", session_disconnect)
    app.router.add_get("/index/status", index_status)
    app.router.add_get("/playbooks", playbooks_list)
    return app


def run():
    app = create_app()
    web.run_app(app, port=HTTP_PORT, print=lambda _: None)
