.PHONY: build publish clean install dev test

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

# Run tests
test:
	pytest

# Run tests with coverage
coverage:
	pytest --cov=medusa --cov-report=term-missing
