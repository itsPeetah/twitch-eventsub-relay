from __future__ import annotations

import logging

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


def test_app_logger_create_returns_configured_logger(tmp_path_factory) -> None:
    proj = tmp_path_factory.mktemp("proj")
    logger = AppLogger.create(proj, name="via_create")
    assert logger.name == "via_create"
    assert len(logger.handlers) == 2


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
