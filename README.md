# Brain — Engineering Knowledge Platform

> The LLM reasons. Brain remembers.

---

## Motivation

### 1. Work from anywhere, on anything

Sit down at any device — a phone, a borrowed laptop, a tablet — open a terminal or a browser, and continue exactly where you left off. No `git clone`. No environment setup. No "which version of Node do I need?". No SSH keys to configure. No credentials to copy over.

The laptop is just a screen and a keyboard. Everything else lives on the server.

### 2. Real hardware where it matters

A cheap laptop is enough when the actual compute happens remotely. The server can be as powerful as you need — and a NAS gives you incrementally expandable storage without limits. Add drives as your repos, history, and knowledge grow. Add a UPS and the server stays up regardless of power interruptions. Your dev environment becomes as reliable as infrastructure.

### 3. Security in one place

Credentials and access to production systems stop being scattered across every machine you own. With Brain, there is one point of access: the server. Production databases, SSH keys, API tokens — they never leave it. Every device connects to the server; the server connects to infrastructure.

If a laptop gets stolen, nothing is compromised. Rotate one set of keys on one machine and you're done.

### 4. Know-how that never disappears

Every convention, every architectural decision, every bug fixed, every domain explained — stored in Brain, attached to your workspace. A new session on any device starts with full context. Switch models, switch devices, switch teams — the knowledge stays.

### 5. Fewer tokens, lower cost

LLMs are expensive when they re-derive the same context on every session. Brain pre-extracts and stores what the model needs to know. The model reasons; Brain remembers. Structural code queries that would cost thousands of tokens in file reads become a single `brain.query()` call answered from a local index.

---

**Brain is for anyone who:**
- Works across multiple devices and is tired of syncing environments
- Wants to work from a phone or minimal setup without sacrificing capability
- Wants a single, secure point of access to all infrastructure
- Uses LLMs heavily and wants to stop paying to re-explain the codebase
- Runs a multi-repo workspace and wants one place that understands all of it

---

## The problem

Every time you start a session with an LLM inside a codebase, it starts from zero:

- It doesn't know how your system is structured
- It doesn't know your conventions
- It doesn't know why that code exists or what bug it fixed
- It doesn't know how to connect to your infrastructure
- It doesn't remember what was decided last week

And on top of that, your dev environment is scattered: code on one machine, tools on another, context lost every time you switch devices.

Brain solves both problems.

---

## Two layers

Brain is built in two independent layers:

```
┌─────────────────────────────────────────┐
│  LAYER 2 — Software                     │
│  Knowledge engines that reduce LLM work │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  LAYER 1 — Infrastructure               │
│  Server-based dev environment           │
│  Laptops as dumb terminals              │
└─────────────────────────────────────────┘
```

---

## Layer 1 — Infrastructure (dumb terminals)

The core idea: **everything runs on the server, nothing on the laptop**.

```
Home server (compute)
├── Brain Gateway    (always-on service)
├── GitNexus MCP     (always-on service)
├── Engram MCP       (always-on service)
├── Claude Code CLI
├── cloudflared      (Cloudflare Tunnel)
├── tmux             (session persistence)
└── /mnt/nas/        ← NAS mounted as local storage
    ├── All repos
    └── .brain/

Cloudflare Tunnel (free tier, no open ports needed)
├── ssh.yourdomain.com    → SSH into server
├── brain.yourdomain.com  → Brain Gateway HTTP (monitoring)
└── code.yourdomain.com   → code-server/IDE (optional)

Any device (laptop, tablet, phone)
├── Terminal  →  ssh user@ssh.yourdomain.com
├── Browser   →  https://brain.yourdomain.com/status
└── IDE       →  VS Code Remote SSH (on local network)
```

### Why Cloudflare Tunnel

No open ports on your router. The server makes an outbound connection to Cloudflare. You access it from anywhere via your domain. Free for personal use.

### Why tmux

SSH connections drop. Without tmux, your Claude session dies when the connection breaks. With tmux, the session lives on the server — you just re-attach:

```bash
ssh user@ssh.yourdomain.com
tmux attach -t repo-a    # back exactly where you left off
```

### Session management per repo

One tmux session per repo, created on-demand, destroyed on disconnect. Sessions don't stay alive when idle (they'd burn tokens). Context is saved to Engram and reloaded on reconnect.

```bash
brain connect repo-a     # creates session if needed, attaches if exists
                         # injects context from last session automatically
brain disconnect         # saves session summary to Engram, kills tmux session
```

Brain Gateway HTTP shows all session state from any browser:

```
GET brain.yourdomain.com/sessions

{
  "repo-a": { "status": "active",  "last_activity": "2 min ago" },
  "repo-b": { "status": "idle",    "last_session": "yesterday" }
}
```

---

## Layer 2 — Software (knowledge engines)

