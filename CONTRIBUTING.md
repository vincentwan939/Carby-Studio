# Contributing to Carby Studio

Thank you for your interest in contributing to Carby Studio!

---

## How to Contribute

### Reporting Issues

1. Check existing issues to avoid duplicates
2. Use issue templates when available
3. Provide clear reproduction steps
4. Include environment details (OS, Python version, etc.)

### Suggesting Features

1. Open a discussion first for major features
2. Describe the use case and expected behavior
3. Consider implementation complexity
4. Be open to feedback and iteration

### Contributing Code

#### 1. Fork and Clone

```bash
git clone https://github.com/vincentwan939/Carby-Studio.git
cd Carby-Studio
```

#### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e ".[dev]"
```

#### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-new-command`
- `fix/handle-edge-case`
- `docs/update-api-reference`
- `test/add-missing-tests`

#### 4. Make Changes

- Follow the code style guidelines
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

#### 5. Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific category
python -m pytest tests/security/ -v
python -m pytest tests/reliability/ -v

# With coverage
python -m pytest tests/ --cov=carby_sprint --cov-report=html
```

#### 6. Submit Pull Request

1. Push your branch to your fork
2. Open a PR against the main repository
3. Fill out the PR template
4. Link related issues
5. Request review from maintainers

---

## Code Style Guidelines

### Python Style

We follow PEP 8 with these specifics:

#### Formatting

- **Line length:** 100 characters maximum
- **Indentation:** 4 spaces (no tabs)
- **Quotes:** Double quotes for strings
- **Imports:** Sorted alphabetically, grouped by stdlib/third-party/local

```python
# Good
from pathlib import Path
from typing import Dict, List, Optional

import click
from pydantic import BaseModel

from carby_sprint.validators import SprintModel

# Bad
import click
from typing import Dict
from carby_sprint.validators import SprintModel
from pathlib import Path
```

#### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Modules | `snake_case` | `gate_enforcer.py` |
| Classes | `PascalCase` | `GateEnforcer` |
| Functions | `snake_case` | `validate_token()` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEOUT` |
| Private | `_leading_underscore` | `_internal_helper()` |

#### Type Hints

Use type hints for all function signatures:

```python
def process_sprint(
    sprint_id: str,
    output_dir: str = ".carby-sprints"
) -> Dict[str, Any]:
    """Process a sprint and return results."""
    ...
```

#### Docstrings

Use Google-style docstrings:

```python
def validate_sprint(data: Dict[str, Any]) -> SprintModel:
    """
    Validate sprint data using Pydantic model.
    
    Args:
        data: Sprint data dictionary
        
    Returns:
        Validated SprintModel instance
        
    Raises:
        ValueError: If validation fails
    """
    ...
```

### Documentation Style

- Use Markdown for all documentation
- Include code examples where helpful
- Keep line length to 100 characters
- Use tables for structured data
- Include a table of contents for long docs

### Commit Messages

Follow conventional commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, semicolons, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Build process or auxiliary tool changes

Examples:
```
feat(gate): add design approval gate

fix(lock): handle stale lock edge case

docs(api): update PhaseLock documentation

test(security): add path traversal tests
```

---

## Testing Requirements

### Test Coverage

- Minimum 80% coverage for new code
- 100% coverage for critical paths
- All security features must have tests

### Test Organization

```
tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
├── security/          # Security tests
├── reliability/       # Reliability tests
└── conftest.py        # Shared fixtures
```

### Writing Tests

Use pytest with descriptive names:

```python
def test_sprint_repository_creates_sprint_with_valid_data():
    """Test that SprintRepository.create() succeeds with valid input."""
    repo = SprintRepository()
    data, paths = repo.create(
        sprint_id="test-001",
        project="test",
        goal="Test goal"
    )
    assert data["sprint_id"] == "test-001"
    assert paths.metadata.exists()
```

### Security Tests

Security tests are mandatory for:
- Path traversal prevention
- Token validation
- Gate enforcement
- Input sanitization

Example:
```python
def test_path_traversal_attempt_is_rejected():
    """Test that path traversal attempts raise ValueError."""
    with pytest.raises(ValueError):
        validate_sprint_id("../etc/passwd")
```

---

## Development Workflow

### Before Starting Work

1. Check open issues and PRs
2. Comment on issues you plan to work on
3. Ask questions if requirements are unclear

### During Development

1. Make small, focused commits
2. Write tests alongside code
3. Update documentation as you go
4. Run tests frequently

### Before Submitting PR

1. Run the full test suite
2. Check code style with `flake8` or `ruff`
3. Update CHANGELOG.md if needed
4. Ensure documentation is current
5. Rebase on latest main branch

### PR Review Process

1. All PRs require at least one review
2. Address review feedback promptly
3. Maintain a constructive tone
4. Squash commits if requested

---

## Project Structure

```
Carby-Studio/
├── agents/              # Agent prompt definitions
├── carby_sprint/        # Main Python package
│   ├── commands/        # CLI commands
│   ├── lib/             # Shared utilities
│   └── *.py             # Core modules
├── docs/                # Documentation
├── scripts/             # Shell scripts
├── team-tasks/          # Workflow engine
├── templates/           # Project templates
├── tests/               # Test suite
├── CHANGELOG.md         # Version history
├── CONTRIBUTING.md      # This file
├── LICENSE              # MIT License
├── README.md            # Main documentation
├── SKILL.md             # OpenClaw skill definition
└── pyproject.toml       # Package configuration
```

---

## Questions?

- Open an issue for bugs
- Start a discussion for questions
- Contact maintainers for sensitive matters

---

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions

---

*Thank you for contributing to Carby Studio!*
