"""
Pytest configuration and shared fixtures
"""
import os
import sys
from pathlib import Path
import pytest
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_vault():
    """Create a temporary Obsidian vault for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "test_vault"
        vault_path.mkdir()
        yield vault_path


@pytest.fixture
def sample_note_content():
    """Sample markdown note content"""
    return """---
title: Test Note
tags: [test, sample]
created: 2024-01-01
---

# Test Note

This is a test note with some content.

## Section 1
Content about CAR-T therapy and lymphoma treatment.

## Section 2
More content about medical treatments.
"""


@pytest.fixture
def sample_note_no_frontmatter():
    """Sample markdown without frontmatter"""
    return """# Test Note

This is a test note without frontmatter.
"""


@pytest.fixture
def sample_note_invalid_frontmatter():
    """Sample markdown with invalid frontmatter"""
    return """---
invalid yaml content
  badly: indented
---

# Test Note
"""


@pytest.fixture
def sample_moc_content():
    """Sample Map of Contents note"""
    return """---
title: Main MoC
type: moc
tags: [moc, index]
---

# Main MoC

## Related Notes
- [[Note 1]]
- [[Note 2]]
- [[Subfolder/Note 3]]
"""


@pytest.fixture
def mock_api_key(monkeypatch):
    """Mock ANTHROPIC_API_KEY for tests"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_api_key_12345")
    return "test_api_key_12345"


@pytest.fixture
def mock_vault_path(monkeypatch, temp_vault):
    """Mock OBSIDIAN_VAULT_PATH environment variable"""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))
    return temp_vault


@pytest.fixture
def sample_graph_data():
    """Sample knowledge graph data for testing"""
    return {
        'nodes': [
            {'id': 'CAR-T Therapy', 'type': 'treatment'},
            {'id': 'Lymphoma', 'type': 'condition'},
            {'id': 'Immunotherapy', 'type': 'treatment'},
        ],
        'edges': [
            {'source': 'CAR-T Therapy', 'target': 'Lymphoma', 'relationship': 'treats'},
            {'source': 'CAR-T Therapy', 'target': 'Immunotherapy', 'relationship': 'part_of'},
        ]
    }


@pytest.fixture
def sample_chunks():
    """Sample chunks for graph building"""
    return [
        {
            'text': 'CAR-T therapy is a treatment for lymphoma.',
            'metadata': {'filename': 'cart_therapy.md', 'source': 'test'}
        },
        {
            'text': 'Lymphoma is treated with various immunotherapy approaches.',
            'metadata': {'filename': 'lymphoma.md', 'source': 'test'}
        }
    ]


@pytest.fixture
def create_note_file(temp_vault):
    """Factory fixture to create note files in temp vault"""
    def _create_note(filename: str, content: str, subfolder: str = None):
        if subfolder:
            note_dir = temp_vault / subfolder
            note_dir.mkdir(parents=True, exist_ok=True)
            note_path = note_dir / filename
        else:
            note_path = temp_vault / filename

        note_path.write_text(content, encoding='utf-8')
        return note_path

    return _create_note


@pytest.fixture
def mock_chromadb_client(mocker):
    """Mock ChromaDB client"""
    mock_client = mocker.MagicMock()
    mock_collection = mocker.MagicMock()
    mock_client.get_collection.return_value = mock_collection
    mock_collection.query.return_value = {
        'documents': [['Sample content']],
        'metadatas': [[{'filename': 'test.md', 'filepath': '/vault/test.md'}]],
        'distances': [[0.5]]
    }
    return mock_client


@pytest.fixture
def mock_anthropic_client(mocker):
    """Mock Anthropic API client"""
    mock_client = mocker.MagicMock()
    mock_response = mocker.MagicMock()
    mock_response.content = [mocker.MagicMock(text='{"entities": [], "relationships": []}')]
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture(autouse=True)
def reset_env_vars(monkeypatch):
    """Reset environment variables before each test"""
    # Don't require API key for all tests
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def sample_tag_suggestions():
    """Sample tag suggestions data"""
    return [
        {
            'file': 'note1.md',
            'filename': 'note1.md',
            'existing_tags': ['old-tag'],
            'suggested_tags': ['medical', 'treatment', 'car-t'],
            'final_tags': ['old-tag', 'medical', 'treatment', 'car-t'],
            'suggested_backlink': 'Main MoC'
        },
        {
            'file': 'note2.md',
            'filename': 'note2.md',
            'existing_tags': [],
            'suggested_tags': ['tech', 'python'],
            'final_tags': ['tech', 'python'],
            'suggested_backlink': None
        }
    ]
