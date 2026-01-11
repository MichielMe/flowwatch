# Contributing to FlowWatch

Thank you for your interest in contributing to FlowWatch! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Clone and Install

```bash
git clone https://github.com/MichielMe/flowwatch.git
cd flowwatch

# Install all dependencies including dev and dashboard extras
uv sync --all-extras
```

### Verify Installation

```bash
# Run tests
uv run pytest

# Run linter
uv run ruff check src/

# Run type checker
uv run mypy src/
```

## Code Style

FlowWatch uses strict linting and type checking to maintain code quality.

### Ruff

We use [Ruff](https://github.com/astral-sh/ruff) for linting with a comprehensive rule set including:

- **E/F**: pycodestyle and Pyflakes
- **I**: isort (import sorting)
- **B**: flake8-bugbear
- **UP**: pyupgrade
- **N**: pep8-naming
- **S**: flake8-bandit (security)
- **PL**: Pylint

Run the linter:

```bash
uv run ruff check src/
uv run ruff check src/ --fix  # Auto-fix issues
```

### MyPy

We use [MyPy](https://mypy.readthedocs.io/) for static type checking with strict settings:

- `disallow_untyped_defs = true`
- `warn_return_any = true`
- `warn_unused_ignores = true`

All functions must have type annotations:

```python
# Good
def process_file(path: Path, pattern: str | None = None) -> bool:
    ...

# Bad - will fail type checking
def process_file(path, pattern=None):
    ...
```

Run type checking:

```bash
uv run mypy src/
```

### Formatting

Ruff also handles formatting. Line length is set to 88 characters (Black-compatible):

```bash
uv run ruff format src/
```

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=flowwatch --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_app.py -v

# Run specific test
uv run pytest tests/test_app.py::TestFileEvent::test_is_created -v
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use pytest fixtures for common setup
- Aim for high coverage on new code

Example test structure:

```python
import pytest
from flowwatch import FileEvent, FlowWatchApp


class TestMyFeature:
    """Tests for my new feature."""

    def test_basic_functionality(self) -> None:
        """Test the happy path."""
        ...

    def test_edge_case(self) -> None:
        """Test edge case behavior."""
        ...

    def test_error_handling(self) -> None:
        """Test that errors are handled correctly."""
        with pytest.raises(ValueError, match="expected error"):
            ...
```

### Test Coverage

We aim for **85%+ test coverage**. Check coverage with:

```bash
uv run pytest --cov=flowwatch --cov-report=html
open htmlcov/index.html  # View detailed report
```

## Pull Request Process

### Before Submitting

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes** with clear, focused commits

3. **Run all checks**:
   ```bash
   uv run ruff check src/
   uv run mypy src/
   uv run pytest
   ```

4. **Ensure tests pass** and coverage doesn't decrease significantly

### Submitting

1. Push your branch to GitHub
2. Open a Pull Request against `main`
3. Fill out the PR template with:
   - Description of changes
   - Related issue (if any)
   - Testing performed
4. Wait for CI checks to pass
5. Address any review feedback

### Commit Messages

Write clear, descriptive commit messages:

```
feat: add JSON logging option for production environments

- Add JsonFormatter class for structured logging
- Add --json-logs CLI flag
- Add json_logs parameter to FlowWatchApp
```

Use conventional commit prefixes:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `test:` Adding/updating tests
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## Project Structure

```
flowwatch/
├── src/flowwatch/
│   ├── __init__.py           # Package exports
│   ├── app.py                # Core FlowWatchApp and FileEvent
│   ├── cli.py                # Typer CLI
│   ├── dashboard.py          # Standalone web dashboard (optional)
│   ├── fastapi_integration.py # FastAPI router integration (optional)
│   ├── decorators.py         # @on_created, @on_modified, etc.
│   └── static/               # Dashboard HTML/CSS
├── tests/
│   ├── conftest.py      # Shared fixtures
│   ├── test_app.py
│   ├── test_cli.py
│   ├── test_dashboard.py
│   └── test_decorators.py
├── docs/
│   └── images/          # Screenshots for README
├── pyproject.toml       # Project config
└── README.md
```

## Adding New Features

### Core Features

For changes to the core watching functionality (`app.py`, `decorators.py`):

1. Update the implementation
2. Add comprehensive tests
3. Update docstrings
4. Update README if it's a user-facing change

### Dashboard Features

For dashboard changes (`dashboard.py`, `static/`):

1. Dashboard is an **optional dependency** — code should handle missing deps gracefully
2. Test with `httpx` and Starlette's `TestClient`
3. Update the dashboard HTML if adding new UI features

### CLI Features

For CLI changes (`cli.py`):

1. Use Typer's `Option` and `Argument` with help text
2. Test using `typer.testing.CliRunner`
3. Update README CLI documentation

## Getting Help

- **Questions?** Open a [GitHub Discussion](https://github.com/MichielMe/flowwatch/discussions)
- **Found a bug?** Open a [GitHub Issue](https://github.com/MichielMe/flowwatch/issues)
- **Security issue?** Email the maintainer directly (see pyproject.toml)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
