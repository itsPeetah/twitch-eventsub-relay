from __future__ import annotations

import logging

import pytest

from src.logger import AppLogger


def test_app_logger_log_path_layout(tmp_path_factory) -> None:
    root = tmp_path_factory.mktemp("proj")
    cfg = AppLogger(root, name="unit_test_stem")
    assert cfg.log_path.parent == root / "logs"
    assert cfg.log_path.suffix == ".log"
    assert cfg.log_path.name.endswith("_unit_test_stem.log")
    assert cfg.log_path.parent.is_dir()


def test_app_logger_stem_override(tmp_path_factory) -> None:
    root = tmp_path_factory.mktemp("proj")
    root_logger = logging.getLogger()
    before_handlers = len(root_logger.handlers)

    cfg = AppLogger(root, name="wrap_test_logger", stem="wrap_stem")
    assert cfg.log_path.parent == root / "logs"
    assert cfg.log_path.name.endswith("_wrap_stem.log")
    assert cfg.logger.name == "wrap_test_logger"
    assert len(root_logger.handlers) == before_handlers
    cfg.logger.info("x")
    assert cfg.log_path.read_text(encoding="utf-8").strip().endswith("x")


def test_app_logger_no_logs_skips_file(monkeypatch, tmp_path_factory) -> None:
    monkeypatch.setenv("NO_LOGS", "1")
    proj = tmp_path_factory.mktemp("proj")
    cfg = AppLogger.create(proj, name="no_file_logs")
    assert len(cfg.logger.handlers) == 1
    assert isinstance(cfg.logger.handlers[0], logging.StreamHandler)
    assert not (proj / "logs").exists()
    cfg.logger.info("x")


def test_app_logger_create_returns_facade(tmp_path_factory) -> None:
    proj = tmp_path_factory.mktemp("proj")
    cfg = AppLogger.create(proj, name="via_create")
    assert cfg.logger.name == "via_create"
    assert len(cfg.logger.handlers) == 2


def test_app_logger_sub_shares_output_distinct_names(tmp_path_factory) -> None:
    proj = tmp_path_factory.mktemp("proj")
    cfg = AppLogger.create(proj, name="base_app")
    child = cfg.sub("websockets")
    assert child.name == "base_app.websockets"
    assert child.propagate is True
    assert len(child.handlers) == 0

    cfg.logger.info("from_base")
    child.info("from_ws")

    text = cfg.log_path.read_text(encoding="utf-8")
    assert "base_app:" in text
    assert "base_app.websockets:" in text


def test_app_logger_sub_rejects_empty_suffix(tmp_path_factory) -> None:
    cfg = AppLogger.create(tmp_path_factory.mktemp("proj"), name="x")
    with pytest.raises(ValueError):
        cfg.sub("")


def test_app_logger_does_not_mutate_root(tmp_path_factory) -> None:
    root_logger = logging.getLogger()
    before_handlers = len(root_logger.handlers)

    proj = tmp_path_factory.mktemp("proj")
    cfg = AppLogger(proj, name="mlmr_test_logger_xyz")

    assert len(root_logger.handlers) == before_handlers
    assert cfg.logger.name == "mlmr_test_logger_xyz"
    assert cfg.logger.propagate is False
    assert len(cfg.logger.handlers) == 2
    cfg.logger.info("hello")
    assert cfg.log_path.read_text(encoding="utf-8").strip().endswith("hello")
