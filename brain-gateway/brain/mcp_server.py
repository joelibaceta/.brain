import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from brain.engines import gitnexus, playbooks, environments, knowledge, history


app = Server("brain-gateway")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="brain_query",
            description="Search the codebase using natural language. Routes to GitNexus hybrid search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "repo": {"type": "string", "description": "Optional: limit to a specific repo"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="brain_context",
            description="Get 360° context for a symbol: callers, dependencies, cluster membership.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Symbol name (class, function, etc.)"},
                    "repo": {"type": "string", "description": "Optional: repo name"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="brain_impact",
            description="Blast radius analysis — what breaks if this symbol changes?",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Symbol to analyze"},
                    "direction": {"type": "string", "enum": ["upstream", "downstream"], "default": "downstream"},
                    "repo": {"type": "string"},
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="brain_repos",
            description="List all indexed repositories.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="brain_playbooks_list",
            description="List available playbooks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "description": "all | shared | repo:<name>"},
                },
            },
        ),
        Tool(
            name="brain_playbooks_get",
            description="Get playbook details and required parameters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="brain_playbooks_run",
            description="Execute a playbook deterministically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "params": {"type": "object", "description": "Key-value pairs for playbook parameters"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="brain_playbooks_search",
            description="Find a playbook by natural language description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="brain_env_list",
            description="List all registered environments (projects with their services and DB info).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="brain_env_get",
            description="Get full environment config for a project (services, env vars, connect hints).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="brain_env_resolve",
            description="Resolve a specific resource (database, api, etc.) from a project environment. Returns connection params.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "resource": {"type": "string", "description": "Resource key: database, email, external_api, etc."},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="brain_knowledge_list",
            description="List all extracted domain knowledge documents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Optional: filter by repo"},
                },
            },
        ),
        Tool(
            name="brain_knowledge_get",
            description="Get the full knowledge document for a domain in a repo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "domain": {"type": "string"},
                },
                "required": ["repo", "domain"],
            },
        ),
        Tool(
            name="brain_knowledge_search",
            description="Full-text search across all domain knowledge documents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "repo": {"type": "string", "description": "Optional: limit to a repo"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="brain_knowledge_prepare",
            description="Read source code for a repo domain and return it ready for LLM summarization. After calling this, write the knowledge document and call brain_knowledge_save.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "domain": {"type": "string", "description": "Subdirectory name (e.g. 'backend', 'models', 'views')"},
                },
                "required": ["repo", "domain"],
            },
        ),
        Tool(
            name="brain_knowledge_save",
            description="Save a knowledge document generated by the LLM for a repo domain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "domain": {"type": "string"},
                    "content": {"type": "string", "description": "Full Markdown content of the knowledge document"},
                },
                "required": ["repo", "domain", "content"],
            },
        ),
        Tool(
            name="brain_knowledge_domains",
            description="List extractable domains (code subdirectories) for a repo, before extraction. Returns quinoto-spec documents if available.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                },
                "required": ["repo"],
            },
        ),
        Tool(
            name="brain_history_fetch",
            description="Fetch PRs, commits and issues from GitHub for a repo. Use force=true to always refresh, otherwise only syncs stale files (older than 3 days).",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "force": {"type": "boolean", "default": False},
                },
                "required": ["repo"],
            },
        ),
        Tool(
            name="brain_history_staleness",
            description="Check how old the history files are for a repo and whether they need syncing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                },
                "required": ["repo"],
            },
        ),
        Tool(
            name="brain_history_prs",
            description="Fetch merged PRs from GitHub for a repo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "limit": {"type": "integer", "default": 30},
                },
                "required": ["repo"],
            },
        ),
        Tool(
            name="brain_history_commits",
            description="Fetch recent commits from GitHub for a repo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["repo"],
            },
        ),
        Tool(
            name="brain_history_issues",
            description="Fetch GitHub issues (open and closed) for a repo. Useful to find pending bugs, feature requests and task context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["repo"],
            },
        ),
        Tool(
            name="brain_knowledge_import_quinoto",
            description="Import .quinoto-spec/discovery/ documents directly into Brain knowledge. Use this instead of brain_knowledge_prepare when a repo has QuinotoSpec.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repo name. Supports nested paths like 'remesas.com/remesas-api'"},
                },
                "required": ["repo"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "brain_query":
            result = await gitnexus.query(arguments["query"], arguments.get("repo"))
        elif name == "brain_context":
            result = await gitnexus.context(arguments["name"], arguments.get("repo"))
        elif name == "brain_impact":
            result = await gitnexus.impact(
                arguments["target"],
                arguments.get("direction", "downstream"),
                arguments.get("repo"),
            )
        elif name == "brain_repos":
            result = await gitnexus.list_repos()
        elif name == "brain_playbooks_list":
            result = playbooks.list_playbooks(arguments.get("scope", "all"))
        elif name == "brain_playbooks_get":
            result = playbooks.get_playbook(arguments["name"])
        elif name == "brain_playbooks_run":
            result = playbooks.run_playbook(arguments["name"], arguments.get("params", {}))
        elif name == "brain_playbooks_search":
            result = playbooks.search_playbooks(arguments["query"])
        elif name == "brain_env_list":
            result = environments.list_envs()
        elif name == "brain_env_get":
            result = environments.get_env(arguments["name"])
        elif name == "brain_env_resolve":
            result = environments.resolve(arguments["name"], arguments.get("resource"))
        elif name == "brain_knowledge_list":
            result = knowledge.list_domains(arguments.get("repo"))
        elif name == "brain_knowledge_get":
            result = knowledge.get(arguments["repo"], arguments["domain"])
        elif name == "brain_knowledge_search":
            result = knowledge.search(arguments["query"], arguments.get("repo"))
        elif name == "brain_knowledge_prepare":
            result = knowledge.prepare(arguments["repo"], arguments["domain"])
        elif name == "brain_knowledge_save":
            result = knowledge.save(arguments["repo"], arguments["domain"], arguments["content"])
        elif name == "brain_knowledge_domains":
            result = knowledge.list_repo_domains(arguments["repo"])
        elif name == "brain_knowledge_import_quinoto":
            result = knowledge.import_quinoto_spec(arguments["repo"])
        elif name == "brain_history_fetch":
            if arguments.get("force"):
                result = history.fetch_all(arguments["repo"])
            else:
                result = history.sync_if_stale(arguments["repo"])
        elif name == "brain_history_staleness":
            result = history.staleness(arguments["repo"])
        elif name == "brain_history_prs":
            result = history.fetch_prs(arguments["repo"], arguments.get("limit", 30))
        elif name == "brain_history_commits":
            result = history.fetch_commits(arguments["repo"], arguments.get("limit", 50))
        elif name == "brain_history_issues":
            result = history.fetch_issues(arguments["repo"], arguments.get("limit", 50))
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def run_mcp():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
