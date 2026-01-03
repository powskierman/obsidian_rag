# Obsidian RAG Test Suite

This directory contains comprehensive tests for the Obsidian RAG project.

## Quick Start

```bash
# Install dependencies
pip install -r ../requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov

# Run only fast tests
pytest -m "unit and not slow"
```

## Structure

```
tests/
├── README.md              # This file
├── conftest.py           # Shared fixtures
├── __init__.py           # Package marker
├── unit/                 # Unit tests (fast)
│   ├── test_frontmatter.py      # 15+ tests
│   ├── test_tag_generation.py   # 20+ tests
│   └── test_graph_builder.py    # 25+ tests
├── integration/          # Integration tests
│   └── test_mcp_server.py       # 30+ tests
└── fixtures/            # Test data (if needed)
```

## Test Categories

- **Unit Tests**: Fast, isolated tests (~90+ tests)
  - Frontmatter parsing
  - Tag generation logic
  - Graph builder core functions

- **Integration Tests**: Multi-component tests (~30+ tests)
  - MCP server endpoints
  - Full workflows

## Coverage

Current test coverage targets:

- **Overall**: 70%+
- **Core modules**: 80%+
  - `claude_graph_builder.py`
  - `Scripts/generate_tags.py`
  - `obsidian_rag_unified_mcp.py`

View coverage:
```bash
pytest --cov --cov-report=html
open htmlcov/index.html
```

## Running Specific Tests

```bash
# Single file
pytest unit/test_frontmatter.py

# Single class
pytest unit/test_tag_generation.py::TestContentTypeDetection

# Single test
pytest unit/test_frontmatter.py::TestFrontmatterParsing::test_parse_valid_frontmatter

# By marker
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
pytest -m "not slow"    # Skip slow tests
```

## Writing Tests

See the main [TESTING.md](../TESTING.md) for detailed instructions.

Quick example:

```python
import pytest

class TestMyFeature:
    @pytest.mark.unit
    def test_basic_case(self, temp_vault):
        """Test basic functionality"""
        # Use fixtures from conftest.py
        result = my_function(temp_vault)
        assert result is not None
```

## Available Fixtures

From `conftest.py`:

- `temp_vault` - Temporary vault directory
- `sample_note_content` - Sample markdown with frontmatter
- `mock_api_key` - Mocked API key
- `create_note_file` - Factory to create test notes
- `mock_chromadb_client` - Mocked ChromaDB
- `mock_anthropic_client` - Mocked Anthropic API

See `conftest.py` for complete list.

## Continuous Integration

Tests run automatically on:
- Push to main branch
- Pull requests
- Pre-commit hooks (if configured)

## Troubleshooting

**Import errors?**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."
```

**Slow tests?**
```bash
pytest -m "unit and not slow"
```

**Need debug output?**
```bash
pytest -vv -s
```

See [TESTING.md](../TESTING.md) for more troubleshooting.

## Contributing

When adding new features:

1. Write tests first (TDD)
2. Maintain coverage targets
3. Use appropriate markers
4. Add docstrings
5. Mock external dependencies

## Resources

- [Main Testing Guide](../TESTING.md)
- [Pytest Documentation](https://docs.pytest.org/)
- [Project README](../README.md)
