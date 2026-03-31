.PHONY: help install dev test build publish publish-test clean

PYTHON  := python
PACKAGE := docx_jinja2_validator

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install       Install package (editable)"
	@echo "  dev           Install build/publish tools (build, twine)"
	@echo "  test          Run smoke tests"
	@echo "  build         Build wheel + sdist into dist/"
	@echo "  publish       Upload to PyPI (requires PYPI_TOKEN or ~/.pypirc)"
	@echo "  publish-test  Upload to TestPyPI"
	@echo "  clean         Remove dist/, build/, __pycache__, *.egg-info"

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install build twine

# ── Test ──────────────────────────────────────────────────────────────────────

test:
	@echo ">>> Import check"
	$(PYTHON) -c "from $(PACKAGE).validator import validate_one; print('  OK')"
	@echo ">>> Version flag"
	$(PYTHON) -m $(PACKAGE) --version
	@echo ">>> Help flag"
	$(PYTHON) -m $(PACKAGE) --help
	@echo ">>> All checks passed"

# ── Build ─────────────────────────────────────────────────────────────────────

build: clean
	$(PYTHON) -m build
	@echo ""
	@ls -lh dist/

# ── Publish ───────────────────────────────────────────────────────────────────

publish: build
	$(PYTHON) -m twine upload dist/* \
		$(if $(PYPI_TOKEN),--username __token__ --password $(PYPI_TOKEN),)

publish-test: build
	$(PYTHON) -m twine upload --repository testpypi dist/* \
		$(if $(PYPI_TOKEN),--username __token__ --password $(PYPI_TOKEN),)

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	rm -rf dist/ build/
	find . -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -name "__pycache__"  -exec rm -rf {} + 2>/dev/null || true
