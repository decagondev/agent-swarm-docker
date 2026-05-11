.PHONY: install test test-demo test-all lint format clean image help

# Python interpreter — override with `make PY=python3.12 test`.
PY ?= python

help:
	@echo "Targets:"
	@echo "  install     Editable install + dev tooling + runtime deps."
	@echo "  test        Unit tests (no Docker required)."
	@echo "  test-demo   Integration tests against a real Docker Swarm."
	@echo "  test-all    test + test-demo."
	@echo "  lint        ruff check ."
	@echo "  format      ruff check --fix + ruff format."
	@echo "  image       Build agent-swarm:latest from docker/Dockerfile."
	@echo "  clean       Remove caches and the smoke venv."

install:
	$(PY) -m pip install -e ".[dev]"
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest tests/unit -v

test-demo:
	DOCKER_SWARM_TESTS=1 $(PY) -m pytest tests/integration -v

test-all: test test-demo

lint:
	$(PY) -m ruff check .

format:
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

image:
	docker build -f docker/Dockerfile -t agent-swarm:latest .

clean:
	rm -rf .venv-smoke .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
