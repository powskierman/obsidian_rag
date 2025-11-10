"""
Tests for frontmatter parsing across multiple modules
"""
import pytest
import sys
from pathlib import Path

# Import the parse_frontmatter functions from different modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "Scripts"))
from generate_tags import parse_frontmatter as parse_frontmatter_tags
from apply_tags import parse_frontmatter as parse_frontmatter_apply


class TestFrontmatterParsing:
    """Test frontmatter parsing functionality"""

    @pytest.mark.unit
    def test_parse_valid_frontmatter(self, sample_note_content):
        """Test parsing valid frontmatter"""
        frontmatter, body = parse_frontmatter_tags(sample_note_content)

        assert frontmatter is not None
        assert isinstance(frontmatter, dict)
        assert frontmatter['title'] == 'Test Note'
        assert 'test' in frontmatter['tags']
        assert 'sample' in frontmatter['tags']
        assert '# Test Note' in body

    @pytest.mark.unit
    def test_parse_no_frontmatter(self, sample_note_no_frontmatter):
        """Test parsing note without frontmatter"""
        frontmatter, body = parse_frontmatter_tags(sample_note_no_frontmatter)

        assert frontmatter is None
        assert body == sample_note_no_frontmatter

    @pytest.mark.unit
    def test_parse_invalid_frontmatter(self, sample_note_invalid_frontmatter):
        """Test parsing invalid YAML frontmatter"""
        frontmatter, body = parse_frontmatter_tags(sample_note_invalid_frontmatter)

        # Should return None for invalid frontmatter
        assert frontmatter is None
        assert body == sample_note_invalid_frontmatter

    @pytest.mark.unit
    def test_parse_empty_frontmatter(self):
        """Test parsing empty frontmatter"""
        content = """---
---

# Note
"""
        frontmatter, body = parse_frontmatter_tags(content)

        assert frontmatter is not None
        assert isinstance(frontmatter, dict)
        assert len(frontmatter) == 0

    @pytest.mark.unit
    def test_parse_frontmatter_with_multiline_values(self):
        """Test parsing frontmatter with multiline values"""
        content = """---
title: Test Note
description: |
  This is a multiline
  description
tags: [test]
---

# Content
"""
        frontmatter, body = parse_frontmatter_tags(content)

        assert frontmatter is not None
        assert 'This is a multiline' in frontmatter['description']

    @pytest.mark.unit
    def test_parse_frontmatter_preserves_body(self, sample_note_content):
        """Test that parsing preserves body content"""
        frontmatter, body = parse_frontmatter_tags(sample_note_content)

        assert '# Test Note' in body
        assert 'CAR-T therapy' in body
        assert 'Section 1' in body

    @pytest.mark.unit
    def test_parse_frontmatter_non_dict_yaml(self):
        """Test parsing frontmatter that's valid YAML but not a dict"""
        content = """---
just a string
---

# Note
"""
        frontmatter, body = parse_frontmatter_tags(content)

        # Should return None when YAML is not a dict
        assert frontmatter is None
        assert body == content

    @pytest.mark.unit
    def test_consistency_across_modules(self, sample_note_content):
        """Test that both parse_frontmatter implementations work the same"""
        fm1, body1 = parse_frontmatter_tags(sample_note_content)
        fm2, body2 = parse_frontmatter_apply(sample_note_content)

        assert fm1 == fm2
        assert body1 == body2

    @pytest.mark.unit
    def test_parse_frontmatter_with_special_chars(self):
        """Test parsing frontmatter with special characters"""
        content = """---
title: "Note with \"quotes\""
tags: ['tag-with-dash', 'tag_with_underscore']
emoji: 🔥
---

# Content
"""
        frontmatter, body = parse_frontmatter_tags(content)

        assert frontmatter is not None
        assert 'quotes' in frontmatter['title']
        assert 'tag-with-dash' in frontmatter['tags']

    @pytest.mark.unit
    def test_parse_frontmatter_with_null_values(self):
        """Test parsing frontmatter with null values"""
        content = """---
title: Test
author: null
tags: []
---

# Content
"""
        frontmatter, body = parse_frontmatter_tags(content)

        assert frontmatter is not None
        assert frontmatter['title'] == 'Test'
        assert frontmatter['author'] is None
        assert frontmatter['tags'] == []


class TestFrontmatterEdgeCases:
    """Test edge cases in frontmatter parsing"""

    @pytest.mark.unit
    def test_frontmatter_with_code_blocks_in_body(self):
        """Test that code blocks in body don't interfere with parsing"""
        content = """---
title: Test
---

# Note

```yaml
---
fake: frontmatter
---
```
"""
        frontmatter, body = parse_frontmatter_tags(content)

        assert frontmatter is not None
        assert frontmatter['title'] == 'Test'
        assert 'fake: frontmatter' in body

    @pytest.mark.unit
    def test_frontmatter_with_windows_line_endings(self):
        """Test parsing with Windows line endings"""
        content = "---\r\ntitle: Test\r\ntags: [test]\r\n---\r\n\r\n# Note\r\n"
        frontmatter, body = parse_frontmatter_tags(content)

        assert frontmatter is not None
        assert frontmatter['title'] == 'Test'

    @pytest.mark.unit
    def test_empty_string(self):
        """Test parsing empty string"""
        frontmatter, body = parse_frontmatter_tags("")

        assert frontmatter is None
        assert body == ""

    @pytest.mark.unit
    def test_only_frontmatter_markers(self):
        """Test content with only frontmatter markers"""
        content = "---\n---\n"
        frontmatter, body = parse_frontmatter_tags(content)

        assert frontmatter is not None
        assert isinstance(frontmatter, dict)

    @pytest.mark.unit
    def test_frontmatter_with_nested_structures(self):
        """Test parsing frontmatter with nested YAML structures"""
        content = """---
title: Test
metadata:
  author: John
  date: 2024-01-01
  tags:
    - nested
    - tags
---

# Note
"""
        frontmatter, body = parse_frontmatter_tags(content)

        assert frontmatter is not None
        assert frontmatter['metadata']['author'] == 'John'
        assert 'nested' in frontmatter['metadata']['tags']