Instead of dumping context into every prompt, Brain pre-extracts and stores it. The LLM queries Brain. Brain answers. No re-derivation every session.

```
Server
    │
    ▼
GitNexus MCP             — code structure, call graph, cross-repo resolution
    │
    ▼
Knowledge Engine         — business domains extracted from code clusters
    │
    ▼
Playbook Engine          — deterministic actions (SSH, DB tunnels, deploys)
    │
    ▼
Change Intelligence      — git history with meaning ("why does this exist?")
    │
    ▼
Environment Registry     — "prod" resolves to real hostnames/ports
    │
    ▼
Conventions Engine       — coding conventions per repo and language
    │
    ▼
Session Priming          — injects full context when a session starts
    │
    ▼
Engram Memory            — conversations, decisions, bugs across sessions
    │
    ▼
Brain Gateway MCP + HTTP — single interface for LLM (MCP) and browser (HTTP)
```

### GitNexus — code structure (external)

[GitNexus](https://github.com/abhigyanpatwari/GitNexus) indexes repositories into a knowledge graph using Tree-sitter. It handles parsing, cross-file symbol resolution, dependency graphs, and Leiden community clustering. Multi-repo support out of the box.

You don't build a parser. You don't build a graph database. GitNexus does it and exposes everything over MCP.

```bash
npx gitnexus analyze    # index a repo
npx gitnexus setup      # configure MCP for Claude Code / Cursor
```

> License: PolyForm Noncommercial — free for personal use.

### Knowledge Engine

Queries GitNexus clusters and uses an LLM (once, at indexing time) to summarize them into business knowledge stored as Markdown:

```yaml
---
domain: Authentication
components: [LoginService, JwtService, OAuthController]
dependencies: [Redis, PostgreSQL]
exposes: [POST /login]
repos: [repo-a]
---
Every authentication flow ends by generating a JWT.
Refresh tokens are stored in Redis with a 7-day TTL.
```

Files are Obsidian-compatible — open `.brain/` as a vault for a visual knowledge graph.

### Playbook Engine

Deterministic YAML action sequences. The LLM decides what to do; Brain knows how to do it.

```yaml
name: ssh-tunnel-db
parameters:
  - name: env       # "prod", "staging" — resolved by Environment Registry
  - name: database  # "postgres", "mysql"
steps:
  - type: shell
    run: ssh -N -L {{ local_port }}:{{ db_host }}:{{ db_port }} {{ ssh_user }}@{{ ssh_host }}
```

```python
brain.playbooks.run("ssh-tunnel-db", { env: "prod", database: "postgres" })
# No SSH flags to remember. No hostname to look up.
```

Scoped as `shared/` (cross-repo) or `repos/<name>/` (per-repo).

### Change Intelligence

Extracts meaning from git history so the LLM can answer "why does this code exist?" without git archaeology:

```python
brain.history.why("auth/jwt_service.py", lines=45-52)
# → "Added in PR #98 — hotfix for a race condition in token refresh under high load"
```

### Environment Registry

Maps environment names to real infrastructure. Playbooks resolve `env: prod` to actual hostnames, ports, and users automatically.

### Conventions Engine

Coding conventions per repo/language stored as queryable YAML. The LLM calls `brain.conventions.list(repo)` before generating code.

### Session Priming

`brain.prime(repo)` aggregates domain context, conventions, recent changes, available playbooks, and Engram memory summary into a single session starter. Also auto-generates `CLAUDE.md` per repo that Claude Code reads on every session start.

### Engram — session memory (external)

[Engram](https://github.com/Gentleman-Programming/engram) stores conversations, decisions, and discoveries across sessions. SQLite + FTS5, zero external dependencies, MCP-compatible.

### Brain Gateway

Single Python process exposing two interfaces:
- **MCP server** — for LLM clients (Claude Code, Cursor, etc.)
- **HTTP server** — for browser monitoring

```
GET  /status              → health of all components
GET  /sessions            → active sessions per repo
GET  /index/status        → indexed repos, freshness, errors
GET  /logs?tail=50        → recent operations
POST /index?repo=repo-a   → trigger re-index
```

---

## Technology stack

| Layer | Tool | License |
|---|---|---|
| Connectivity | Cloudflare Tunnel | Free |
| Session persistence | tmux | Free |
| Code parsing + graph | GitNexus | PolyForm Noncommercial |
| Session memory | Engram | Open source |
| Knowledge + Playbooks + Gateway | Built here | — |
| Knowledge store | Markdown + SQLite | — |
| Playbook / env / convention store | YAML | — |

No Neo4j. No Qdrant. No cloud compute. Runs entirely on your own hardware.

---

## What lives in this repo

Public methodology, templates, and the full Brain Gateway implementation.

```
.brain/
├── README.md                    ← this file
├── .gitignore                   ← keeps all private data out
├── .mcp.json.example            ← Claude Code MCP config template
├── brain-gateway/               ← Python MCP + HTTP server (the engine)
│   ├── main.py                  ← entry point: mcp | http | both
│   ├── requirements.txt
│   ├── brain_cli.py             ← brain connect/disconnect/sessions CLI
│   ├── brain/
│   │   ├── config.py            ← env-based config (BRAIN_WORKSPACE, ports)
│   │   ├── mcp_server.py        ← 19 MCP tools for LLM clients
│   │   ├── engines/
│   │   │   ├── gitnexus.py      ← code search, context, impact (GitNexus API)
│   │   │   ├── knowledge.py     ← domain docs, QuinotoSpec import, FTS search
│   │   │   ├── history.py       ← GitHub PRs/issues/commits via gh CLI
│   │   │   ├── playbooks.py     ← YAML action executor with Jinja2
│   │   │   ├── environments.py  ← service registry with auto-resolution
│   │   │   └── sessions.py      ← tmux session management per repo
│   │   └── http/
│   │       └── server.py        ← monitoring HTTP server (aiohttp)
│   └── scripts/
│       └── extract_knowledge.py ← LLM-based domain extraction (optional)
├── systemd/                     ← service templates for auto-start
│   ├── brain-gateway.service
│   └── gitnexus-serve.service
└── playbooks/
    └── shared/                  ← operational templates
        ├── ssh-run.yaml
        ├── ssh-tunnel-db.yaml
        ├── db-connect-postgres.yaml
        ├── db-connect-mysql.yaml
        └── check-service-logs.yaml
```

Private (never committed): `knowledge/`, `environments/`, `conventions/`, `history/`, `memory/`, `decisions/`, `SPEC.md`.

---

## MCP Tools (19 total)

Once connected, the LLM has access to:

| Tool | What it does |
|------|-------------|
| `brain_query` | Natural language code search via GitNexus |
| `brain_context` | 360° context for a symbol: callers, deps, cluster |
| `brain_impact` | Blast radius — what breaks if this changes? |
| `brain_repos` | List all indexed repositories |
| `brain_knowledge_list` | List extracted domain knowledge documents |
| `brain_knowledge_get` | Get a domain knowledge document |
| `brain_knowledge_search` | Full-text search across all knowledge |
| `brain_knowledge_prepare` | Read source code for LLM summarization |
| `brain_knowledge_save` | Persist a knowledge document |
| `brain_knowledge_domains` | List extractable domains for a repo |
| `brain_knowledge_import_quinoto` | Import QuinotoSpec discovery docs |
| `brain_history_fetch` | Sync PRs/commits/issues (staleness-aware) |
| `brain_history_prs` | Fetch merged PRs from GitHub |
| `brain_history_commits` | Fetch recent commits |
| `brain_history_issues` | Fetch open and closed issues |
| `brain_history_staleness` | Check how old the history files are |
| `brain_playbooks_list` | List available playbooks |
| `brain_playbooks_run` | Execute a playbook deterministically |
| `brain_playbooks_search` | Find a playbook by description |
| `brain_env_list` | List registered environments |
| `brain_env_get` | Get full environment config |
| `brain_env_resolve` | Resolve a service (db, api) from an environment |

---

## How to copy this

### 1. Server setup

Any Linux box with SSH. A NAS with an external drive is ideal for storage.

```bash
sudo apt install tmux git gh
npm install -g gitnexus   # or: npx gitnexus
```

### 2. Cloudflare Tunnel

```bash
# Install cloudflared and create a tunnel
cloudflared tunnel create my-tunnel
# Add to /etc/cloudflared/config.yml:
#   hostname: ssh.yourdomain.com  → ssh://127.0.0.1:22
#   hostname: brain.yourdomain.com → http://127.0.0.1:8181
sudo systemctl enable --now cloudflared
```

### 3. Clone and install Brain Gateway

```bash
git clone https://github.com/joelibaceta/.brain.git
cd .brain/brain-gateway
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure

```bash
export BRAIN_WORKSPACE=~/Projects   # root of all your repos
export BRAIN_HTTP_PORT=8181
```

Copy `.mcp.json.example` to your workspace root as `.mcp.json` and fill in paths.

### 5. Index your repos

```bash
cd ~/Projects/my-repo
npx gitnexus analyze
```

### 6. Install as systemd services

```bash
# Edit systemd/*.service replacing YOUR_USER and YOUR_WORKSPACE
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gitnexus-serve brain-gateway
```

### 7. Open Claude Code from your workspace

```bash
cd ~/Projects/my-repo
claude   # brain_* tools load automatically from .mcp.json
```

---

## Status

**Production.** Running on a home server with a NAS mounted as local storage (8TB+). All services run on the compute box; repos and knowledge live on the NAS. Accessible from anywhere via Cloudflare Tunnel.
