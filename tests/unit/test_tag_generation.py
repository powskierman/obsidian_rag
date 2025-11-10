"""
Tests for tag generation logic
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "Scripts"))
from generate_tags import (
    detect_content_type,
    analyze_content_for_tags,
    find_backlink_moc,
    generate_tags_for_note,
)


class TestContentTypeDetection:
    """Test content type detection"""

    @pytest.mark.unit
    def test_detect_recipe_type(self):
        """Test detecting recipe content"""
        content = """
# Chicken Soup Recipe

Ingredients:
- Chicken
- Water
- Salt

Cook time: 30 minutes
Servings: 4
"""
        content_type = detect_content_type("recipe.md", content)
        assert content_type == 'recipe'

    @pytest.mark.unit
    def test_detect_medical_type(self):
        """Test detecting medical content"""
        content = """
# CAR-T Therapy

Treatment for lymphoma using immunotherapy.
Patient outcomes and diagnosis information.
"""
        content_type = detect_content_type("medical_note.md", content)
        assert content_type == 'medical'

    @pytest.mark.unit
    def test_detect_tech_type(self):
        """Test detecting technical content"""
        content = """
# Python API Documentation

```python
def function():
    import requests
    api.get()
```
"""
        content_type = detect_content_type("api.md", content)
        assert content_type == 'tech'

    @pytest.mark.unit
    def test_detect_hardware_type(self):
        """Test detecting hardware content"""
        content = """
# ESP32 Setup

Configure GPIO pins for sensors.
Arduino compatible microcontroller.
"""
        content_type = detect_content_type("esp32.md", content)
        assert content_type == 'hardware'

    @pytest.mark.unit
    def test_detect_ai_type(self):
        """Test detecting AI/ML content"""
        content = """
# RAG System

Using embeddings and vector search with Claude.
LLM-based retrieval augmented generation.
"""
        content_type = detect_content_type("rag.md", content)
        assert content_type == 'ai'

    @pytest.mark.unit
    def test_detect_general_type(self):
        """Test detecting general content"""
        content = """
# General Notes

Just some general thoughts and ideas.
"""
        content_type = detect_content_type("notes.md", content)
        assert content_type == 'general'


class TestTagAnalysis:
    """Test tag analysis from content"""

    @pytest.mark.unit
    def test_analyze_medical_content(self):
        """Test analyzing medical content for tags"""
        content = """
# CAR-T Therapy Overview

Treatment for lymphoma and cancer patients.
Medical diagnosis and therapy information.
"""
        tags = analyze_content_for_tags("medical.md", content)

        assert 'medical' in tags
        # Should not get unrelated tags
        assert 'cooking' not in tags
        assert 'tech' not in tags

    @pytest.mark.unit
    def test_analyze_recipe_content(self):
        """Test analyzing recipe content for tags"""
        content = """
# Pasta Recipe

Ingredients: pasta, sauce
Cook time: 20 minutes
Servings: 4
"""
        tags = analyze_content_for_tags("pasta.md", content)

        assert 'cooking' in tags
        assert 'recipe' in tags
        # Should not get tech tags
        assert 'tech' not in tags
        assert 'ai' not in tags

    @pytest.mark.unit
    def test_analyze_tech_content(self):
        """Test analyzing technical content for tags"""
        content = """
# Python API Development

Building REST APIs with Flask.
Software development best practices.
"""
        tags = analyze_content_for_tags("api_dev.md", content)

        assert 'tech' in tags
        # Should not get cooking tags
        assert 'cooking' not in tags
        assert 'recipe' not in tags

    @pytest.mark.unit
    def test_tag_exclusion_based_on_type(self):
        """Test that irrelevant tags are excluded based on content type"""
        # Medical content shouldn't get tech tags
        medical_content = "Treatment for lymphoma cancer diagnosis patient doctor"
        tags = analyze_content_for_tags("medical.md", medical_content)

        # Should have medical tag
        assert 'medical' in tags
        # Should NOT have tech, ai, hardware, cooking
        assert 'tech' not in tags
        assert 'ai' not in tags
        assert 'hardware' not in tags
        assert 'cooking' not in tags

    @pytest.mark.unit
    def test_minimum_keyword_threshold(self):
        """Test that minimum keyword matches are required"""
        # Single medical keyword shouldn't trigger medical tag
        content = "patient visited the store"
        tags = analyze_content_for_tags("note.md", content)

        # Should not get medical tag with only 1 keyword
        assert 'medical' not in tags

    @pytest.mark.unit
    def test_extract_capitalized_terms(self):
        """Test extraction of capitalized key terms"""
        content = """
