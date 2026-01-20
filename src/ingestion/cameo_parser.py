"""
CAMEO Reference File Parser

Parses CAMEO ontology files (actors, verbs, event types, options) into domain models.

File formats:
- Levant.080629.actors: Actor names with codes and metadata
- CAMEO.080612.verbs: Verb patterns with codes
- CAMEO.09b5.options: Event type labels (LABEL: code= description)
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging

from src.domain.cameo import (
    CAMEOActorType,
    CAMEOVerb,
    CAMEOEventType,
    CAMEOOption,
    CAMEOOntology
)

logger = logging.getLogger(__name__)


class CAMEOParser:
    """Parse CAMEO reference files into domain models."""

    def parse_actors(self, file_path: Path) -> List[CAMEOActorType]:
        """
        Parse CAMEO actors file.

        Format examples:
        - ACTOR_NAME   ;initials date
        - A_PRESIDENT_AND_FIVE_OTHER   ;ab 21 Sep 2005
        - IRAQI_GOVERNMENT [IRQGOV]
        - UNITED_STATES [USA]

        Args:
            file_path: Path to actors file

        Returns:
            List of CAMEOActorType objects
        """
        actors = []
        line_count = 0

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line_count = line_num
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('<') or line.startswith('//') or line.startswith('#'):
                        continue

                    # Parse actor entry
                    actor = self._parse_actor_line(line, line_num)
                    if actor:
                        actors.append(actor)

            logger.info(f"Parsed {len(actors)} actors from {file_path} ({line_count} lines)")

        except Exception as e:
            logger.error(f"Failed to parse actors file {file_path}: {e}")
            raise

        return actors

    def _parse_actor_line(self, line: str, line_num: int) -> Optional[CAMEOActorType]:
        """
        Parse a single actor line.

        Handles various formats:
        - NAME [CODE] ;metadata
        - NAME ;metadata
        - NAME [CODE <date] or [CODE >date] for temporal validity
        """
        # Extract code from [XXX] pattern
        code_match = re.search(r'\[([^\]]+)\]', line)
        code = None
        if code_match:
            code_raw = code_match.group(1)
            # Handle temporal markers like [CODE <date] or [CODE >date]
            code = re.sub(r'\s*[<>].*', '', code_raw).strip()

        # Extract metadata after semicolon
        metadata = None
        if ';' in line:
            parts = line.split(';', 1)
            metadata = parts[1].strip()
            line = parts[0]

        # Extract name (before [code] or whole line)
        if code_match:
            name = line[:code_match.start()].strip()
        else:
            name = line.split(';')[0].strip()

        # Use code as fallback name if no name provided
        if not name and code:
            name = code

        # Skip if both name and code are missing
        if not name and not code:
            return None

        # Handle special codes
        if code in ['---', '###', None]:
            code = name  # Use name as code for undefined codes

        # Clean up name (replace underscores with spaces)
        display_name = name.replace('_', ' ').title()

        return CAMEOActorType(
            code=code or name,
            name=display_name,
            description=metadata,
            date_added=metadata  # Metadata often contains date info
        )

    def parse_verbs(self, file_path: Path) -> List[CAMEOVerb]:
        """
        Parse CAMEO verbs file.

        Format examples:
        - VERB_PATTERN  [CODE] ;metadata
        - ABANDON  [---] ;OY 25 Jul 2003
        - ACCEPT * DEMAND [1032]

        Args:
            file_path: Path to verbs file

        Returns:
            List of CAMEOVerb objects
        """
        verbs = []
        line_count = 0

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line_count = line_num
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('//') or line.startswith('#'):
                        continue

                    # Parse verb entry
                    verb = self._parse_verb_line(line, line_num)
                    if verb:
                        verbs.append(verb)

            logger.info(f"Parsed {len(verbs)} verbs from {file_path} ({line_count} lines)")

        except Exception as e:
            logger.error(f"Failed to parse verbs file {file_path}: {e}")
            raise

        return verbs

    def _parse_verb_line(self, line: str, line_num: int) -> Optional[CAMEOVerb]:
        """Parse a single verb line."""
        # Extract code from [XXX] pattern
        code_match = re.search(r'\[([^\]]+)\]', line)
        code = code_match.group(1).strip() if code_match else None

        # Skip undefined codes
        if code in ['---', '###']:
            code = None

        # Get pattern (text before [code])
        if code_match:
            pattern = line[:code_match.start()].strip()
        else:
            # If no code, split on semicolon
            pattern = line.split(';')[0].strip()

        # Metadata after semicolon
        metadata = None
        if ';' in line:
            metadata = line.split(';', 1)[1].strip()

        if not pattern:
            return None

        # Determine hierarchy level from code
        level = self._get_verb_level(code) if code else 0

        # Determine parent code
        parent_code = None
        if code and len(code) > 2:
            parent_code = code[:-1]

        return CAMEOVerb(
            code=code or '',
            pattern=pattern,
            label=metadata,
            level=level,
            parent_code=parent_code,
            metadata=metadata
        )

    def _get_verb_level(self, code: Optional[str]) -> int:
        """Determine hierarchy level from code length."""
        if not code or code in ['---', '###']:
            return 0
        return len(code)

    def parse_event_types(self, file_path: Path) -> List[CAMEOEventType]:
        """
        Parse CAMEO event type labels from options file.

        Format:
        - LABEL: 010= Make statement
        - LABEL: 0111= Decline comment on specific issue

        Args:
            file_path: Path to options file

        Returns:
            List of CAMEOEventType objects
        """
        event_types = []
        line_count = 0

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line_count = line_num
                    line = line.strip()

                    # Skip non-label lines
                    if not line.startswith('LABEL:'):
                        continue

                    # Parse "LABEL: 010= Make statement"
                    match = re.match(r'LABEL:\s*(\d+)\s*=\s*(.+)', line)
                    if match:
                        code, label = match.groups()
                        event_type = CAMEOEventType(
                            code=code.strip(),
                            label=label.strip(),
                            level=len(code.strip()),
                            category=code.strip()[:2] if len(code.strip()) >= 2 else code.strip()
                        )
                        event_types.append(event_type)

            logger.info(f"Parsed {len(event_types)} event types from {file_path} ({line_count} lines)")

        except Exception as e:
            logger.error(f"Failed to parse event types file {file_path}: {e}")
            raise

        return event_types

    def parse_options(self, file_path: Path) -> List[CAMEOOption]:
        """
        Parse CAMEO options/qualifiers.

        Currently, options are primarily the event type labels.
        This method can be extended for additional option types.

        Args:
            file_path: Path to options file

        Returns:
            List of CAMEOOption objects
        """
        options = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()

                    # Parse option entries (non-label entries)
                    if line and not line.startswith('LABEL:') and not line.startswith('//'):
                        # Simple key=value options
                        if '=' in line:
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                code, label = parts
                                option = CAMEOOption(
                                    code=code.strip(),
                                    label=label.strip()
                                )
                                options.append(option)

            logger.info(f"Parsed {len(options)} options from {file_path}")

        except Exception as e:
            logger.error(f"Failed to parse options file {file_path}: {e}")
            raise

        return options

    def build_event_type_hierarchy(self, event_types: List[CAMEOEventType]) -> Dict[str, List[str]]:
        """
        Build parent-child relationships for event types.

        Args:
            event_types: List of CAMEOEventType objects

        Returns:
            Dictionary mapping parent codes to lists of child codes
        """
        hierarchy = {}
        for et in event_types:
            if et.parent_code:
                if et.parent_code not in hierarchy:
                    hierarchy[et.parent_code] = []
                hierarchy[et.parent_code].append(et.code)

        logger.info(f"Built event type hierarchy with {len(hierarchy)} parent nodes")
        return hierarchy

    def parse_all(self, cameo_dir: Path) -> CAMEOOntology:
        """
        Parse all CAMEO files and return complete ontology.

        Args:
            cameo_dir: Directory containing CAMEO reference files

        Returns:
            CAMEOOntology with all components loaded
        """
        logger.info(f"Parsing CAMEO ontology from {cameo_dir}")

        # Expected file names
        actors_file = cameo_dir / "Levant.080629.actors"
        verbs_file = cameo_dir / "CAMEO.080612.verbs"
        options_file = cameo_dir / "CAMEO.09b5.options"

        # Parse each file
        actors = []
        if actors_file.exists():
            actors = self.parse_actors(actors_file)
        else:
            logger.warning(f"Actors file not found: {actors_file}")

        verbs = []
        if verbs_file.exists():
            verbs = self.parse_verbs(verbs_file)
        else:
            logger.warning(f"Verbs file not found: {verbs_file}")

        event_types = []
        options = []
        if options_file.exists():
            event_types = self.parse_event_types(options_file)
            options = self.parse_options(options_file)
        else:
            logger.warning(f"Options file not found: {options_file}")

        ontology = CAMEOOntology(
            actor_types=actors,
            verbs=verbs,
            event_types=event_types,
            options=options
        )

        logger.info(f"Parsed complete CAMEO ontology: {ontology}")
        return ontology


def main():
    """CLI for testing CAMEO parser."""
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python cameo_parser.py <cameo_directory>")
        sys.exit(1)

    cameo_dir = Path(sys.argv[1])
    if not cameo_dir.exists():
        print(f"Directory not found: {cameo_dir}")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = CAMEOParser()
    ontology = parser.parse_all(cameo_dir)

    print(f"\n{ontology}")
    print(f"\nSample actor types:")
    for actor in ontology.actor_types[:5]:
        print(f"  {actor}")

    print(f"\nSample event types:")
    for et in ontology.event_types[:5]:
        print(f"  {et}")

    print(f"\nEvent hierarchy (first 5 parent nodes):")
    hierarchy = ontology.build_event_hierarchy()
    for parent, children in list(hierarchy.items())[:5]:
        print(f"  {parent} -> {children}")


if __name__ == "__main__":
    main()
