"""
Ensures process runs from this script's directory so backend and db_connections.yaml resolve correctly.
"""
import os
import sys

# Run from this script's directory so backend and db_connections.yaml are found
_script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_script_dir)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

import uvicorn
from backend.core.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(
        "backend.api.app:app",
        host=s.app_host,
        port=s.app_port,
        reload=(s.environment == "dev"),
        reload_dirs=["backend"] if s.environment == "dev" else None,
    )
