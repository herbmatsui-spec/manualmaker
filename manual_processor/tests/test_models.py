"""
Tests for data models.
"""

import pytest

from src.models import Section


class TestSection:
    """Test Section dataclass"""

    def test_create_section_basic(self):
        """Test creating a basic section"""
        section = Section(title="Test Section", content="Test content")
        assert section.title == "Test Section"
        assert section.content == "Test content"
        assert section.subsections == []

    def test_create_section_with_subsections(self):
        """Test creating a section with subsections"""
        subsection1 = Section(title="Sub 1", content="Content 1")
        subsection2 = Section(title="Sub 2", content="Content 2")
        section = Section(
            title="Main Section",
            content="Main content",
            subsections=[subsection1, subsection2]
        )
        assert len(section.subsections) == 2
        assert section.subsections[0].title == "Sub 1"

    def test_to_dict_basic(self):
        """Test to_dict without subsections"""
        section = Section(title="Test", content="Content")
        result = section.to_dict()
        assert result == {"title": "Test", "content": "Content"}

    def test_to_dict_with_subsections(self):
        """Test to_dict with subsections (note: current impl doesn't include subsections in dict)"""
        subsection = Section(title="Sub", content="Sub content")
        section = Section(title="Main", content="Main content", subsections=[subsection])
        result = section.to_dict()
        # Current implementation returns only title and content
        assert result == {"title": "Main", "content": "Main content"}
        assert "subsections" not in result

    def test_section_equality(self):
        """Test section equality"""
        section1 = Section(title="Test", content="Content")
        section2 = Section(title="Test", content="Content")
        assert section1 == section2

    def test_section_inequality(self):
        """Test section inequality"""
        section1 = Section(title="Test 1", content="Content")
        section2 = Section(title="Test 2", content="Content")
        assert section1 != section2

    def test_section_with_empty_strings(self):
        """Test section with empty strings"""
        section = Section(title="", content="")
        assert section.title == ""
        assert section.content == ""
        result = section.to_dict()
        assert result == {"title": "", "content": ""}

    def test_section_nested_subsections(self):
        """Test deeply nested subsections"""
        deep = Section(title="Deep", content="Deep content")
        mid = Section(title="Mid", content="Mid content", subsections=[deep])
        top = Section(title="Top", content="Top content", subsections=[mid])
        
        assert len(top.subsections) == 1
        assert top.subsections[0].subsections[0].title == "Deep"