Discussion about Python, Django, and Flask frameworks.
Reference to TensorFlow and PyTorch libraries.
"""
        tags = analyze_content_for_tags("frameworks.md", content)

        # Should extract some capitalized terms (lowercased)
        # Filter out common words
        capitalized_found = any(tag in ['python', 'django', 'flask'] for tag in tags)
        assert capitalized_found


class TestBacklinkFinding:
    """Test finding backlinks in MoCs"""

    @pytest.mark.unit
    def test_find_backlink_exact_match(self, temp_vault, sample_moc_content):
        """Test finding backlink with exact note name"""
        # Create MoC
        moc_path = temp_vault / "Main MoC.md"
        moc_path.write_text(sample_moc_content, encoding='utf-8')

        # Create note that MoC links to
        note_path = temp_vault / "Note 1.md"
        note_path.write_text("# Note 1\n\nContent", encoding='utf-8')

        moc_list = [{'file': 'Main MoC.md'}]

        backlink = find_backlink_moc(note_path, moc_list, temp_vault)
        assert backlink == 'Main MoC'

    @pytest.mark.unit
    def test_find_backlink_with_subfolder(self, temp_vault, sample_moc_content):
        """Test finding backlink for note in subfolder"""
        # Create MoC
        moc_path = temp_vault / "Main MoC.md"
        moc_path.write_text(sample_moc_content, encoding='utf-8')

        # Create note in subfolder
        subfolder = temp_vault / "Subfolder"
        subfolder.mkdir()
        note_path = subfolder / "Note 3.md"
        note_path.write_text("# Note 3\n\nContent", encoding='utf-8')

        moc_list = [{'file': 'Main MoC.md'}]

        backlink = find_backlink_moc(note_path, moc_list, temp_vault)
        assert backlink == 'Main MoC'

    @pytest.mark.unit
    def test_find_backlink_no_match(self, temp_vault, sample_moc_content):
        """Test when no backlink is found"""
        # Create MoC
        moc_path = temp_vault / "Main MoC.md"
        moc_path.write_text(sample_moc_content, encoding='utf-8')

        # Create note NOT linked in MoC
        note_path = temp_vault / "Unlinked Note.md"
        note_path.write_text("# Unlinked\n\nContent", encoding='utf-8')

        moc_list = [{'file': 'Main MoC.md'}]

        backlink = find_backlink_moc(note_path, moc_list, temp_vault)
        assert backlink is None


class TestGenerateTagsForNote:
    """Test generating tags for a complete note"""

    @pytest.mark.unit
    def test_generate_tags_basic(self, temp_vault, create_note_file):
        """Test basic tag generation for a note"""
        content = """---
tags: [existing-tag]
---

# Medical Note

Information about CAR-T therapy for lymphoma treatment.
Patient diagnosis and medical procedures.
"""
        note_path = create_note_file("medical.md", content)

        result = generate_tags_for_note(
            note_path, temp_vault,
            graph_builder=None,
            chroma_db_path=None,
            moc_list=None
        )

        assert result['file'] == 'medical.md'
        assert 'existing-tag' in result['existing_tags']
        assert 'medical' in result['suggested_tags']
        assert 'existing-tag' in result['final_tags']

    @pytest.mark.unit
    def test_generate_tags_no_duplicates(self, temp_vault, create_note_file):
        """Test that duplicate tags are not added"""
        content = """---
tags: [medical]
---

# Medical Note

Medical treatment information.
"""
        note_path = create_note_file("medical.md", content)

        result = generate_tags_for_note(
            note_path, temp_vault,
            graph_builder=None,
            chroma_db_path=None,
            moc_list=None
        )

        # 'medical' is already in existing tags
        assert 'medical' in result['existing_tags']
        # Should not be in suggested tags (no duplicates)
        assert 'medical' not in result['suggested_tags']

    @pytest.mark.unit
    def test_generate_tags_with_backlink(self, temp_vault, create_note_file):
        """Test tag generation with MoC backlink"""
        moc_content = """---
type: moc
---

# Main MoC

- [[test_note]]
"""
        create_note_file("Main MoC.md", moc_content)

        note_content = """# Test Note

Some content.
"""
        note_path = create_note_file("test_note.md", note_content)

        moc_list = [{'file': 'Main MoC.md'}]

        result = generate_tags_for_note(
            note_path, temp_vault,
            graph_builder=None,
            chroma_db_path=None,
            moc_list=moc_list
        )

        assert result['suggested_backlink'] == 'Main MoC'

    @pytest.mark.unit
    def test_generate_tags_limit(self, temp_vault, create_note_file):
        """Test that final tags are limited to 10"""
        content = """---
tags: [tag1, tag2, tag3, tag4, tag5]
---

# Note

Medical treatment cancer diagnosis patient doctor hospital
therapy immunotherapy lymphoma CAR-T medications procedures
"""
        note_path = create_note_file("note.md", content)

        result = generate_tags_for_note(
            note_path, temp_vault,
            graph_builder=None,
            chroma_db_path=None,
            moc_list=None
        )

        # Should limit to 10 tags total
        assert len(result['final_tags']) <= 10

    @pytest.mark.unit
    def test_generate_tags_error_handling(self, temp_vault):
        """Test error handling for non-existent file"""
        fake_path = temp_vault / "nonexistent.md"

        result = generate_tags_for_note(
            fake_path, temp_vault,
            graph_builder=None,
            chroma_db_path=None,
            moc_list=None
        )

        assert 'error' in result
        assert result['suggested_tags'] == []


class TestTagSourceTracking:
    """Test tracking where tags come from"""

    @pytest.mark.unit
    def test_track_content_analysis_source(self, temp_vault, create_note_file):
        """Test tracking tags from content analysis"""
        content = """# Medical Note

CAR-T therapy and lymphoma treatment information.
Patient diagnosis and medical procedures.
"""
        note_path = create_note_file("medical.md", content)

        result = generate_tags_for_note(
            note_path, temp_vault,
            graph_builder=None,
            chroma_db_path=None,
            moc_list=None
        )

        # Should have sources tracking
        assert 'sources' in result
        # Content analysis should contribute tags
        assert result['sources']['from_content_analysis'] > 0
