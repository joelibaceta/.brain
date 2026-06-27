#!/usr/bin/env python3
"""
Extract domain knowledge from a repo using GitNexus + Claude.

Usage:
  python scripts/extract_knowledge.py <repo_name> [--model claude-haiku-4-5-20251001]

Requires: ANTHROPIC_API_KEY env var
"""
import sys
import os
import json
import httpx
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.config import WORKSPACE_ROOT, BRAIN_DIR, GITNEXUS_URL
from brain.engines.knowledge import index_file

KNOWLEDGE_DIR = BRAIN_DIR / "knowledge"
MAX_FILE_BYTES = 8_000
MAX_FILES_PER_DOMAIN = 10
IGNORE_DIRS = {"migrations", "static", "templates", "__pycache__", ".git", "node_modules", "fixtures", "dist", "build"}
CODE_EXTS = {".py", ".js", ".ts", ".rb", ".go", ".java", ".rs"}


def get_domain_dirs(repo_path: Path) -> list[tuple[str, Path]]:
    domains = []
    for item in sorted(repo_path.iterdir()):
        if item.is_dir() and item.name not in IGNORE_DIRS and not item.name.startswith("."):
            code_files = [f for f in item.rglob("*") if f.suffix in CODE_EXTS and not any(p in IGNORE_DIRS for p in f.parts)]
            if code_files:
                domains.append((item.name, item))
    # Also add top-level code files as a "root" domain
    root_files = [f for f in repo_path.glob("*") if f.is_file() and f.suffix in CODE_EXTS]
    if root_files:
        domains.append(("root", repo_path))
    return domains


def read_domain_files(domain_dir: Path, repo_path: Path) -> str:
    files = sorted([f for f in domain_dir.rglob("*") if f.suffix in CODE_EXTS and not any(p in IGNORE_DIRS for p in f.parts)])[:MAX_FILES_PER_DOMAIN]
    parts = []
    total = 0
    for f in files:
        rel = f.relative_to(repo_path)
        try:
            content = f.read_text(errors="ignore")[:MAX_FILE_BYTES]
            parts.append(f"### {rel}\n```\n{content}\n```")
            total += len(content)
            if total > 60_000:
                break
        except Exception:
            continue
    return "\n\n".join(parts)


def extract_with_llm(repo: str, domain: str, code_excerpt: str, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic()

    prompt = f"""You are analyzing the `{domain}` module of the `{repo}` codebase.

Based on the code below, write a concise knowledge document in Markdown with this exact structure:

---
repo: {repo}
domain: {domain}
tags: [list, of, relevant, tags]
---

## Purpose
One paragraph: what does this module do and why does it exist?

## Key Entities
Bullet list of the main classes/models/functions and what each represents.

## Key Behaviors
Bullet list of the main operations, flows, or business rules implemented here.

## External Dependencies
Bullet list of external services, APIs, or libraries this module depends on.

## Related Domains
WikiLinks to related domains in this repo: [[DomainName]]

---

Code:
{code_excerpt}

Write only the Markdown document, no extra commentary."""

    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="Repo name (must exist in WORKSPACE_ROOT)")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001", help="Claude model to use")
    parser.add_argument("--domain", help="Extract only this domain (optional)")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    repo_path = WORKSPACE_ROOT / args.repo
    if not repo_path.exists():
        print(f"Error: repo not found at {repo_path}")
        sys.exit(1)

    out_dir = KNOWLEDGE_DIR / args.repo
    out_dir.mkdir(parents=True, exist_ok=True)

    domains = get_domain_dirs(repo_path)
    if args.domain:
        domains = [(n, p) for n, p in domains if n == args.domain]

    print(f"Extracting knowledge from {args.repo} ({len(domains)} domains)...")

    for domain_name, domain_path in domains:
        print(f"  [{domain_name}]...", end=" ", flush=True)
        code = read_domain_files(domain_path, repo_path)
        if not code.strip():
            print("skipped (no code)")
            continue
        try:
            md = extract_with_llm(args.repo, domain_name, code, args.model)
            out_file = out_dir / f"{domain_name}.md"
            out_file.write_text(md)
            index_file(args.repo, domain_name, out_file)
            print("done")
        except Exception as e:
            print(f"error: {e}")

    print(f"\nKnowledge saved to {out_dir}")


if __name__ == "__main__":
    main()
