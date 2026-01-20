"""
SPEED CSV Parser

Parses SPEED CSV files into Event domain models with robust error handling.

The SPEED dataset has 106 columns with high missing data rates (93-100% in some fields).
This parser handles:
- Missing data sentinels (".", "", NaN)
- Type coercion and validation
- Chunked reading for memory efficiency
- Actor parsing (initiator, target, victim)
- Temporal information with varying precision
- Sparse field storage in properties dict
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Iterator, List, Optional, Dict, Any
from datetime import date

from src.domain.events import (
    Event,
    Actor,
    ActorRole,
    Location,
    TemporalInfo,
    Impact
)

logger = logging.getLogger(__name__)


class SPEEDCSVParser:
    """Parse SPEED CSV with robust error handling."""

    # Missing data sentinels in SPEED data
    MISSING_VALUES = [".", "", "nan", "NaN", None]

    def __init__(self, csv_path: Path):
        """
        Initialize parser.

        Args:
            csv_path: Path to SPEED CSV file
        """
        self.csv_path = csv_path
        self.errors: List[Dict] = []
        self.parsed_count = 0
        self.skipped_count = 0

    def parse(self, chunk_size: int = 1000) -> Iterator[Event]:
        """
        Parse CSV in chunks for memory efficiency.

        Args:
            chunk_size: Number of rows to process per chunk

        Yields:
            Event objects
        """
        logger.info(f"Parsing CSV: {self.csv_path}")

        try:
            # Read in chunks (use latin1 encoding for older CSV files)
            for chunk_idx, df_chunk in enumerate(pd.read_csv(
                self.csv_path,
                chunksize=chunk_size,
                na_values=self.MISSING_VALUES,
                keep_default_na=True,
                low_memory=False,
                encoding='latin1'
            )):
                logger.debug(f"Processing chunk {chunk_idx}, rows: {len(df_chunk)}")

                for idx, row in df_chunk.iterrows():
                    try:
                        event = self._parse_row(row)
                        if event:
                            self.parsed_count += 1
                            yield event
                        else:
                            self.skipped_count += 1
                    except Exception as e:
                        self._log_error(idx, row, e)
                        self.skipped_count += 1

        except Exception as e:
            logger.error(f"CSV parse failed: {e}")
            raise

        logger.info(f"Parsing complete. Parsed: {self.parsed_count}, Skipped: {self.skipped_count}, Errors: {len(self.errors)}")

    def _parse_row(self, row: pd.Series) -> Optional[Event]:
        """
        Parse a single CSV row into Event model.

        Args:
            row: Pandas Series representing one CSV row

        Returns:
            Event object or None if invalid
        """
        # Event ID is required
        event_id = self._safe_get(row, 'eventid')
        if not event_id:
            return None

        # Parse temporal info
        temporal = self._parse_temporal(row)

        # Parse actors
        initiator = self._parse_actor(row, 'INI', ActorRole.INITIATOR)
        target = self._parse_actor(row, 'TAR', ActorRole.TARGET)
        victim = self._parse_actor(row, 'VIC', ActorRole.VICTIM)

        # Parse location
        location = self._parse_location(row)

        # Parse impact
        impact = self._parse_impact(row)

        # Parse linked events
        is_linked = self._safe_int(row, 'linked') == 1
        linked_from = []
        linked_to = []
        if is_linked:
            from_eid = self._safe_get(row, 'FROM_EID')
            to_eid = self._safe_get(row, 'TO_EID')
            if from_eid:
                linked_from.append(from_eid)
            if to_eid:
                linked_to.append(to_eid)

        # Create event
        event = Event(
            event_id=event_id,
            temporal=temporal,
            event_type=self._safe_int(row, 'EV_TYPE'),
            pe_type=self._safe_int(row, 'PE_TYPE'),
            atk_type=self._safe_int(row, 'ATK_TYPE'),
            dsa_type=self._safe_int(row, 'DSA_TYPE'),
            news_source=self._safe_get(row, 'NEWS_SOURCE'),
            article_id=self._safe_get(row, 'aid'),
            initiator=initiator,
            target=target,
            victim=victim,
            location=location,
            impact=impact,
            is_quasi_event=self._safe_int(row, 'QUASI_EVENT') == 1,
            is_state_action=self._safe_int(row, 'STAT_ACT') == 1,
            is_coup=self._safe_int(row, 'coup') == 1,
            is_coup_failed=self._safe_int(row, 'COUP_FAILED') == 1,
            is_linked=is_linked,
            link_type=self._safe_int(row, 'LINK_TYPE'),
            linked_from=linked_from,
            linked_to=linked_to,
            is_posthoc=self._safe_int(row, 'posthoc') == 1
        )

        # Store sparse/motivation fields in properties
        self._extract_properties(row, event)

        return event

    def _parse_temporal(self, row: pd.Series) -> TemporalInfo:
        """Parse temporal information."""
        # Publication date
        pub_date = None
        pub_year = self._safe_int(row, 'PUB_YEAR')
        pub_mon = self._safe_int(row, 'PUB_MON')
        pub_day = self._safe_int(row, 'PUB_DATE')
        if pub_year and pub_mon and pub_day:
            try:
                pub_date = date(pub_year, pub_mon, pub_day)
            except ValueError:
                pass

        # Code date
        code_date = None
        code_year = self._safe_int(row, 'CODE_YEAR')
        code_mon = self._safe_int(row, 'CODE_MONTH')
        code_day = self._safe_int(row, 'CODE_DAY')
        if code_year and code_mon and code_day:
            try:
                code_date = date(code_year, code_mon, code_day)
            except ValueError:
                pass

        return TemporalInfo(
            year=self._safe_int(row, 'year'),
            month=self._safe_int(row, 'month'),
            day=self._safe_int(row, 'day'),
            date_type=self._safe_int(row, 'DATE_TYP'),
            julian_possible_start=self._safe_int(row, 'JUL_PSD'),
            julian_possible_end=self._safe_int(row, 'JUL_PED'),
            julian_earliest=self._safe_int(row, 'JUL_EED'),
            julian_latest=self._safe_int(row, 'JUL_LED'),
            julian_start_date=self._safe_int(row, 'JUL_START_DATE'),
            julian_end_date=self._safe_int(row, 'JUL_END_DATE'),
            day_span=self._safe_int(row, 'DAY_SPAN'),
            publication_date=pub_date,
            code_date=code_date
        )

    def _parse_actor(self, row: pd.Series, prefix: str, role: ActorRole) -> Optional[Actor]:
        """
        Parse actor information for given role (INI, TAR, VIC).

        Args:
            row: CSV row
            prefix: Field prefix (INI, TAR, or VIC)
            role: Actor role

        Returns:
            Actor object or None
        """
        # Check if actor exists (at least one group defined)
        igrp = self._safe_get(row, f'{prefix}_IGRP1')
        sgrp = self._safe_get(row, f'{prefix}_SGRP1')
        pgrp = self._safe_get(row, f'{prefix}_PGRP1')

        if not any([igrp, sgrp, pgrp]):
            return None

        # Build actor
        actor = Actor(
            role=role,
            identity_group=igrp,
            sector_group=sgrp,
            political_group=pgrp,
            actor_type=self._safe_int(row, f'{prefix}_TYPE'),
            government_type=self._safe_int(row, f'GOV_{prefix[0]}1'),
            government_level=self._safe_int(row, f'G_LVL_{prefix[0]}'),
            non_gov_type=self._safe_int(row, f'NGOV_{prefix[0]}1')
        )

        # Initiator-specific fields
        if prefix == 'INI':
            actor.is_known = self._safe_int(row, 'KNOW_INI')
            actor.ambiguity = self._safe_float(row, 'AMBIG_INI')
            actor.num_participants = self._safe_int(row, 'N_OF_INI_P')
            actor.num_armed = self._safe_int(row, 'N_OF_INI_A')

        # Human indicator for targets/victims
        if prefix == 'TAR':
            actor.human_indicator = self._safe_int(row, 'HUMAN_T1')
        elif prefix == 'VIC':
            actor.human_indicator = self._safe_int(row, 'HUMAN_V1')

        return actor

    def _parse_location(self, row: pd.Series) -> Optional[Location]:
        """Parse location information."""
        # Check if location exists
        gp3 = self._safe_get(row, 'GP3')
        country = self._safe_get(row, 'country')

        if not gp3 and not country:
            return None

        return Location(
            name=gp3,
            country=country,
            latitude=self._safe_float(row, 'GP7'),
            longitude=self._safe_float(row, 'GP8'),
            location_type=self._safe_int(row, 'LOC_TYPE'),
            region=self._safe_int(row, 'region'),
            cow_code=self._safe_int(row, 'cowcode'),
            pinpoint=self._safe_int(row, 'pinpoint')
        )

    def _parse_impact(self, row: pd.Series) -> Optional[Impact]:
        """Parse impact/casualties information."""
        # Check if any impact data exists
        has_impact = any([
            self._safe_int(row, 'N_KILLED_P'),
            self._safe_int(row, 'N_KILLED_A'),
            self._safe_int(row, 'N_INJURD'),
            self._safe_int(row, 'arrests'),
            self._safe_int(row, 'property_damaged')
        ])

        if not has_impact:
            return None

        return Impact(
            killed_participants=self._safe_int(row, 'N_KILLED_P'),
            killed_armed=self._safe_int(row, 'N_KILLED_A'),
            injured=self._safe_int(row, 'N_INJURD'),
            injured_detailed=self._safe_int(row, 'N_INJURD_D'),
            arrests=self._safe_int(row, 'arrests'),
            property_damaged=self._safe_int(row, 'property_damaged'),
            property_owner=self._safe_get(row, 'property_owner'),
            victim_effect=self._safe_get(row, 'victim_effect')
        )

    def _extract_properties(self, row: pd.Series, event: Event):
        """
        Extract sparse fields into event properties dict.

        These are fields with very high missing rates that don't warrant
        dedicated fields in the domain model.
        """
        sparse_fields = [
            # Violence/tactics
            'AD_VIOL', 'AD_TACT', 'weapon', 'WEAP_GRD',
            # Event characteristics
            'E_LENGTH', 'SYM_TYPE',
            # Motivation/context
            'SC_ANIMOSITY', 'ANTI_GOV_SENTMNTS', 'CLASS_CONFLICT',
            'POL_DESIRES', 'RETAIN_POWER', 'ECO_SCARCITY',
            'PERS_SECURITY', 'retribution', 'POL_EXPRESS',
            'MASS_EXPRESS', 'POL_VIOL', 'STAT_VIOL',
            'ST_REPRESS', 'PUB_ORDER',
            # Other
            'INTANG_REP', 'recap', 'AMBIG_WGT',
            'ctry_bias', 'TAR_GPOL', 'GP_TYPE', 'GP4'
        ]

        for field in sparse_fields:
            value = self._safe_get(row, field)
            if value is not None:
                event.properties[field] = value

        # Numeric fields that should remain numeric
        numeric_fields = [
            'N_INJURD', 'N_KILLED_P', 'N_KILLED_A',
            'N_OF_INI_P', 'N_OF_INI_A', 'WEAP_GRD', 'E_LENGTH'
        ]

        for field in numeric_fields:
            value = self._safe_int(row, field)
            if value is not None:
                event.properties[field] = value

    def _safe_get(self, row: pd.Series, field: str) -> Optional[str]:
        """
        Safely get string value, handling missing data.

        Args:
            row: CSV row
            field: Column name

        Returns:
            String value or None
        """
        if field not in row.index:
            return None

        value = row[field]
        if pd.isna(value) or value in self.MISSING_VALUES:
            return None

        return str(value).strip()

    def _safe_int(self, row: pd.Series, field: str) -> Optional[int]:
        """
        Safely get integer value.

        Args:
            row: CSV row
            field: Column name

        Returns:
            Integer value or None
        """
        value = self._safe_get(row, field)
        if value is None:
            return None

        try:
            # Handle "1.0" strings from CSV
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _safe_float(self, row: pd.Series, field: str) -> Optional[float]:
        """
        Safely get float value.

        Args:
            row: CSV row
            field: Column name

        Returns:
            Float value or None
        """
        value = self._safe_get(row, field)
        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _log_error(self, idx: int, row: pd.Series, error: Exception):
        """
        Log parsing error.

        Args:
            idx: Row index
            row: CSV row
            error: Exception that occurred
        """
        error_info = {
            "row_index": int(idx) if pd.notna(idx) else None,
            "event_id": self._safe_get(row, 'eventid'),
            "error": str(error),
            "error_type": type(error).__name__
        }
        self.errors.append(error_info)
        logger.warning(f"Row parse error at index {idx}: {error}")

    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get summary of parsing errors.

        Returns:
            Dictionary with error statistics
        """
        if not self.errors:
            return {"total_errors": 0}

        error_types = {}
        for error in self.errors:
            error_type = error.get('error_type', 'Unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "total_errors": len(self.errors),
            "error_types": error_types,
            "sample_errors": self.errors[:5]  # First 5 errors
        }


def main():
    """CLI for testing CSV parser."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python csv_parser.py <csv_file>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = SPEEDCSVParser(csv_path)

    # Parse first 100 events
    print(f"\nParsing first 100 events from {csv_path}\n")
    count = 0
    for event in parser.parse(chunk_size=100):
        count += 1
        if count <= 5:
            print(f"{count}. {event.display_summary}")
        if count >= 100:
            break

    print(f"\nParsed {count} events")
    print(f"Errors: {parser.get_error_summary()}")


if __name__ == "__main__":
    main()
