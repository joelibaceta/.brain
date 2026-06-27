#!/usr/bin/env python3
"""
Brain Gateway — entry point.

Modes:
  python main.py mcp     Start MCP server (stdio, for Claude Code)
  python main.py http    Start HTTP server (for browser monitoring)
  python main.py both    Start both (MCP on stdio + HTTP on port 8080)
"""
import sys
import asyncio


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "mcp"

    if mode == "mcp":
        from brain.mcp_server import run_mcp
        asyncio.run(run_mcp())

    elif mode == "http":
        from brain.http.server import run
        run()

    elif mode == "both":
        import threading
        from brain.http.server import run as run_http
        from brain.mcp_server import run_mcp

        http_thread = threading.Thread(target=run_http, daemon=True)
        http_thread.start()
        asyncio.run(run_mcp())

    else:
        print(f"Unknown mode: {mode}. Use: mcp | http | both")
        sys.exit(1)


if __name__ == "__main__":
    main()
