import json
import subprocess
import time
from pathlib import Path
from brain.config import BRAIN_DIR, WORKSPACE_ROOT
from brain.engines.knowledge import index_file

HISTORY_DIR = BRAIN_DIR / "history"
STALE_DAYS = 3  # re-sync if history is older than this


def _gh(args: list) -> tuple[int, str]:
    r = subprocess.run(["gh"] + args, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def _detect_github_repo(repo: str) -> str | None:
    """Get GitHub owner/repo from local git remote."""
    repo_path = WORKSPACE_ROOT / repo
    if not repo_path.exists():
        return None
    r = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        capture_output=True, text=True
    )
    url = r.stdout.strip()
    # ssh: git@github.com:owner/repo.git or https://github.com/owner/repo
    for prefix in ["git@github.com:", "https://github.com/"]:
        if prefix in url:
            slug = url.split(prefix)[-1].removesuffix(".git")
            return slug
    return None


def fetch_prs(repo: str, limit: int = 30) -> dict:
    """Fetch merged PRs from GitHub and save as knowledge."""
    slug = _detect_github_repo(repo)
    if not slug:
        return {"error": f"Could not detect GitHub remote for '{repo}'"}

    code, out = _gh([
        "pr", "list",
        "--repo", slug,
        "--state", "merged",
        "--limit", str(limit),
        "--json", "number,title,body,mergedAt,author,files,labels",
    ])
    if code != 0:
        return {"error": f"gh pr list failed: {out}"}

    prs = json.loads(out) if out else []
    if not prs:
        return {"status": "no_prs", "repo": repo, "slug": slug}

    out_dir = HISTORY_DIR / repo
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [f"# PR History — {repo}\n", f"GitHub: {slug}  |  {len(prs)} PRs\n\n---\n"]
    for pr in prs:
        files = [f["path"] for f in pr.get("files", [])][:10]
        labels = [l["name"] for l in pr.get("labels", [])]
        body = (pr.get("body") or "").strip()[:500]
        lines.append(f"## PR #{pr['number']} — {pr['title']}")
        lines.append(f"**Merged:** {pr.get('mergedAt', '')[:10]}  |  **Author:** {pr['author']['login']}")
        if labels:
            lines.append(f"**Labels:** {', '.join(labels)}")
        if files:
            lines.append(f"**Files:** `{'`, `'.join(files)}`")
        if body:
            lines.append(f"\n{body}")
        lines.append("\n---\n")

    content = "\n".join(lines)
    out_file = out_dir / "pr-history.md"
    out_file.write_text(content)
    index_file(repo, "pr-history", out_file)

    return {"status": "saved", "repo": repo, "slug": slug, "prs": len(prs), "path": str(out_file)}


