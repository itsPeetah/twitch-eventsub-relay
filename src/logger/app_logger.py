from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


class AppLogger:
    """
    Timestamped file under ``<project_root>/logs/`` plus stderr.

    ``name`` is the ``logging`` logger name; ``stem`` selects the filename suffix
    (defaults to ``name``).

    Use :meth:`create` when you only need a configured :class:`logging.Logger`.
    Construct ``AppLogger(...)`` directly when you also need :attr:`log_path`.
    """

    log_path: Path
    logger: logging.Logger

    @classmethod
    def create(
        cls,
        project_root: Path | str,
        *,
        name: str,
        stem: str | None = None,
    ) -> logging.Logger:
        """Configure logging and return the stdlib logger (one-step for callers)."""
        return cls(project_root, name=name, stem=stem).logger

    def __init__(
        self,
        project_root: Path | str,
        *,
        name: str,
        stem: str | None = None,
    ) -> None:
        root = Path(project_root)
        file_stem = stem if stem is not None else name

        logs_dir = root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_path = logs_dir / f"{ts}_{file_stem}.log"

        level = logging.DEBUG if os.environ.get("TWITCH_DEBUG") else logging.INFO
        fmt = logging.Formatter("%(levelname)s %(name)s: %(message)s")
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()
        logger.propagate = False
        file_handler = logging.FileHandler(
            self.log_path, mode="w", encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        self.logger = logger
