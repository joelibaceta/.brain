# Brain — Engineering Knowledge Platform

> The LLM reasons. Brain remembers.

---

## Motivation

I want to sit down at any device — a phone, a borrowed laptop, a tablet — open a terminal or a browser, and continue exactly where I left off. No git clone. No environment setup. No "which version of Node do I need?". No SSH keys to configure. No credentials to copy.

Everything lives in one place: the server. The context, the code, the agents, the access to databases and production environments. The laptop is just a screen and a keyboard.

This also solves a security problem I've always had: credentials and access to production systems scattered across multiple machines. With Brain, there's a single point of access — the server. Production databases, SSH keys, VPN configs — they never leave it. Every device connects to the server; the server connects to infrastructure. If a laptop gets lost, nothing is compromised.

**Brain is for anyone who:**
- Works across multiple devices and is tired of syncing environments
- Wants to work from a phone or a minimal setup without sacrificing capability
- Wants a single, secure point of access to all their infrastructure
- Uses LLMs heavily and is tired of re-explaining the codebase every session
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
Server (NAS or any Linux box)
├── All repos
├── .brain/
├── Brain Gateway    (always-on service)
├── GitNexus MCP     (always-on service)
├── Engram MCP       (always-on service)
├── Claude Code CLI
├── cloudflared      (Cloudflare Tunnel)
└── tmux             (session persistence)

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

Public methodology and templates only. Private workspace data stays local.

```
.brain/
├── README.md            ← this file
├── .gitignore           ← keeps all private data out
└── playbooks/
    └── shared/          ← operational templates ready to copy and customize
        ├── ssh-run.yaml
        ├── ssh-tunnel-db.yaml
        ├── db-connect-postgres.yaml
        ├── db-connect-mysql.yaml
        └── check-service-logs.yaml
```

Private (never committed): `knowledge/`, `environments/`, `conventions/`, `history/`, `memory/`, `decisions/`, `SPEC.md`.

---

## How to copy this

1. **Set up the server** — any Linux box with SSH access
2. **Set up Cloudflare Tunnel** — expose SSH and Brain Gateway HTTP via your domain
3. **Install tmux** — for session persistence
4. **Set up GitNexus** — `npx gitnexus analyze` in each repo
5. **Copy `playbooks/shared/`** from this repo and customize for your infrastructure
6. **Build Brain Gateway** — Python MCP + HTTP server routing `brain.*` calls
7. **Set up Engram** — for session memory
8. **Open `.brain/` in Obsidian** — browse your knowledge graph visually

---

## Status

Design complete. Implementation in progress.
