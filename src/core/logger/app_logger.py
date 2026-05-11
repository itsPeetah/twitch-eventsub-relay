from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


def _no_logs_env() -> bool:
    """When ``NO_LOGS=1``, skip log files (stderr only) — avoids growing disk on small hosts."""
    return os.environ.get("NO_LOGS", "").strip() == "1"


class AppLogger:
    """
    Timestamped file under ``<project_root>/logs/`` plus stderr, unless ``NO_LOGS=1``
    is set (then stderr only; no ``logs/`` directory is created).

    ``name`` is the ``logging`` logger name; ``stem`` selects the filename suffix
    (defaults to ``name``).

    Handlers live only on :attr:`logger`. Call :meth:`sub` to get descendant
    loggers whose records propagate there so ``%(name)s`` differs while the output
    file stays the same.

    Use :meth:`create` for the usual entrypoint (returns ``AppLogger``). Access
    :attr:`logger` for the base record name (e.g. Twitch stack).
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
    ) -> AppLogger:
        """Configure logging and return this facade (use :attr:`logger` / :meth:`sub`)."""
        return cls(project_root, name=name, stem=stem)

    def sub(self, suffix: str) -> logging.Logger:
        """
        Named child logger under the base :attr:`logger` hierarchy.

        Shares the same file and stderr output; messages show ``suffix`` in the
        logger name (e.g. ``myapp.websockets``). ``suffix`` may contain dots
        (``rabbit.publisher``).
        """
        part = suffix.strip().strip(".")
        if not part:
            raise ValueError("sub logger suffix must be non-empty")
        full_name = f"{self.logger.name}.{part}"
        child = logging.getLogger(full_name)
        child.handlers.clear()
        child.propagate = True
        child.setLevel(self.logger.level)
        return child

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
        no_file_logs = _no_logs_env()

        if no_file_logs:
            self.log_path = logs_dir / ".no_file_logging"
        else:
            logs_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.log_path = logs_dir / f"{ts}_{file_stem}.log"

        level = logging.DEBUG if os.environ.get("TWITCH_DEBUG") else logging.INFO
        fmt = logging.Formatter("%(levelname)s %(name)s: %(message)s")
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()
        logger.propagate = False
        if not no_file_logs:
            file_handler = logging.FileHandler(
                self.log_path, mode="w", encoding="utf-8"
            )
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(fmt)
        logger.addHandler(stream_handler)
        self.logger = logger
