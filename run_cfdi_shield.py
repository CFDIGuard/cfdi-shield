from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import uvicorn


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return _application_root() / relative_path


def _ensure_runtime_files(root: Path) -> None:
    (root / "logs").mkdir(exist_ok=True)

    env_path = root / ".env"
    if not env_path.exists():
        env_example_path = _resource_path(".env.example")
        if env_example_path.exists():
            shutil.copyfile(env_example_path, env_path)

    from app.db.init_db import ensure_db_initialized

    ensure_db_initialized()


if __name__ == "__main__":
    app_root = _application_root()
    os.chdir(app_root)
    _ensure_runtime_files(app_root)
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
