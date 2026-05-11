from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.amqp.config import AmqpConfig, load_amqp_config


def test_load_amqp_config_defaults(tmp_path: Path) -> None:
    p = tmp_path / "amqp.json"
    p.write_text(
        json.dumps({"url": "amqp://guest:guest@localhost:5672/", "exchange": "x"}),
        encoding="utf-8",
    )
    cfg = load_amqp_config(p)
    assert cfg.reconnect_delay == 1.0
    assert cfg.reconnect_backoff == 2.0
    assert cfg.reconnect_max_retries is None
    assert cfg.reconnect_max_delay == 60.0


def test_load_amqp_config_retry_options(tmp_path: Path) -> None:
    p = tmp_path / "amqp.json"
    p.write_text(
        json.dumps(
            {
                "url": "amqp://h/",
                "exchange": "e",
                "reconnect_delay": 0.5,
                "reconnect_backoff": 1.5,
                "reconnect_max_retries": 10,
                "reconnect_max_delay": 30.0,
            }
        ),
        encoding="utf-8",
    )
    cfg = load_amqp_config(p)
    assert cfg == AmqpConfig(
        url="amqp://h/",
        exchange="e",
        reconnect_delay=0.5,
        reconnect_backoff=1.5,
        reconnect_max_retries=10,
        reconnect_max_delay=30.0,
    )


def test_load_amqp_config_max_retries_null(tmp_path: Path) -> None:
    p = tmp_path / "amqp.json"
    p.write_text(
        json.dumps(
            {
                "url": "amqp://h/",
                "exchange": "e",
                "reconnect_max_retries": None,
            }
        ),
        encoding="utf-8",
    )
    cfg = load_amqp_config(p)
    assert cfg.reconnect_max_retries is None


def test_load_amqp_config_rejects_bad_backoff(tmp_path: Path) -> None:
    p = tmp_path / "amqp.json"
    p.write_text(
        json.dumps(
            {"url": "amqp://h/", "exchange": "e", "reconnect_backoff": 0.5}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reconnect_backoff"):
        load_amqp_config(p)


def test_load_amqp_config_rejects_max_delay_below_delay(tmp_path: Path) -> None:
    p = tmp_path / "amqp.json"
    p.write_text(
        json.dumps(
            {
                "url": "amqp://h/",
                "exchange": "e",
                "reconnect_delay": 5.0,
                "reconnect_max_delay": 2.0,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reconnect_max_delay"):
        load_amqp_config(p)
