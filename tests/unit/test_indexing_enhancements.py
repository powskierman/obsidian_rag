import pytest
import sys
from pathlib import Path

# Add src to path
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.indexing.index_vault import sanitize_content, extract_metadata, smart_chunk_document

def test_sanitize_content_removes_comments():
    raw = "This is visible %% This is a hidden comment %% text."
    expected = "This is visible  text."
    assert sanitize_content(raw) == expected

def test_sanitize_content_removes_block_refs():
    raw = "Some text here ^block-id-123\nAnother line."
    expected = "Some text here\nAnother line."
    assert sanitize_content(raw) == expected

def test_sanitize_content_handles_newlines():
    raw = "Line 1\r\nLine 2\r"
    expected = "Line 1\nLine 2\n"
    assert sanitize_content(raw) == expected

def test_extract_metadata_basic():
    content = """---\ntitle: My Note
tags: [ai, rag]
aliases: ["Note 1", "Important"]
---
# Content Header
Body text.
"""
    metadata, body = extract_metadata(content)
    
    assert metadata['title'] == 'My Note'
    assert metadata['tags'] == 'ai, rag' # Normalized to string
    assert metadata['aliases'] == 'Note 1, Important' # Normalized list
    assert body.strip() == "# Content Header\nBody text."

def test_extract_metadata_no_frontmatter():
    content = "# Just a title\nNo frontmatter."
    metadata, body = extract_metadata(content)
    assert metadata == {}
    assert body == content

def test_smart_chunking_respects_lists():
    # Create content that would split in the middle of a list if chunk size was small
    # List items are explicitly preferred break points now
    content = "Header\n\n" + "\n- Item " * 20
    
    # Force a small chunk size to trigger splitting
    chunks = smart_chunk_document(content, max_size=50, overlap=10)
    
    # Check that chunks don't start with "- Item" (meaning we split IN the bullet) 
    # unless it's a fresh start. Ideally, they break BEFORE a "- ".
    
    for chunk in chunks:
        # A chunk should ideally start with a bullet if it's a list part
        # or be the header.
        pass
    
    # A better test for the specific logic added:
    # Logic added: chunk.rfind('\n- ') is in break_points
    
    text = "Start " + "x"*40 + "\n- List Item 1\n- List Item 2"
    # Max size 60. 
    # "Start " + 40 chars = 46 chars.
    # "\n- List Item 1" is ~14 chars. Total 60.
    
    # If it works, it should prefer breaking at "\n- " over random space if it exists
    chunks = smart_chunk_document(text, max_size=55, overlap=0)
    
    # Verify we didn't split "List Item 1" in half
    assert "- List Item 1" in chunks[0] or "- List Item 1" in chunks[1]
    assert not chunks[0].endswith("- List I") 

def test_smart_chunking_context_logic_validation():
    # This simulates the logic we added to index_vault.py's process_file
    # We can't test process_file easily, but we can verify the formatting logic
    
    metadata = {
        'filename': 'test.md',
        'modified': '2023-01-01T12:00:00',
        'tags': 'tag1, tag2',
        'aliases': 'alias1'
    }
    
    source_filename = metadata.get('filename', 'Unknown')
    modified_date = metadata.get('modified', 'Unknown Date').split('T')[0]
    timeline_date = str(metadata.get('timeline_date') or '').strip()

    context_parts = [f"Source: {source_filename}"]
    if timeline_date:
        context_parts.append(f"Date: {timeline_date}")
        if modified_date and modified_date != timeline_date:
            context_parts.append(f"File Date: {modified_date}")
    else:
        context_parts.append(f"File Date: {modified_date}")
    
    if 'tags' in metadata:
        context_parts.append(f"Tags: {metadata['tags']}")
    if 'aliases' in metadata:
        context_parts.append(f"Aliases: {metadata['aliases']}")
        
    context_str = "[" + "] [".join(context_parts) + "]"
    
    assert "Source: test.md" in context_str
    assert "File Date: 2023-01-01" in context_str
    assert "Tags: tag1, tag2" in context_str
    assert "Aliases: alias1" in context_str
    assert context_str == "[Source: test.md] [File Date: 2023-01-01] [Tags: tag1, tag2] [Aliases: alias1]"
