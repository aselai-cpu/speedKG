"""
Unit tests for SPEED CSV parser
"""

import pytest
from pathlib import Path
from src.ingestion.csv_parser import SPEEDCSVParser
from src.domain.events import Event, ActorRole


class TestSPEEDCSVParser:
    """Test CSV parser functionality."""

    @pytest.fixture
    def parser(self, tmp_path):
        """Create parser with temporary CSV file."""
        csv_file = tmp_path / "test.csv"
        return SPEEDCSVParser(csv_file)

    def test_safe_get_valid_value(self, parser):
        """Test safe get with valid value."""
        import pandas as pd
        row = pd.Series({'field1': 'value1', 'field2': 123})

        result = parser._safe_get(row, 'field1')
        assert result == 'value1'

    def test_safe_get_missing_sentinel(self, parser):
        """Test safe get with missing sentinel."""
        import pandas as pd
        row = pd.Series({'field1': '.', 'field2': ''})

        assert parser._safe_get(row, 'field1') is None
        assert parser._safe_get(row, 'field2') is None

    def test_safe_get_nan(self, parser):
        """Test safe get with NaN."""
        import pandas as pd
        import numpy as np
        row = pd.Series({'field1': np.nan})

        assert parser._safe_get(row, 'field1') is None

    def test_safe_int_valid(self, parser):
        """Test safe int with valid value."""
        import pandas as pd
        row = pd.Series({'field1': '123', 'field2': '45.0'})

        assert parser._safe_int(row, 'field1') == 123
        assert parser._safe_int(row, 'field2') == 45

    def test_safe_int_invalid(self, parser):
        """Test safe int with invalid value."""
        import pandas as pd
        row = pd.Series({'field1': 'abc', 'field2': '.'})

        assert parser._safe_int(row, 'field1') is None
        assert parser._safe_int(row, 'field2') is None

    def test_safe_float_valid(self, parser):
        """Test safe float with valid value."""
        import pandas as pd
        row = pd.Series({'field1': '123.45', 'field2': '67'})

        assert parser._safe_float(row, 'field1') == 123.45
        assert parser._safe_float(row, 'field2') == 67.0

    def test_parse_temporal(self, parser):
        """Test temporal information parsing."""
        import pandas as pd
        row = pd.Series({
            'year': 1950,
            'month': 6,
            'day': 15,
            'DATE_TYP': 1,
            'DAY_SPAN': 1,
            'JUL_START_DATE': 123456,
            'PUB_YEAR': 1950,
            'PUB_MON': 6,
            'PUB_DATE': 20
        })

        temporal = parser._parse_temporal(row)

        assert temporal.year == 1950
        assert temporal.month == 6
        assert temporal.day == 15
        assert temporal.precision == "day"
        assert temporal.calendar_date is not None

    def test_parse_actor_initiator(self, parser):
        """Test initiator actor parsing."""
        import pandas as pd
        row = pd.Series({
            'INI_IGRP1': 'United States',
            'INI_SGRP1': 'Government',
            'INI_PGRP1': 'Military',
            'INI_TYPE': 2,
            'GOV_I1': 5,
            'G_LVL_I': 4,
            'KNOW_INI': 1,
            'AMBIG_INI': 0.0,
            'N_OF_INI_P': 100,
            'N_OF_INI_A': 50
        })

        actor = parser._parse_actor(row, 'INI', ActorRole.INITIATOR)

        assert actor is not None
        assert actor.role == ActorRole.INITIATOR
        assert actor.identity_group == 'United States'
        assert actor.political_group == 'Military'
        assert actor.is_government
        assert actor.num_participants == 100
        assert actor.num_armed == 50

    def test_parse_actor_no_data(self, parser):
        """Test actor parsing with no data."""
        import pandas as pd
        row = pd.Series({
            'INI_IGRP1': '.',
            'INI_SGRP1': '',
            'INI_PGRP1': None
        })

        actor = parser._parse_actor(row, 'INI', ActorRole.INITIATOR)

        assert actor is None

    def test_parse_location(self, parser):
        """Test location parsing."""
        import pandas as pd
        row = pd.Series({
            'GP3': 'Washington DC',
            'country': 'United States',
            'GP7': 38.9072,
            'GP8': -77.0369,
            'LOC_TYPE': 2,
            'region': 1
        })

        location = parser._parse_location(row)

        assert location is not None
        assert location.name == 'Washington DC'
        assert location.country == 'United States'
        assert location.has_coordinates
        assert -90 <= location.latitude <= 90
        assert -180 <= location.longitude <= 180

    def test_parse_impact(self, parser):
        """Test impact parsing."""
        import pandas as pd
        row = pd.Series({
            'N_KILLED_P': 10,
            'N_KILLED_A': 5,
            'N_INJURD': 20,
            'arrests': 15,
            'property_damaged': 1
        })

        impact = parser._parse_impact(row)

        assert impact is not None
        assert impact.total_killed == 15
        assert impact.total_injured == 20
        assert impact.has_casualties

    def test_error_logging(self, parser):
        """Test error logging."""
        import pandas as pd

        row = pd.Series({'eventid': 'EID001'})
        error = ValueError("Test error")

        parser._log_error(1, row, error)

        assert len(parser.errors) == 1
        assert parser.errors[0]['event_id'] == 'EID001'
        assert parser.errors[0]['error_type'] == 'ValueError'

    def test_error_summary(self, parser):
        """Test error summary generation."""
        import pandas as pd

        # Log some errors
        row1 = pd.Series({'eventid': 'EID001'})
        row2 = pd.Series({'eventid': 'EID002'})

        parser._log_error(1, row1, ValueError("Error 1"))
        parser._log_error(2, row2, KeyError("Error 2"))
        parser._log_error(3, row1, ValueError("Error 3"))

        summary = parser.get_error_summary()

        assert summary['total_errors'] == 3
        assert 'ValueError' in summary['error_types']
        assert summary['error_types']['ValueError'] == 2
        assert 'KeyError' in summary['error_types']
        assert len(summary['sample_errors']) <= 5


# Integration test with actual data
class TestSPEEDCSVParserIntegration:
    """Integration tests with actual SPEED CSV."""

    @pytest.fixture
    def speed_csv(self):
        """Path to SPEED CSV file."""
        return Path("data/ssp_public.csv")

    @pytest.mark.skipif(
        not Path("data/ssp_public.csv").exists(),
        reason="SPEED CSV file not found"
    )
    def test_parse_actual_csv(self, speed_csv):
        """Test parsing actual SPEED CSV file."""
        parser = SPEEDCSVParser(speed_csv)

        # Parse first 100 events
        events = list(event for i, event in enumerate(parser.parse(chunk_size=100)) if i < 100)

        assert len(events) > 0
        assert all(isinstance(e, Event) for e in events)
        assert all(e.event_id for e in events)

        # Check some events have actors
        events_with_actors = [e for e in events if e.has_actors]
        assert len(events_with_actors) > 0

        # Check some events have locations
        events_with_location = [e for e in events if e.has_location]
        assert len(events_with_location) > 0
