import pytest
from src.indexing.frontmatter import extract_frontmatter, _extract_frontmatter_fields, _parse_frontmatter_value

def test_parse_frontmatter_value_list():
    assert _parse_frontmatter_value("[a, b]") == ["a", "b"]
    assert _parse_frontmatter_value("simple") == ["simple"]
    assert _parse_frontmatter_value("['quoted', \"double\"]") == ["quoted", "double"]

def test_extract_frontmatter_standard_yaml():
    content = """---
title: Test Note
tags: [tag1, tag2]
aliases:
  - alias1
  - alias2
---
# Body
Content here.
"""
    meta, body = extract_frontmatter(content)
    assert meta["title"] == "Test Note"
    assert "tag1" in meta["tags"]
    assert "tag2" in meta["tags"]
    assert "alias1" in meta["aliases"]
    assert "alias2" in meta["aliases"]
    assert body.strip() == "# Body\nContent here."

def test_extract_frontmatter_flow_tags():
    content = """---
tags: [tagA, tagB]
---
Body
"""
    meta, body = extract_frontmatter(content)
    assert "tagA" in meta["tags"]
    assert "tagB" in meta["tags"]

def test_extract_frontmatter_robustness():
    # Malformed YAML that PyYAML might choke on, but our regex/logic should handle key fields
    content = """---
tags:
  - valid_tag
  - "quoted_tag"
random_broken_key: [unclosed_list
aliases: [alias_a]
---
Body
"""
    meta, body = extract_frontmatter(content)
    assert "valid_tag" in meta["tags"]
    assert "quoted_tag" in meta["tags"]
    assert "alias_a" in meta["aliases"]
