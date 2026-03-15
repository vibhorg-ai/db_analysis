"""
Run the DB Analyzer AI v5 API. Execute from v5 directory: python run_api.py
"""
import uvicorn
from backend.core.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(
        "backend.api.app:app",
        host=s.app_host,
        port=s.app_port,
        reload=(s.environment == "dev"),
    )
