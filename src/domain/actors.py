"""
Actor domain logic and utilities.

Provides helper functions for working with actors, including:
- Actor identification and normalization
- Government/non-government classification
- Actor name generation
"""

import hashlib
from typing import Optional
from src.domain.events import Actor, ActorRole


def generate_actor_id(actor_name: str) -> str:
    """
    Generate a stable, unique actor ID from actor name.

    Uses MD5 hash of normalized name to create consistent IDs
    for the same actor across multiple events.

    Args:
        actor_name: Actor name to generate ID from

    Returns:
        Actor ID in format ACTOR_XXXXXXXXXXXX
    """
    if not actor_name:
        return "ACTOR_UNKNOWN"

    # Normalize name (lowercase, strip whitespace)
    normalized = actor_name.lower().strip()

    # Generate hash
    hash_value = hashlib.md5(normalized.encode('utf-8')).hexdigest()[:12].upper()

    return f"ACTOR_{hash_value}"


def normalize_actor_name(name: Optional[str]) -> Optional[str]:
    """
    Normalize actor name for consistency.

    Args:
        name: Raw actor name from CSV

    Returns:
        Normalized name or None
    """
    if not name or name in ['.', '', 'nan', 'NaN']:
        return None

    # Remove extra whitespace
    normalized = ' '.join(name.split())

    # Title case for readability
    normalized = normalized.title()

    return normalized


def is_government_actor(actor: Actor) -> bool:
    """
    Check if actor is a government entity.

    Args:
        actor: Actor instance

    Returns:
        True if government actor
    """
    return actor.is_government


def is_armed_actor(actor: Actor) -> bool:
    """
    Check if actor has armed participants.

    Args:
        actor: Actor instance

    Returns:
        True if actor has armed participants
    """
    return actor.num_armed is not None and actor.num_armed > 0


def get_actor_description(actor: Actor) -> str:
    """
    Get human-readable actor description.

    Args:
        actor: Actor instance

    Returns:
        Description string
    """
    parts = []

    # Name
    name = actor.primary_name or "Unknown Actor"
    parts.append(name)

    # Role
    parts.append(f"({actor.role.value})")

    # Type
    if actor.is_government:
        parts.append("[Government]")
    elif actor.is_non_government:
        parts.append("[Non-Government]")

    # Armed status
    if actor.num_armed:
        parts.append(f"Armed: {actor.num_armed}")

    return " ".join(parts)


def classify_actor_type(actor: Actor) -> str:
    """
    Classify actor into broad categories.

    Args:
        actor: Actor instance

    Returns:
        Classification string
    """
    if actor.is_government:
        if actor.government_level == 4:
            return "national_government"
        elif actor.government_level == 3:
            return "regional_government"
        elif actor.government_level in [1, 2]:
            return "local_government"
        return "government_unspecified"

    elif actor.is_non_government:
        if actor.non_gov_type:
            # Map to general categories (simplified)
            if actor.non_gov_type in range(1, 10):
                return "political_organization"
            elif actor.non_gov_type in range(10, 20):
                return "armed_group"
            elif actor.non_gov_type in range(20, 30):
                return "civil_society"
            else:
                return "other_non_government"
        return "non_government_unspecified"

    return "unknown"


def merge_actor_info(actors: list[Actor]) -> dict:
    """
    Merge information from multiple actor instances (same entity in different events).

    Args:
        actors: List of Actor instances for the same entity

    Returns:
        Dictionary with merged actor information
    """
    if not actors:
        return {}

    # Use most common or most recent values
    merged = {
        "names": list({a.primary_name for a in actors if a.primary_name}),
        "roles": list({a.role.value for a in actors}),
        "is_government": any(a.is_government for a in actors),
        "is_non_government": any(a.is_non_government for a in actors),
        "total_appearances": len(actors),
    }

    # Aggregate numeric fields
    merged["total_armed"] = sum(a.num_armed or 0 for a in actors)
    merged["total_participants"] = sum(a.num_participants or 0 for a in actors)

    return merged


# Government type mappings (from SPEED codebook)
GOVERNMENT_TYPES = {
    1: "Executive",
    2: "Legislature",
    3: "Judiciary",
    4: "Police",
    5: "Military",
    6: "Intelligence",
    7: "Bureaucracy",
    8: "Political party",
    9: "Election commission",
    10: "State media",
    11: "State-owned enterprise",
    12: "Local government",
    13: "Regional government",
    14: "National government",
    15: "Former government",
    16: "Government coalition",
    17: "Government supporter",
    18: "Pro-government militia",
    19: "Government in exile",
    20: "Transitional government",
    21: "Government delegate",
    22: "Government spokesperson",
    23: "Other government"
}

# Non-government type mappings
NON_GOVERNMENT_TYPES = {
    1: "Political opposition",
    2: "Armed opposition",
    3: "Rebel group",
    4: "Insurgent group",
    5: "Guerrilla group",
    6: "Paramilitary group",
    7: "Militia",
    8: "Terrorist group",
    9: "Separatist group",
    10: "Civil society organization",
    11: "NGO",
    12: "Religious organization",
    13: "Labor union",
    14: "Student group",
    15: "Women's group",
    16: "Business association",
    17: "Professional association",
    18: "Community organization",
    19: "Ethnic group",
    20: "Tribal group",
    21: "Clan",
    22: "Family",
    23: "Individual",
    24: "Protesters",
    25: "Demonstrators",
    26: "Rioters",
    27: "Strikers",
    28: "Refugees",
    29: "Displaced persons",
    30: "Civilians",
    31: "Media",
    32: "Academic institution",
    33: "Think tank",
    34: "International organization",
    35: "Foreign government",
    36: "Criminal organization",
    37: "Other non-government"
}


def get_government_type_name(type_code: Optional[int]) -> Optional[str]:
    """Get government type name from code."""
    return GOVERNMENT_TYPES.get(type_code) if type_code else None


def get_non_government_type_name(type_code: Optional[int]) -> Optional[str]:
    """Get non-government type name from code."""
    return NON_GOVERNMENT_TYPES.get(type_code) if type_code else None
