"""
SPEED Event Domain Models

Defines the core domain entities for SPEED historical events, including:
- Event: Main event entity with temporal, spatial, and actor information
- Actor: Event participants (initiators, targets, victims)
- Location: Geographic information
- TemporalInfo: Date and time details with varying precision
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


class ActorRole(Enum):
    """Roles an actor can play in an event."""
    INITIATOR = "initiator"
    TARGET = "target"
    VICTIM = "victim"


@dataclass
class Actor:
    """
    Represents an actor in an event (initiator, target, or victim).

    Actors are derived from SPEED CSV fields like:
    - INI_IGRP1, INI_SGRP1, INI_PGRP1 (initiator groups)
    - TAR_IGRP1, TAR_SGRP1, TAR_PGRP1 (target groups)
    - VIC_IGRP1, VIC_SGRP1, VIC_PGRP1 (victim groups)
    """
    role: ActorRole
    identity_group: Optional[str] = None  # IGRP1
    sector_group: Optional[str] = None    # SGRP1
    political_group: Optional[str] = None # PGRP1
    actor_type: Optional[int] = None      # TYPE field (1-5)
    government_type: Optional[int] = None # GOV_X1 (1-23 government types)
    government_level: Optional[int] = None # G_LVL_X (1-4: local to national)
    non_gov_type: Optional[int] = None    # NGOV_X1 (1-37 non-gov types)
    is_known: Optional[int] = None        # KNOW_INI (0/1/2)
    ambiguity: Optional[float] = None     # AMBIG_INI, AMBIG_WGT
    human_indicator: Optional[int] = None # HUMAN_T1, HUMAN_V1
    num_participants: Optional[int] = None # N_OF_INI_P
    num_armed: Optional[int] = None       # N_OF_INI_A

    @property
    def primary_name(self) -> Optional[str]:
        """Get the most specific group name available."""
        return (self.political_group or
                self.sector_group or
                self.identity_group)

    @property
    def is_government(self) -> bool:
        """Check if this is a government actor."""
        return self.government_type is not None and self.government_type > 0

    @property
    def is_non_government(self) -> bool:
        """Check if this is a non-government actor."""
        return self.non_gov_type is not None and self.non_gov_type > 0

    @property
    def is_human(self) -> bool:
        """Check if this is a human target/victim."""
        return self.human_indicator == 1

    def __repr__(self) -> str:
        name = self.primary_name or "Unknown"
        return f"Actor(role={self.role.value}, name='{name}')"


@dataclass
class Location:
    """
    Represents event location with geographic data.

    Derived from SPEED CSV fields:
    - GP3, GP4: Location names
    - GP7, GP8: Latitude, Longitude
    - country, region, cowcode: Geographic classifications
    """
    name: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_type: Optional[int] = None   # LOC_TYPE (precision indicator)
    region: Optional[int] = None          # Regional classification
    cow_code: Optional[int] = None        # Correlates of War country code
    pinpoint: Optional[int] = None        # Location precision flag

    @property
    def has_coordinates(self) -> bool:
        """Check if valid coordinates are available."""
        return (self.latitude is not None and
                self.longitude is not None and
                -90 <= self.latitude <= 90 and
                -180 <= self.longitude <= 180)

    @property
    def display_name(self) -> str:
        """Get displayable location name."""
        if self.name:
            return self.name
        if self.country:
            return self.country
        return "Unknown Location"

    def __repr__(self) -> str:
        coords = f"({self.latitude}, {self.longitude})" if self.has_coordinates else "no coords"
        return f"Location(name='{self.display_name}', {coords})"


@dataclass
class TemporalInfo:
    """
    Event temporal information with varying precision.

    SPEED events have multiple date fields for different precision levels:
    - year, month, day: Basic calendar date
    - Julian dates (JUL_*): Various precision levels
    - DAY_SPAN: Event duration
    - DATE_TYP: Date type qualifier
    """
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    date_type: Optional[int] = None       # DATE_TYP
    julian_possible_start: Optional[int] = None  # JUL_PSD
    julian_possible_end: Optional[int] = None    # JUL_PED
    julian_earliest: Optional[int] = None        # JUL_EED
    julian_latest: Optional[int] = None          # JUL_LED
    julian_start_date: Optional[int] = None      # JUL_START_DATE
    julian_end_date: Optional[int] = None        # JUL_END_DATE
    day_span: Optional[int] = None        # Event duration in days
    publication_date: Optional[date] = None # Article publication date
    code_date: Optional[date] = None      # When event was coded

    @property
    def precision(self) -> str:
        """Determine temporal precision level."""
        if self.day:
            return "day"
        elif self.month:
            return "month"
        elif self.year:
            return "year"
        return "unknown"

    @property
    def has_range(self) -> bool:
        """Check if event has a date range."""
        return (self.day_span is not None and self.day_span > 1) or \
               (self.julian_start_date is not None and self.julian_end_date is not None)

    @property
    def calendar_date(self) -> Optional[date]:
        """Get calendar date if available."""
        if self.year and self.month and self.day:
            try:
                return date(self.year, self.month, self.day)
            except ValueError:
                return None
        return None

    @property
    def display_date(self) -> str:
        """Get human-readable date string."""
        if self.calendar_date:
            return self.calendar_date.isoformat()
        elif self.year and self.month:
            return f"{self.year}-{self.month:02d}"
        elif self.year:
            return str(self.year)
        return "Unknown date"

    def __repr__(self) -> str:
        return f"TemporalInfo(date='{self.display_date}', precision='{self.precision}')"


@dataclass
class Impact:
    """
    Event impact and consequences.

    Captures casualties, damage, and other measurable outcomes.
    """
    killed_participants: Optional[int] = None # N_KILLED_P
    killed_armed: Optional[int] = None        # N_KILLED_A
    injured: Optional[int] = None             # N_INJURD
    injured_detailed: Optional[int] = None    # N_INJURD_D
    arrests: Optional[int] = None
    property_damaged: Optional[int] = None
    property_owner: Optional[str] = None
    victim_effect: Optional[str] = None

    @property
    def has_casualties(self) -> bool:
        """Check if there were casualties."""
        return (self.killed_participants and self.killed_participants > 0) or \
               (self.killed_armed and self.killed_armed > 0) or \
               (self.injured and self.injured > 0)

    @property
    def total_killed(self) -> int:
        """Get total killed count."""
        return (self.killed_participants or 0) + (self.killed_armed or 0)

    @property
    def total_injured(self) -> int:
        """Get total injured count."""
        return max(self.injured or 0, self.injured_detailed or 0)

    def __repr__(self) -> str:
        casualties = f"killed={self.total_killed}, injured={self.total_injured}"
        return f"Impact({casualties})"


@dataclass
class Event:
    """
    Core SPEED event model.

    Represents a single historical event with all associated data including
    actors, location, temporal information, and impact.
    """
    event_id: str  # Unique identifier (e.g., EID40124)
    temporal: TemporalInfo
    event_type: Optional[int] = None       # EV_TYPE (1-5)
    pe_type: Optional[int] = None          # Political expression type
    atk_type: Optional[int] = None         # Attack type
    dsa_type: Optional[int] = None         # Destabilizing state act type
    news_source: Optional[str] = None      # NEWS_SOURCE (NYT, WSJ)
    article_id: Optional[str] = None       # aid

    # Actors
    initiator: Optional[Actor] = None
    target: Optional[Actor] = None
    victim: Optional[Actor] = None

    # Location
    location: Optional[Location] = None

    # Impact
    impact: Optional[Impact] = None

    # Event characteristics
    is_quasi_event: bool = False          # QUASI_EVENT
    is_state_action: bool = False         # STAT_ACT
    is_coup: bool = False                 # coup
    is_coup_failed: bool = False          # COUP_FAILED

    # Linkages
    is_linked: bool = False               # linked (0/1)
    link_type: Optional[int] = None       # LINK_TYPE
    linked_from: List[str] = field(default_factory=list)  # FROM_EID
    linked_to: List[str] = field(default_factory=list)    # TO_EID
    is_posthoc: bool = False              # posthoc

    # Motivation/context (sparse fields stored as properties)
    properties: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_actors(self) -> bool:
        """Check if event has any actors."""
        return any([self.initiator, self.target, self.victim])

    @property
    def actor_count(self) -> int:
        """Count number of actors involved."""
        return sum(1 for actor in [self.initiator, self.target, self.victim] if actor)

    @property
    def is_violent(self) -> bool:
        """Check if event is categorized as violent (type 2 or has casualties)."""
        return (self.event_type == 2) or \
               (self.impact is not None and self.impact.has_casualties)

    @property
    def has_location(self) -> bool:
        """Check if event has location information."""
        return self.location is not None

    @property
    def event_date(self) -> Optional[date]:
        """Get event date if available."""
        return self.temporal.calendar_date if self.temporal else None

    @property
    def display_summary(self) -> str:
        """Get brief event summary for display."""
        actors = []
        if self.initiator:
            actors.append(f"Init: {self.initiator.primary_name}")
        if self.target:
            actors.append(f"Tgt: {self.target.primary_name}")

        actor_str = ", ".join(actors) if actors else "Unknown actors"
        date_str = self.temporal.display_date if self.temporal else "Unknown date"
        loc_str = self.location.display_name if self.location else "Unknown location"

        return f"{self.event_id}: {actor_str} at {loc_str} on {date_str}"

    def add_motivation_property(self, key: str, value: Any):
        """Add a motivation or context property."""
        if value is not None:
            self.properties[key] = value

    def get_all_linked_events(self) -> List[str]:
        """Get all linked event IDs (both from and to)."""
        return self.linked_from + self.linked_to

    def __repr__(self) -> str:
        return f"Event(id='{self.event_id}', date='{self.temporal.display_date if self.temporal else 'N/A'}')"


# Event type constants from SPEED codebook
EVENT_TYPE_POLITICAL_EXPRESSION = 1
EVENT_TYPE_POLITICALLY_MOTIVATED_ATTACK = 2
EVENT_TYPE_DESTABILIZING_STATE_ACT = 4
EVENT_TYPE_OTHER = 5

EVENT_TYPES = {
    1: "Political expression",
    2: "Politically motivated attacks",
    4: "Destabilizing state acts",
    5: "Other"
}