def fetch_commits(repo: str, limit: int = 50) -> dict:
    """Fetch recent commits and save as knowledge."""
    slug = _detect_github_repo(repo)
    if not slug:
        return {"error": f"Could not detect GitHub remote for '{repo}'"}

    code, out = _gh([
        "api", f"repos/{slug}/commits",
        "--paginate",
        "-X", "GET",
        "-F", f"per_page={limit}",
        "--jq", ".[] | {sha: .sha[:8], message: .commit.message, author: .commit.author.name, date: .commit.author.date[:10], files: [.files[]?.filename][:5]}"
    ])
    if code != 0:
        # Fallback: use local git log
        r = subprocess.run(
            ["git", "-C", str(WORKSPACE_ROOT / repo), "log",
             f"--max-count={limit}", "--pretty=format:%h|%s|%an|%ad", "--date=short"],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            return {"error": "Could not fetch commits"}
        lines = [f"# Commit History — {repo}\n\n"]
        for line in r.stdout.strip().splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                sha, msg, author, date = parts
                lines.append(f"- `{sha}` {date} **{author}**: {msg}")
        content = "\n".join(lines)
    else:
        lines = [f"# Commit History — {repo}\n\n"]
        for line in out.strip().splitlines():
            try:
                c = json.loads(line)
                files = ", ".join(c.get("files", []))
                lines.append(f"- `{c['sha']}` {c['date']} **{c['author']}**: {c['message'].splitlines()[0]}")
                if files:
                    lines.append(f"  *Files: {files}*")
            except Exception:
                continue
        content = "\n".join(lines)

    out_dir = HISTORY_DIR / repo
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "commit-history.md"
    out_file.write_text(content)
    index_file(repo, "commit-history", out_file)

    return {"status": "saved", "repo": repo, "path": str(out_file)}


def fetch_issues(repo: str, limit: int = 50) -> dict:
    """Fetch closed and open issues from GitHub and save as knowledge."""
    slug = _detect_github_repo(repo)
    if not slug:
        return {"error": f"Could not detect GitHub remote for '{repo}'"}

    code, out = _gh([
        "issue", "list",
        "--repo", slug,
        "--state", "all",
        "--limit", str(limit),
        "--json", "number,title,body,state,createdAt,closedAt,author,labels,assignees,comments",
    ])
    if code != 0:
        return {"error": f"gh issue list failed: {out}"}

    issues = json.loads(out) if out else []
    if not issues:
        return {"status": "no_issues", "repo": repo, "slug": slug}

    out_dir = HISTORY_DIR / repo
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [f"# Issue History — {repo}\n", f"GitHub: {slug}  |  {len(issues)} issues\n\n---\n"]
    for issue in issues:
        labels = [l["name"] for l in issue.get("labels", [])]
        assignees = [a["login"] for a in issue.get("assignees", [])]
        body = (issue.get("body") or "").strip()[:800]
        state = issue.get("state", "")
        closed = issue.get("closedAt", "")[:10] if issue.get("closedAt") else "open"
        comments = issue.get("comments", [])

        lines.append(f"## Issue #{issue['number']} — {issue['title']}")
        lines.append(f"**State:** {state}  |  **Created:** {issue.get('createdAt','')[:10]}  |  **Closed:** {closed}")
        if labels:
            lines.append(f"**Labels:** {', '.join(labels)}")
        if assignees:
            lines.append(f"**Assignees:** {', '.join(assignees)}")
        if body:
            lines.append(f"\n{body}")
        # Include first comment if it adds context
        if comments:
            first = comments[0]
            comment_body = (first.get("body") or "").strip()[:400]
            if comment_body:
                lines.append(f"\n> **{first.get('author', {}).get('login', '')}:** {comment_body}")
        lines.append("\n---\n")

    content = "\n".join(lines)
    out_file = out_dir / "issue-history.md"
    out_file.write_text(content)
    index_file(repo, "issue-history", out_file)

    return {"status": "saved", "repo": repo, "slug": slug, "issues": len(issues), "path": str(out_file)}


def staleness(repo: str) -> dict:
    """Check how old the history files are for a repo."""
    repo_dir = HISTORY_DIR / repo
    result = {}
    now = time.time()
    for name in ["pr-history", "commit-history", "issue-history"]:
        f = repo_dir / f"{name}.md"
        if f.exists():
            age_days = (now - f.stat().st_mtime) / 86400
            result[name] = {"exists": True, "age_days": round(age_days, 1), "stale": age_days > STALE_DAYS}
        else:
            result[name] = {"exists": False, "stale": True}
    return result


def sync_if_stale(repo: str) -> dict:
    """Fetch only if history is older than STALE_DAYS. Returns status per file."""
    status = staleness(repo)
    results = {}

    if status["pr-history"]["stale"]:
        results["prs"] = fetch_prs(repo)
    else:
        results["prs"] = {"status": "fresh", "age_days": status["pr-history"]["age_days"]}

    if status["commit-history"]["stale"]:
        results["commits"] = fetch_commits(repo)
    else:
        results["commits"] = {"status": "fresh", "age_days": status["commit-history"]["age_days"]}

    if status["issue-history"]["stale"]:
        results["issues"] = fetch_issues(repo)
    else:
        results["issues"] = {"status": "fresh", "age_days": status["issue-history"]["age_days"]}

    return results


def fetch_all(repo: str) -> dict:
    """Fetch PRs, commits and issues for a repo (force refresh)."""
    prs = fetch_prs(repo)
    commits = fetch_commits(repo)
    issues = fetch_issues(repo)
    return {"prs": prs, "commits": commits, "issues": issues}
