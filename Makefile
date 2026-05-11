PYTHON ?= python3
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
LOGS := logs

.DEFAULT_GOAL := help

.PHONY: help venv install install-dev setup test run clean clean-logs

help:
	@echo "Targets:"
	@echo "  venv         Create $(VENV) if missing"
	@echo "  install      Install runtime deps (requirements.txt)"
	@echo "  install-dev  Install runtime + dev deps (requirements-dev.txt)"
	@echo "  setup        Alias for install-dev"
	@echo "  test         Run pytest (ensures install-dev first)"
	@echo "  run          main.py --use-rabbitmq --use-websockets (needs install once)"
	@echo "  clean        Remove $(VENV)"
	@echo "  clean-logs   Remove $(LOGS)/ (runtime log files)"

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

run: install
	$(PY) main.py --use-rabbitmq --use-websockets

test: install-dev
	$(PY) -m pytest tests/

clean:
	rm -rf $(VENV)

clean-logs:
	rm -rf $(LOGS)
