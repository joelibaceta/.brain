# Brain — Engineering Knowledge Platform

> The LLM reasons. Brain remembers.

---

## The problem

Every time you start a session with an LLM inside a codebase, it starts from zero:

- It doesn't know how your system is structured
- It doesn't know your conventions
- It doesn't know why that code exists or what bug it fixed
- It doesn't know how to connect to your infrastructure
- It doesn't remember what was decided last week

The typical solution is to dump context into the prompt. That scales poorly, costs tokens, and still misses the institutional knowledge that lives in your git history, your ADRs, and your head.

**Brain is a different approach:** instead of feeding context to the LLM on every session, you build a persistent knowledge layer that sits alongside your workspace. The LLM queries it. The LLM reasons on top of it. The LLM never has to re-derive what Brain already knows.

---

## Core idea

```
Traditional:   Code → LLM (re-derives everything, every time)

Brain:         Code
                 ↓
               AST + Graph
                 ↓
               Knowledge
                 ↓
               LLM          (reasons on top of pre-extracted knowledge)
```

The Brain is **LLM-independent**. Claude, GPT, Qwen, Gemini — they all consume the same Brain. You switch models without losing context.

---

## Architecture

Brain is a set of engines that each solve a specific "why does the LLM have to figure this out?" problem.

```
Workspace (multi-repo)
        │
        ▼
┌─────────────────────────────┐
│  GitNexus MCP               │  ← code structure layer (external)
│  Tree-sitter + graph        │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Knowledge Engine           │  ← business domains extracted from code
│  "how does this system work?"│
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Playbook Engine            │  ← deterministic action sequences
│  "how do I do X?"           │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Change Intelligence        │  ← git history with meaning
│  "why does this code exist?"│
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Environment Registry       │  ← "prod" → real hostnames/ports
│  "where is prod?"           │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Conventions Engine         │  ← coding conventions per repo/language
│  "how should I write this?" │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Session Priming            │  ← injects context at session start
│  auto-generates CLAUDE.md   │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Engram Memory              │  ← conversations, decisions, bugs found
│  "what did we decide?"      │  (external: github.com/Gentleman-Programming/engram)
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Brain Gateway MCP          │  ← single interface for any LLM
│  brain.query(...)           │
└─────────────────────────────┘
```

---

## Components explained

### 1. GitNexus — code structure layer

