"""Windows entry point for the packaged Heka desktop application."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def user_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Heka"
    return Path.home() / "AppData" / "Local" / "Heka"


def main() -> None:
    data_dir = user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    config_file = data_dir / ".env"
    if not config_file.exists():
        config_file.write_text(
            "# Optional cloud model configuration. Heka works locally without a key.\n"
            "# HEKA_CLOUD_API_KEY=your_key_here\n",
            encoding="utf-8",
        )
    os.environ["HEKA_DATA_DIR"] = str(data_dir)
    os.environ["HEKA_CONFIG_FILE"] = str(config_file)
    os.environ.setdefault("HEKA_OPEN_BROWSER", "1")
    from server import run_server
    run_server()


if __name__ == "__main__":
    main()
