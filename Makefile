.PHONY: build publish clean install dev test lint

# Build the package
build: clean
	pip install build
	python -m build

# Upload to PyPI
publish: build
	pip install twine
	twine upload dist/*

# Upload to TestPyPI (for testing)
publish-test: build
	pip install twine
	twine upload --repository testpypi dist/*

# Clean build artifacts
clean:
	rm -rf dist/ build/ *.egg-info medusa.egg-info/

# Install locally in editable mode
install:
	pip install -e .

# Install with dev dependencies
dev:
	pip install -e ".[dev]"

# Run tests with coverage (100% minimum)
test:
	pytest --cov=medusa --cov-report=term-missing --cov-fail-under=100

# Run linter and fix issues
lint:
	ruff check --fix .
	ruff format .
