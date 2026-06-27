import os
from pathlib import Path

WORKSPACE_ROOT = Path(os.getenv("BRAIN_WORKSPACE", str(Path.home() / "Projects")))
BRAIN_DIR = WORKSPACE_ROOT / ".brain"
MCP_PORT = int(os.getenv("BRAIN_MCP_PORT", "8765"))
HTTP_PORT = int(os.getenv("BRAIN_HTTP_PORT", "8181"))
GITNEXUS_URL = os.getenv("GITNEXUS_URL", "http://localhost:4747")  # gitnexus serve
