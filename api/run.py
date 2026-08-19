"""Raqib API entrypoint.

Serves the FastAPI backend (and the built SPA from dist/ when present).
Binds 0.0.0.0 so Freebuff-style previews can reach it; PORT env respected.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Raqib API")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    from api.app.main import create_app

    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
