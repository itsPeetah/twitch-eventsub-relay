from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.websockets.config import load_ws_config


def test_load_ws_config_ok(tmp_path: Path) -> None:
    path = tmp_path / "ws.json"
    path.write_text(
        json.dumps({"host": "0.0.0.0", "port": 9000}),
        encoding="utf-8",
    )
    cfg = load_ws_config(path)
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9000


@pytest.mark.parametrize(
    "raw",
    [
        {"host": "", "port": 8765},
        {"port": 8765},
        {"host": "127.0.0.1"},
        {"host": "127.0.0.1", "port": "nope"},
        {"host": "127.0.0.1", "port": 0},
        {"host": "127.0.0.1", "port": 65536},
    ],
)
def test_load_ws_config_invalid(tmp_path: Path, raw: dict) -> None:
    path = tmp_path / "ws.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_ws_config(path)