Instead of building a parser and graph engine from scratch, Brain uses [GitNexus](https://github.com/abhigyanpatwari/GitNexus) — an open-source MCP server that indexes any repository into a knowledge graph using Tree-sitter.

What it gives you for free:
- Full AST parsing across languages
- Cross-file symbol resolution
- Call graph and dependency graph
- Leiden community clustering (auto-detects functional modules)
- Blast radius analysis ("what breaks if I change X?")
- Hybrid BM25 + semantic search over the graph
- Multi-repo support via a global registry

You never write a parser. You never build a graph database. GitNexus handles all of that and exposes it over MCP.

```bash
npx gitnexus analyze    # index a repo
npx gitnexus setup      # configure MCP for Claude Code / Cursor
```

> License: PolyForm Noncommercial — free for personal use.

### 2. Knowledge Engine

GitNexus gives you structure. The Knowledge Engine extracts **meaning**.

It queries GitNexus clusters and uses an LLM (at indexing time, not query time) to summarize them into business knowledge:

```yaml
---
domain: Authentication
components: [LoginService, JwtService, OAuthController]
dependencies: [Redis, PostgreSQL]
exposes: [POST /login]
conventions: [Refresh Token required]
repos: [repo-a]
last_indexed: 2026-06-27
---

Every authentication flow ends by generating a JWT.
Refresh tokens are stored in Redis with a 7-day TTL.
```

Key constraint: **the LLM runs once at indexing time**. After that, knowledge is stored as Markdown + SQLite and served without any LLM call.

Knowledge files are Obsidian-compatible — open `.brain/` as a vault and you get a visual graph of your system's business domains.

### 3. Playbook Engine

The most immediate win. Playbooks are YAML files that describe deterministic action sequences — things the LLM would otherwise have to reason about every time.

```yaml
name: ssh-tunnel-db
description: Open an SSH tunnel to a remote database
parameters:
  - name: env
    required: true      # "prod", "staging" — resolved by Environment Registry
  - name: database
    required: true      # "postgres", "mysql"
steps:
  - type: shell
    run: ssh -N -L {{ local_port }}:{{ db_host }}:{{ db_port }} {{ ssh_user }}@{{ ssh_host }}
```

The LLM doesn't figure out SSH flags. It doesn't remember hostnames. It calls `brain.playbooks.run("ssh-tunnel-db", { env: "prod", database: "postgres" })` and Brain executes it.

Playbooks are scoped:
- `playbooks/shared/` — cross-repo (SSH, DB connections, deploys)
- `playbooks/repos/<name>/` — per-repo (run tests, migrate DB, build image)

### 4. Change Intelligence

Brain extracts meaning from git history so the LLM can answer "why does this code exist?" without doing `git blame` archaeology.

Every significant change gets indexed as:

```yaml
type: fix
date: 2026-06-15
domains: [Authentication]
components: [JwtService]
summary: JWT tokens expired 1h early due to timezone offset in token generation
root_cause: datetime.utcnow() instead of datetime.now(UTC)
broke_before: POST /login returned 401 after ~23h with valid credentials
```

Then the LLM can ask:
```python
brain.history.why("auth/jwt_service.py", lines=45-52)
# → "Added in PR #98 — hotfix for a race condition in token refresh"

brain.history.fixes(repo="repo-a")
# → all bug fixes, summarized
```

### 5. Environment Registry

Playbooks and the LLM should never hardcode hostnames. The Environment Registry maps names to actual infrastructure:

```yaml
# environments/prod.yaml
name: prod
databases:
  postgres:
    host: db.prod.internal
    port: 5432
    tunnel_via: bastion
servers:
  bastion: bastion.prod.internal
```

`brain.env.resolve("prod", "postgres")` returns the full connection params. Playbooks call it automatically.

### 6. Conventions Engine

Coding conventions are extracted from the codebase and stored as queryable YAML. The LLM calls `brain.conventions.list(repo="repo-a")` before generating code and follows them — without being reminded in the prompt every time.

### 7. Session Priming

When a session starts in a repo, `brain.prime(repo)` returns:
- Active domain
- Relevant conventions
- Recent changes
- Available playbooks
- Memory summary from last session

Brain also auto-generates a `CLAUDE.md` in each repo root that Claude Code reads automatically on every session start.

### 8. Engram — session memory

[Engram](https://github.com/Gentleman-Programming/engram) provides persistent memory across sessions: conversations, decisions made, bugs found, preferences. SQLite + FTS5, zero external dependencies, MCP-compatible.

It stores what *happened in sessions*. Change Intelligence stores what *happened in the code*. They're complementary.

### 9. Brain Gateway

A single MCP server that routes to all engines. Every LLM client talks only to Brain — never directly to GitNexus, SQLite, or Engram.

```python
brain.query(question)                     # routes to Knowledge + Memory + GitNexus
brain.explain(symbol)                     # full context: knowledge + graph + history
brain.history.why(file, lines)            # why does this code exist?
brain.playbooks.run(name, params)         # execute deterministically
brain.env.resolve(env, resource)          # resolve environment alias
brain.conventions.list(repo)             # coding conventions
brain.prime(repo)                         # session context injection
```

---

## Workspace layout

```
Projects/
├── repo-a/
│   └── CLAUDE.md          ← auto-generated by brain.prime()
├── repo-b/
│   └── CLAUDE.md
└── .brain/
    ├── knowledge/          ← Obsidian vault (private, not committed)
    ├── playbooks/
    │   ├── shared/         ← cross-repo templates (committed here)
    │   └── repos/          ← per-repo templates
    ├── environments/       ← private, not committed
    ├── conventions/        ← private, not committed
    ├── history/            ← private, not committed
    ├── memory/             ← Engram data, private
    └── decisions/          ← ADRs, private
```

---

## Technology stack

| Layer | Tool | Why |
|---|---|---|
| Code parsing + graph | GitNexus | Solves the hardest part — don't rebuild it |
| Knowledge + Playbooks + Gateway | Built here | The differentiating layer |
| Session memory | Engram | SQLite + MCP, zero deps |
| Knowledge store | Markdown + SQLite | Human-readable, Obsidian-compatible, versionable |
| Playbook store | YAML | Simple, inspectable, no runtime required |

No Neo4j. No Qdrant. No cloud required. Runs entirely local.

---

## How to copy this

1. **Set up GitNexus** across your repos: `npx gitnexus analyze` in each one
2. **Create `.brain/`** at the root of your workspace
3. **Copy `playbooks/shared/`** from this repo as your starting templates
4. **Build the Knowledge Engine** — query `gitnexus group_list`, run an LLM on each cluster, save as Markdown
5. **Build the Brain Gateway** — a Python MCP server that routes `brain.*` calls to the right engine
6. **Set up Engram** for session memory
7. **Open `.brain/` in Obsidian** to browse your knowledge graph

The playbooks in this repo are ready to use. Customize the parameters for your own infrastructure.

---

## Status

Design complete. Implementation in progress.
