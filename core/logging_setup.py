from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def get_logger(name: str, filepath: Path | str) -> logging.Logger:
    """Configure root logging (file + stderr) and return a named logger."""
    level = logging.DEBUG if os.environ.get("TWITCH_DEBUG") else logging.INFO
    fmt = logging.Formatter("%(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    file_handler = logging.FileHandler(
        Path(filepath), mode="w", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    return logging.getLogger(name)
