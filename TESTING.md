# Testing Guide for Obsidian RAG

This guide covers how to run tests, write new tests, and understand the testing framework for the Obsidian RAG project.

## Table of Contents
- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Test Coverage](#test-coverage)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Install Test Dependencies

```bash
# Install all dependencies including test packages
pip install -r requirements.txt

# Or install test dependencies separately
pip install pytest pytest-asyncio pytest-cov pytest-mock pytest-timeout httpx
```

### 2. Run All Tests

```bash
# Run all tests with verbose output
pytest

# Run with coverage report
pytest --cov

# Run quickly (skip slow tests)
pytest -m "not slow"
```

### 3. Verify Installation

```bash
# Quick verification test
pytest tests/unit/test_frontmatter.py -v

# Should see output like:
# ✓ test_parse_valid_frontmatter PASSED
# ✓ test_parse_no_frontmatter PASSED
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_frontmatter.py  # Frontmatter parsing tests
│   ├── test_tag_generation.py # Tag generation logic tests
│   └── test_graph_builder.py  # Graph builder core functions
├── integration/             # Integration tests (slower)
│   └── test_mcp_server.py   # MCP server endpoint tests
└── fixtures/                # Test data and mock objects
```

### Test Categories

Tests are organized by markers:

- **`@pytest.mark.unit`** - Fast, isolated unit tests
- **`@pytest.mark.integration`** - Tests involving multiple components
- **`@pytest.mark.slow`** - Long-running tests
- **`@pytest.mark.requires_api`** - Tests requiring API keys
- **`@pytest.mark.requires_chromadb`** - Tests requiring ChromaDB

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_frontmatter.py

# Run specific test class
pytest tests/unit/test_tag_generation.py::TestContentTypeDetection

# Run specific test
pytest tests/unit/test_frontmatter.py::TestFrontmatterParsing::test_parse_valid_frontmatter
```

### Filter by Markers

```bash
# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run tests that don't require API keys
pytest -m "not requires_api"

# Combine markers
pytest -m "unit and not requires_api"
```

### Coverage Reports

```bash
# Generate terminal coverage report
pytest --cov --cov-report=term-missing

# Generate HTML coverage report
pytest --cov --cov-report=html
# Then open htmlcov/index.html

# Generate XML coverage report (for CI/CD)
pytest --cov --cov-report=xml
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest -n auto  # Use all CPU cores
pytest -n 4     # Use 4 workers
```

### Watch Mode

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw
ptw -- -m unit  # Watch only unit tests
```

## Writing Tests

### Basic Test Structure

```python
import pytest

class TestMyFeature:
    """Test suite for my feature"""

    @pytest.mark.unit
    def test_basic_functionality(self):
        """Test basic functionality"""
        result = my_function("input")
        assert result == "expected"

    @pytest.mark.unit
    def test_edge_case(self):
        """Test edge case handling"""
        with pytest.raises(ValueError):
            my_function(None)
```

### Using Fixtures

```python
import pytest

@pytest.mark.unit
def test_with_temp_vault(temp_vault):
    """Test using temporary vault fixture"""
    # temp_vault is a Path object to a temporary directory
    note_path = temp_vault / "test.md"
    note_path.write_text("# Test", encoding='utf-8')
    assert note_path.exists()

@pytest.mark.unit
def test_with_sample_content(sample_note_content):
    """Test using sample content fixture"""
    # sample_note_content contains markdown with frontmatter
    frontmatter, body = parse_frontmatter(sample_note_content)
    assert frontmatter is not None
```

### Available Fixtures

From `tests/conftest.py`:

- **`temp_vault`** - Temporary vault directory
- **`sample_note_content`** - Sample markdown with frontmatter
- **`sample_note_no_frontmatter`** - Markdown without frontmatter
- **`sample_moc_content`** - Sample Map of Contents note
- **`mock_api_key`** - Mocked API key
- **`mock_vault_path`** - Mocked vault path
- **`sample_graph_data`** - Sample knowledge graph data
- **`create_note_file`** - Factory to create notes in temp vault
- **`mock_chromadb_client`** - Mocked ChromaDB client
- **`mock_anthropic_client`** - Mocked Anthropic API client

### Testing Async Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function"""
    result = await my_async_function()
    assert result is not None
```

### Mocking External Dependencies

```python
from unittest.mock import patch, MagicMock

@pytest.mark.unit
@patch('requests.post')
def test_with_mocked_request(mock_post):
    """Test with mocked HTTP request"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'data': 'test'}
    mock_post.return_value = mock_response

    result = function_that_makes_request()
    assert result == {'data': 'test'}
```

### Testing Error Handling

```python
@pytest.mark.unit
def test_error_handling():
    """Test error handling"""
    with pytest.raises(ValueError, match="Invalid input"):
        my_function(invalid_input)

@pytest.mark.unit
def test_graceful_failure():
    """Test graceful failure"""
    result = my_function_with_fallback(bad_input)
    assert result is not None  # Should not crash
    assert 'error' in result
```

### Parametrized Tests

```python
@pytest.mark.unit
@pytest.mark.parametrize("input,expected", [
    ("recipe", "cooking"),
    ("medical", "medical"),
    ("python code", "tech"),
])
def test_content_detection(input, expected):
    """Test content type detection with various inputs"""
    result = detect_content_type("test.md", input)
    assert result == expected
```

## Test Coverage

### Current Coverage

Run this to see current coverage:

```bash
pytest --cov --cov-report=term-missing
```

### Coverage Goals

- **Overall**: Target 70%+ coverage
- **Core modules**: Target 80%+ coverage
  - `claude_graph_builder.py`
  - `Scripts/generate_tags.py`
  - `Scripts/apply_tags.py`
  - `obsidian_rag_unified_mcp.py`

### Viewing Coverage Reports

```bash
# Generate HTML report
pytest --cov --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage Exclusions

Lines excluded from coverage (configured in `pytest.ini`):

```python
# pragma: no cover
def __repr__():  # Excluded
    ...

if __name__ == '__main__':  # Excluded
    main()

if TYPE_CHECKING:  # Excluded
    ...
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, '3.10', '3.11', '3.12']

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -r requirements.txt

    - name: Run tests
      run: |
        pytest -v --cov --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run tests before commit

echo "Running tests..."
pytest -m "unit and not slow" --quiet

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi

echo "All tests passed!"
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Environment Variables for Testing

### Required

None - tests use mocked dependencies by default

### Optional

```bash
# For tests that require actual API access
export ANTHROPIC_API_KEY="your_api_key"

# For integration tests
export OBSIDIAN_VAULT_PATH="/path/to/test/vault"
export CHROMA_DB_PATH="/path/to/test/chroma_db"
```

### Using .env.test

Create `.env.test`:

```bash
# Test environment variables
ANTHROPIC_API_KEY=test_key_for_mocking
OBSIDIAN_VAULT_PATH=/tmp/test_vault
```

Load before tests:

```bash
# Install python-dotenv
pip install python-dotenv

# Run tests with .env.test
pytest --envfile=.env.test
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

```
ImportError: No module named 'claude_graph_builder'
```

**Solution**: Add project root to PYTHONPATH:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

#### 2. Fixture Not Found

```
fixture 'temp_vault' not found
```

**Solution**: Ensure `conftest.py` exists in `tests/` directory

#### 3. Async Test Warnings

```
RuntimeWarning: coroutine was never awaited
```

**Solution**: Add `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_async_function():
    ...
```

#### 4. ChromaDB Errors

```
RuntimeError: Your system has an unsupported version of sqlite3
```

**Solution**: Skip ChromaDB tests:

```bash
pytest -m "not requires_chromadb"
```

#### 5. Slow Tests

```
Tests taking too long
```

**Solution**: Run only unit tests:

```bash
pytest -m "unit and not slow"
```

### Debug Mode

```bash
# Run with debugging
pytest --pdb  # Drop into debugger on failure

# Print output even for passing tests
pytest -s

# Stop at first failure
pytest -x

# Verbose mode with all details
pytest -vv
```

### Test Collection Issues

```bash
# Show which tests would be run
pytest --collect-only

# Show test tree
pytest --collect-only -q
```

## Best Practices

### 1. Test Naming

```python
# Good
def test_parse_valid_frontmatter():
    """Test parsing valid frontmatter"""

# Bad
def test1():
    """Test"""
```

### 2. One Assertion Focus

```python
# Good - focused test
def test_content_type_is_medical():
    result = detect_content_type("note.md", "patient treatment")
    assert result == 'medical'

# Avoid - testing multiple things
def test_everything():
    assert detect_content_type(...) == 'medical'
    assert analyze_tags(...) == ['tag1']
    assert parse_frontmatter(...)[0] is not None
```

### 3. Use Descriptive Assertions

```python
# Good
assert result['suggested_tags'] == ['medical', 'treatment'], \
    f"Expected medical tags, got {result['suggested_tags']}"

# OK but less helpful
assert result['suggested_tags'] == ['medical', 'treatment']
```

### 4. Test Edge Cases

```python
def test_empty_input():
    result = my_function("")
    assert result is not None

def test_null_input():
    with pytest.raises(TypeError):
        my_function(None)

def test_very_large_input():
    result = my_function("x" * 10000)
    assert result is not None
```

### 5. Keep Tests Independent

```python
# Good - independent
def test_feature_a():
    result = function_a()
    assert result is not None

def test_feature_b():
    result = function_b()
    assert result is not None

# Bad - dependent
test_data = None

def test_setup():
    global test_data
    test_data = setup()

def test_using_data():
    # Depends on test_setup running first
    assert test_data is not None
```

## Contributing Tests

When contributing new features:

1. **Add tests first** (TDD approach)
2. **Maintain coverage** - don't reduce coverage %
3. **Test edge cases** - null, empty, invalid inputs
4. **Use appropriate markers** - unit/integration/slow
5. **Document complex tests** - add docstrings
6. **Mock external dependencies** - API calls, file I/O

### Test Checklist

- [ ] Tests pass locally
- [ ] Coverage maintained or improved
- [ ] Edge cases covered
- [ ] Async functions use `@pytest.mark.asyncio`
- [ ] External APIs mocked
- [ ] Docstrings added
- [ ] Appropriate markers used

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py](https://coverage.readthedocs.io/)

## Getting Help

### Run Test Health Check

```bash
# Verify test setup
pytest --version
pytest --collect-only | head -20
pytest -m unit --collect-only

# Run sample test
pytest tests/unit/test_frontmatter.py::TestFrontmatterParsing::test_parse_valid_frontmatter -v
```

### Report Issues

When reporting test issues, include:

1. Pytest version: `pytest --version`
2. Python version: `python --version`
3. Full error message
4. Command used
5. Environment (OS, etc.)

---

**Happy Testing! 🧪**

For questions or issues, please open a GitHub issue or check existing documentation.
