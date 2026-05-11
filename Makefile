PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.DEFAULT_GOAL := help

.PHONY: help venv install install-dev setup test clean

help:
	@echo "Targets:"
	@echo "  venv         Create $(VENV) if missing"
	@echo "  install      Install runtime deps (requirements.txt)"
	@echo "  install-dev  Install runtime + dev deps (requirements-dev.txt)"
	@echo "  setup        Alias for install-dev"
	@echo "  test         Run pytest (ensures install-dev first)"
	@echo "  clean        Remove $(VENV)"

venv: $(PY)

$(PY):
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)

install: $(PY)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: $(PY)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

setup: install-dev

test: install-dev
	$(PY) -m pytest tests/

clean:
	rm -rf $(VENV)
