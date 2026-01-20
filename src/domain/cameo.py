"""
CAMEO (Conflict and Mediation Event Observations) domain models.

This module defines the data structures for CAMEO ontology components:
- Actor types with hierarchical codes
- Event/verb codes with 4-level hierarchy
- Event type classifications
- Options and qualifiers
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import date


@dataclass
class CAMEOActorType:
    """
    Represents a CAMEO actor type with hierarchical coding.

    CAMEO actor codes use a hierarchical structure:
    - First 3 letters: Country/Region code (e.g., USA, IRQ, PAL)
    - Additional suffixes: Actor type (GOV, MIL, REB, COP, etc.)

    Examples:
    - USAGOV: United States Government
    - IRQREB: Iraq Rebel groups
    - IGOUNO: International Government Organization - United Nations
    """
    code: str
    name: str
    description: Optional[str] = None
    date_added: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    @property
    def base_country(self) -> Optional[str]:
        """Extract country code from actor code (first 3 chars)."""
        if len(self.code) >= 3 and not self.code.startswith('IGO') and not self.code.startswith('NGO'):
            return self.code[:3]
        return None

    @property
    def actor_type(self) -> Optional[str]:
        """Extract actor type suffix (e.g., GOV, MIL, REB)."""
        if len(self.code) > 3:
            return self.code[3:]
        return None

    @property
    def is_international_org(self) -> bool:
        """Check if this is an international organization."""
        return self.code.startswith('IGO') or self.code.startswith('NGO')

    def __repr__(self) -> str:
        return f"CAMEOActorType(code='{self.code}', name='{self.name}')"


@dataclass
class CAMEOVerb:
    """
    Represents a CAMEO verb/action pattern.

    CAMEO verbs define action patterns for event classification.
    They can include wildcards and special patterns for entity extraction.
    """
    code: str
    pattern: str
    label: Optional[str] = None
    level: int = 0
    parent_code: Optional[str] = None
    metadata: Optional[str] = None

    @property
    def root_category(self) -> str:
        """Get root CAMEO category (01-20)."""
        if len(self.code) >= 2:
            return self.code[:2]
        return self.code

    @property
    def is_root(self) -> bool:
        """Check if this is a root category (2 digits)."""
        return len(self.code) == 2

    def __repr__(self) -> str:
        return f"CAMEOVerb(code='{self.code}', pattern='{self.pattern[:30]}...')"


@dataclass
class CAMEOEventType:
    """
    Represents a CAMEO event type with hierarchical classification.

    Event types form a 4-level hierarchy:
    - Level 1 (2 digits): Root categories (01-20)
    - Level 2 (3 digits): Primary subcategories
    - Level 3 (4 digits): Detailed subcategories
    - Level 4 (5 digits): Most specific classifications

    Examples:
    - 01: Make public statement
    - 011: Decline comment
    - 0111: Decline comment on specific issue
    """
    code: str
    label: str
    level: int
    category: Optional[str] = None

    @property
    def parent_code(self) -> Optional[str]:
        """Get parent event type code."""
        if self.level > 1 and len(self.code) > 2:
            return self.code[:-1]
        return None

    @property
    def root_category(self) -> str:
        """Get root category code (first 2 digits)."""
        return self.code[:2] if len(self.code) >= 2 else self.code

    @property
    def is_cooperation(self) -> bool:
        """Check if this is a cooperative event (categories 01-09)."""
        try:
            cat = int(self.root_category)
            return 1 <= cat <= 9
        except ValueError:
            return False

    @property
    def is_conflict(self) -> bool:
        """Check if this is a conflict event (categories 10-20)."""
        try:
            cat = int(self.root_category)
            return 10 <= cat <= 20
        except ValueError:
            return False

    @property
    def is_material(self) -> bool:
        """Check if this is a material event (categories 15-20)."""
        try:
            cat = int(self.root_category)
            return 15 <= cat <= 20
        except ValueError:
            return False

    @property
    def is_verbal(self) -> bool:
        """Check if this is a verbal event (categories 01-14)."""
        try:
            cat = int(self.root_category)
            return 1 <= cat <= 14
        except ValueError:
            return False

    def __repr__(self) -> str:
        return f"CAMEOEventType(code='{self.code}', label='{self.label}', level={self.level})"


@dataclass
class CAMEOOption:
    """
    Represents a CAMEO option/qualifier for events.

    Options provide additional qualifiers and attributes for events
    beyond the basic event type classification.
    """
    code: str
    label: str
    description: Optional[str] = None

    def __repr__(self) -> str:
        return f"CAMEOOption(code='{self.code}', label='{self.label}')"


@dataclass
class CAMEOOntology:
    """
    Complete CAMEO ontology with all components.

    This serves as a container for the full CAMEO taxonomy including
    actor types, verbs, event types, and options.
    """
    actor_types: List[CAMEOActorType] = field(default_factory=list)
    verbs: List[CAMEOVerb] = field(default_factory=list)
    event_types: List[CAMEOEventType] = field(default_factory=list)
    options: List[CAMEOOption] = field(default_factory=list)

    def get_event_type(self, code: str) -> Optional[CAMEOEventType]:
        """Get event type by code."""
        for et in self.event_types:
            if et.code == code:
                return et
        return None

    def get_actor_type(self, code: str) -> Optional[CAMEOActorType]:
        """Get actor type by code."""
        for at in self.actor_types:
            if at.code == code:
                return at
        return None

    def get_event_types_by_category(self, category: str) -> List[CAMEOEventType]:
        """Get all event types in a root category."""
        return [et for et in self.event_types if et.root_category == category]

    def build_event_hierarchy(self) -> dict:
        """
        Build parent-child relationships for event types.

        Returns:
            Dictionary mapping parent codes to lists of child codes
        """
        hierarchy = {}
        for et in self.event_types:
            if et.parent_code:
                if et.parent_code not in hierarchy:
                    hierarchy[et.parent_code] = []
                hierarchy[et.parent_code].append(et.code)
        return hierarchy

    def __repr__(self) -> str:
        return (f"CAMEOOntology(actors={len(self.actor_types)}, "
                f"verbs={len(self.verbs)}, "
                f"event_types={len(self.event_types)}, "
                f"options={len(self.options)})")


# CAMEO event category mappings for reference
CAMEO_ROOT_CATEGORIES = {
    "01": "Make public statement",
    "02": "Appeal",
    "03": "Express intent to cooperate",
    "04": "Consult",
    "05": "Engage in diplomatic cooperation",
    "06": "Engage in material cooperation",
    "07": "Provide aid",
    "08": "Yield",
    "09": "Investigate",
    "10": "Demand",
    "11": "Disapprove",
    "12": "Reject",
    "13": "Threaten",
    "14": "Protest",
    "15": "Exhibit military posture",
    "16": "Reduce relations",
    "17": "Coerce",
    "18": "Assault",
    "19": "Fight",
    "20": "Use unconventional mass violence"
}


# Quadrant classification for Goldstein scale
CAMEO_QUADRANTS = {
    "verbal_cooperation": ["01", "02", "03", "04", "05"],
    "material_cooperation": ["06", "07", "08", "09"],
    "verbal_conflict": ["10", "11", "12", "13", "14"],
    "material_conflict": ["15", "16", "17", "18", "19", "20"]
}
