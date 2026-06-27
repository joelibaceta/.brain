import sqlite3
from pathlib import Path
from brain.config import BRAIN_DIR, WORKSPACE_ROOT

KNOWLEDGE_DIR = BRAIN_DIR / "knowledge"
DB_PATH = BRAIN_DIR / "knowledge.db"


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY,
            repo TEXT NOT NULL,
            domain TEXT NOT NULL,
            file_path TEXT NOT NULL,
            content TEXT NOT NULL,
            UNIQUE(repo, domain)
        )
    """)
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(repo, domain, content, content='knowledge', content_rowid='id')")
    con.commit()
    return con


def index_file(repo: str, domain: str, md_path: Path):
    content = md_path.read_text()
    con = _db()
    con.execute(
        "INSERT OR REPLACE INTO knowledge (repo, domain, file_path, content) VALUES (?, ?, ?, ?)",
        (repo, domain, str(md_path), content)
    )
    rowid = con.execute("SELECT id FROM knowledge WHERE repo=? AND domain=?", (repo, domain)).fetchone()[0]
    con.execute("INSERT OR REPLACE INTO knowledge_fts(rowid, repo, domain, content) VALUES (?, ?, ?, ?)",
                (rowid, repo, domain, content))
    con.commit()
    con.close()


def index_all():
    """Re-index all .md files in knowledge dir."""
    for repo_dir in KNOWLEDGE_DIR.iterdir():
        if repo_dir.is_dir():
            for md in repo_dir.glob("*.md"):
                index_file(repo_dir.name, md.stem, md)


def import_quinoto_spec(repo: str) -> dict:
    """Import .quinoto-spec/discovery/ docs as primary knowledge for a repo."""
    # Support nested repos like remesas.com/remesas-api
    repo_path = WORKSPACE_ROOT / repo
    if not repo_path.exists():
        # Try nested: e.g. "remesas.com/remesas-api"
        return {"error": f"Repo not found: {repo_path}"}

    discovery_dir = repo_path / ".quinoto-spec" / "discovery"
    if not discovery_dir.exists():
        return {"error": f"No .quinoto-spec/discovery/ found in {repo}", "path": str(discovery_dir)}

    out_dir = KNOWLEDGE_DIR / repo
    out_dir.mkdir(parents=True, exist_ok=True)

    imported = []
    for md_file in sorted(discovery_dir.glob("*.md")):
        domain = md_file.stem  # e.g. "01-stack-profile"
        dest = out_dir / md_file.name
        content = md_file.read_text()
        dest.write_text(content)
        index_file(repo, domain, dest)
        imported.append(domain)

    return {"status": "imported", "repo": repo, "documents": imported, "count": len(imported)}


def list_domains(repo: str = None) -> list:
    results = []
    search_dir = KNOWLEDGE_DIR / repo if repo else KNOWLEDGE_DIR
    if not search_dir.exists():
        return results
    if repo:
        return [{"repo": repo, "domain": md.stem} for md in sorted(search_dir.glob("*.md"))]
    for repo_dir in sorted(search_dir.iterdir()):
        if repo_dir.is_dir():
            for md in sorted(repo_dir.glob("*.md")):
                results.append({"repo": repo_dir.name, "domain": md.stem})
    return results


def get(repo: str, domain: str) -> dict:
    path = KNOWLEDGE_DIR / repo / f"{domain}.md"
    if not path.exists():
        available = [d["domain"] for d in list_domains(repo)]
        return {"error": f"Domain '{domain}' not found in '{repo}'", "available": available}
    return {"repo": repo, "domain": domain, "content": path.read_text()}


IGNORE_DIRS = {"migrations", "static", "templates", "__pycache__", ".git", "node_modules", "fixtures", "dist", "build"}
CODE_EXTS = {".py", ".js", ".ts", ".rb", ".go", ".java", ".rs"}
MAX_FILE_BYTES = 6_000
MAX_FILES = 8


def list_repo_domains(repo: str) -> dict:
    """List extractable domains for a repo. Prefers QuinotoSpec discovery if available."""
    repo_path = WORKSPACE_ROOT / repo
    if not repo_path.exists():
        return {"error": f"Repo not found: {repo}"}

    quinoto_dir = repo_path / ".quinoto-spec" / "discovery"
    if quinoto_dir.exists():
        docs = [f.stem for f in sorted(quinoto_dir.glob("*.md"))]
        return {"source": "quinoto-spec", "repo": repo, "documents": docs, "hint": "Run brain_knowledge_import_quinoto to index these."}

    domains = []
    for item in sorted(repo_path.iterdir()):
        if item.is_dir() and item.name not in IGNORE_DIRS and not item.name.startswith("."):
            files = [f for f in item.rglob("*") if f.suffix in CODE_EXTS and not any(p in IGNORE_DIRS for p in f.parts)]
            if files:
                domains.append(item.name)
    return {"source": "code-scan", "repo": repo, "domains": domains}


def prepare(repo: str, domain: str) -> dict:
    """Read code files for a domain — returns excerpt for LLM summarization."""
    repo_path = WORKSPACE_ROOT / repo
    domain_path = repo_path / domain
    if not domain_path.exists():
        available = list_repo_domains(repo)
        return {"error": f"Domain '{domain}' not found", "available": available}

    files = sorted([f for f in domain_path.rglob("*") if f.suffix in CODE_EXTS and not any(p in IGNORE_DIRS for p in f.parts)])[:MAX_FILES]
    parts = []
    total = 0
    for f in files:
        rel = f.relative_to(repo_path)
        try:
            content = f.read_text(errors="ignore")[:MAX_FILE_BYTES]
            parts.append(f"### {rel}\n```\n{content}\n```")
            total += len(content)
            if total > 40_000:
                break
        except Exception:
            continue

    return {
        "repo": repo,
        "domain": domain,
        "files_included": len(parts),
        "instruction": (
            "Summarize this domain as a Markdown knowledge document with frontmatter "
            "(repo, domain, tags), then sections: ## Purpose, ## Key Entities, "
            "## Key Behaviors, ## External Dependencies, ## Related Domains (WikiLinks). "
            "Then call brain_knowledge_save with the result."
        ),
        "code": "\n\n".join(parts),
    }


def save(repo: str, domain: str, content: str) -> dict:
    """Persist a knowledge document written by the LLM."""
    out_dir = KNOWLEDGE_DIR / repo
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{domain}.md"
    path.write_text(content)
    index_file(repo, domain, path)
    return {"status": "saved", "path": str(path)}


def search(query: str, repo: str = None) -> list:
    con = _db()
    if repo:
        rows = con.execute(
            "SELECT repo, domain, snippet(knowledge_fts, 2, '[', ']', '...', 20) FROM knowledge_fts WHERE knowledge_fts MATCH ? AND repo = ? ORDER BY rank LIMIT 10",
            (query, repo)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT repo, domain, snippet(knowledge_fts, 2, '[', ']', '...', 20) FROM knowledge_fts WHERE knowledge_fts MATCH ? ORDER BY rank LIMIT 10",
            (query,)
        ).fetchall()
    con.close()
    return [{"repo": r[0], "domain": r[1], "snippet": r[2]} for r in rows]
