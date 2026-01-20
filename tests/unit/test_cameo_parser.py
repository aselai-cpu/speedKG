"""
Unit tests for CAMEO parser
"""

import pytest
from pathlib import Path
from src.ingestion.cameo_parser import CAMEOParser
from src.domain.cameo import CAMEOActorType, CAMEOEventType, CAMEOVerb


class TestCAMEOParser:
    """Test CAMEO parser functionality."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return CAMEOParser()

    @pytest.fixture
    def sample_actor_lines(self):
        """Sample actor file lines."""
        return [
            "UNITED_STATES [USA]",
            "IRAQI_GOVERNMENT [IRQGOV]",
            "PALESTINIAN_AUTHORITY [PSEGOV]",
            "A_PRESIDENT_AND_FIVE_OTHER   ;ab 21 Sep 2005",
            "UNITED_NATIONS [IGOUNO]",
            "# This is a comment",
            "",  # Empty line
        ]

    @pytest.fixture
    def sample_verb_lines(self):
        """Sample verb file lines."""
        return [
            "ABANDON [---] ;OY 25 Jul 2003",
            "ACCEPT * DEMAND [1032]",
            "ACKNOWLEDGE [010]",
            "// This is a comment",
        ]

    @pytest.fixture
    def sample_event_type_lines(self):
        """Sample event type label lines."""
        return [
            "LABEL: 010= Make statement",
            "LABEL: 011= Decline comment",
            "LABEL: 0111= Decline comment on specific issue",
            "LABEL: 1823= Kill by physical assault",
        ]

    def test_parse_actor_line_with_code(self, parser):
        """Test parsing actor line with code."""
        line = "UNITED_STATES [USA]"
        actor = parser._parse_actor_line(line, 1)

        assert actor is not None
        assert actor.code == "USA"
        assert "United States" in actor.name

    def test_parse_actor_line_with_metadata(self, parser):
        """Test parsing actor line with metadata."""
        line = "A_PRESIDENT_AND_FIVE_OTHER   ;ab 21 Sep 2005"
        actor = parser._parse_actor_line(line, 1)

        assert actor is not None
        assert actor.description == "ab 21 Sep 2005"

    def test_parse_actor_line_igo(self, parser):
        """Test parsing international organization."""
        line = "UNITED_NATIONS [IGOUNO]"
        actor = parser._parse_actor_line(line, 1)

        assert actor is not None
        assert actor.code == "IGOUNO"
        assert actor.is_international_org

    def test_parse_verb_line_with_code(self, parser):
        """Test parsing verb line with code."""
        line = "ACKNOWLEDGE [010]"
        verb = parser._parse_verb_line(line, 1)

        assert verb is not None
        assert verb.code == "010"
        assert verb.pattern == "ACKNOWLEDGE"
        assert verb.level == 3

    def test_parse_verb_line_without_code(self, parser):
        """Test parsing verb line without code."""
        line = "ABANDON [---] ;OY 25 Jul 2003"
        verb = parser._parse_verb_line(line, 1)

        assert verb is not None
        assert verb.code is None or verb.code == ""
        assert verb.pattern == "ABANDON"

    def test_event_type_properties(self):
        """Test event type properties."""
        et = CAMEOEventType(code="1823", label="Kill by physical assault", level=4)

        assert et.root_category == "18"
        assert et.parent_code == "182"
        assert et.is_conflict
        assert et.is_material
        assert not et.is_cooperation
        assert not et.is_verbal

    def test_event_type_cooperation(self):
        """Test cooperation event detection."""
        et = CAMEOEventType(code="05", label="Engage in diplomatic cooperation", level=2)

        assert et.is_cooperation
        assert et.is_verbal
        assert not et.is_conflict
        assert not et.is_material

    def test_actor_type_properties(self):
        """Test actor type properties."""
        actor = CAMEOActorType(code="USAGOV", name="United States Government")

        assert actor.base_country == "USA"
        assert actor.actor_type == "GOV"
        assert not actor.is_international_org

    def test_igo_actor_type(self):
        """Test international organization actor."""
        actor = CAMEOActorType(code="IGOUNO", name="United Nations")

        assert actor.is_international_org
        assert actor.base_country is None

    def test_verb_level_calculation(self, parser):
        """Test verb level calculation."""
        assert parser._get_verb_level("01") == 2
        assert parser._get_verb_level("010") == 3
        assert parser._get_verb_level("0111") == 4
        assert parser._get_verb_level(None) == 0
        assert parser._get_verb_level("---") == 0

    def test_event_hierarchy_building(self, parser):
        """Test event type hierarchy building."""
        event_types = [
            CAMEOEventType(code="01", label="Root", level=2),
            CAMEOEventType(code="010", label="Child1", level=3),
            CAMEOEventType(code="011", label="Child2", level=3),
            CAMEOEventType(code="0111", label="Grandchild", level=4),
        ]

        hierarchy = parser.build_event_type_hierarchy(event_types)

        assert "01" in hierarchy
        assert "010" in hierarchy["01"]
        assert "011" in hierarchy["01"]
        assert "011" in hierarchy
        assert "0111" in hierarchy["011"]


# Integration tests (require actual data files)
class TestCAMEOParserIntegration:
    """Integration tests with actual CAMEO files."""

    @pytest.fixture
    def cameo_dir(self):
        """Path to CAMEO data directory."""
        return Path("data/cameo")

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return CAMEOParser()

    @pytest.mark.skipif(
        not Path("data/cameo").exists(),
        reason="CAMEO data directory not found"
    )
    def test_parse_actual_actors(self, parser, cameo_dir):
        """Test parsing actual actors file."""
        actors_file = cameo_dir / "Levant.080629.actors"

        if not actors_file.exists():
            pytest.skip(f"Actors file not found: {actors_file}")

        actors = parser.parse_actors(actors_file)

        assert len(actors) > 0
        assert all(isinstance(a, CAMEOActorType) for a in actors)
        assert all(a.code for a in actors)

    @pytest.mark.skipif(
        not Path("data/cameo").exists(),
        reason="CAMEO data directory not found"
    )
    def test_parse_actual_event_types(self, parser, cameo_dir):
        """Test parsing actual event types."""
        options_file = cameo_dir / "CAMEO.09b5.options"

        if not options_file.exists():
            pytest.skip(f"Options file not found: {options_file}")

        event_types = parser.parse_event_types(options_file)

        assert len(event_types) > 0
        assert all(isinstance(et, CAMEOEventType) for et in event_types)

        # Check for expected root categories
        root_cats = {et.root_category for et in event_types}
        assert "01" in root_cats
        assert "18" in root_cats

    @pytest.mark.skipif(
        not Path("data/cameo").exists(),
        reason="CAMEO data directory not found"
    )
    def test_parse_all_ontology(self, parser, cameo_dir):
        """Test parsing complete ontology."""
        if not cameo_dir.exists():
            pytest.skip(f"CAMEO directory not found: {cameo_dir}")

        ontology = parser.parse_all(cameo_dir)

        assert ontology is not None
        assert len(ontology.actor_types) > 0
        assert len(ontology.event_types) > 0

        # Test ontology methods
        hierarchy = ontology.build_event_hierarchy()
        assert len(hierarchy) > 0

        # Test lookup methods
        usa_actor = ontology.get_actor_type("USA")
        assert usa_actor is None or usa_actor.code == "USA"
