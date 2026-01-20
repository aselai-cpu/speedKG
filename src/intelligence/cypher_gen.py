"""
Cypher Query Generator

Generates Cypher queries from natural language using Claude with few-shot prompting.
Includes schema context and security validation.
"""

import logging
import re
from typing import Tuple, Optional
from anthropic import Anthropic, APIError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.intelligence.state import QueryIntent
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class CypherGenerator:
    """Generates Cypher queries from natural language."""

    SCHEMA_DESCRIPTION = """
# Neo4j Schema for SPEED-CAMEO Knowledge Graph

## Node Types

**Event**: Historical conflict/mediation events
- Properties: eventId (unique), year, month, day, eventType, peType, atkType, dsaType, newsSource, articleId, isCoup, isLinked, propertiesJson
- Temporal: julianStartDate, julianEndDate, daySpan
- Flags: isQuasiEvent, isStateAction, isCoupFailed, isPosthoc

**Actor**: People, groups, organizations involved in events
- Properties: actorId (unique), name, cameoCode, actorType, governmentType, governmentLevel, isKnown, ambiguity, numParticipants, numArmed, humanIndicator

**Location**: Geographic locations
- Properties: locationId (unique), name, country, latitude, longitude, locationType, region, cowCode, pinpoint

**EventType**: CAMEO event classification hierarchy
- Properties: cameoCode (unique), label, level (1-4), category

**CAMEOActorType**: CAMEO actor classification
- Properties: code (unique), description, countryCode, actorTypeCode, isTemporallyRestricted, validFrom, validUntil

## Relationships

- (Event)-[:INITIATED_BY {actorType, governmentType, ambiguity}]->(Actor)
- (Event)-[:TARGETED {actorType, governmentType}]->(Actor)
- (Event)-[:VICTIMIZED {actorType, governmentType}]->(Actor)
- (Event)-[:OCCURRED_AT]->(Location)
- (Event)-[:OF_TYPE]->(EventType)
- (Event)-[:LINKED_TO {linkType, direction}]->(Event)
- (EventType)-[:PARENT_TYPE]->(EventType)

## Key Patterns

**Temporal Queries**: Use e.year, e.month, e.day for filtering
**Actor Queries**: Match through INITIATED_BY, TARGETED, or VICTIMIZED relationships
**Location Queries**: Use OCCURRED_AT relationship, filter by l.country or l.region
**Event Chains**: Follow LINKED_TO relationships
**Aggregations**: Use count(), collect() for pattern analysis
**Always add LIMIT**: Add LIMIT clause if not specified (default 100 for lists, 10 for examples)
"""

    FEW_SHOT_EXAMPLES = """
# Example Queries

**Example 1: Single Event Query**
User: "What happened in event EID12345?"
Intent: single_event
Cypher:
```
MATCH (e:Event {eventId: 'EID12345'})
OPTIONAL MATCH (e)-[:INITIATED_BY]->(ini:Actor)
OPTIONAL MATCH (e)-[:TARGETED]->(tar:Actor)
OPTIONAL MATCH (e)-[:OCCURRED_AT]->(l:Location)
RETURN e.eventId, e.year, e.month, e.day, e.eventType,
       ini.name as initiator, tar.name as target,
       l.name as location, l.country
```

**Example 2: Actor Analysis**
User: "What actions did Palestinian Arabs take in 2003?"
Intent: actor_analysis
Cypher:
```
MATCH (a:Actor {name: 'Palestinian Arab'})<-[:INITIATED_BY]-(e:Event)
WHERE e.year = 2003
RETURN e.eventId, e.year, e.month, e.day, e.eventType, e.newsSource
ORDER BY e.year, e.month, e.day
LIMIT 100
```

**Example 3: Temporal Analysis**
User: "How many protests occurred each year between 2000 and 2005?"
Intent: temporal_analysis
Cypher:
```
MATCH (e:Event)
WHERE e.year >= 2000 AND e.year <= 2005
  AND e.eventType IN [14, 15]  // Protest event types
RETURN e.year, count(e) as event_count
ORDER BY e.year
```

**Example 4: Geographic Analysis**
User: "What events occurred in Palestine?"
Intent: geographic_analysis
Cypher:
```
MATCH (e:Event)-[:OCCURRED_AT]->(l:Location)
WHERE l.country = 'Palestine' OR l.name CONTAINS 'Palestine'
RETURN e.eventId, e.year, e.month, e.day, e.eventType,
       l.name, l.country
ORDER BY e.year DESC, e.month DESC, e.day DESC
LIMIT 100
```

**Example 5: Event Chain**
User: "What events were linked to the coup in Chile?"
Intent: event_chain
Cypher:
```
MATCH (e:Event)
WHERE e.isCoup = true
  AND (e)-[:OCCURRED_AT]->(:Location {country: 'Chile'})
OPTIONAL MATCH (e)-[:LINKED_TO*1..2]-(linked:Event)
RETURN e.eventId, e.year, linked.eventId as linked_event,
       linked.year as linked_year
LIMIT 50
```

**Example 6: Pattern Analysis**
User: "What are the top 5 most active actors?"
Intent: pattern_analysis
Cypher:
```
MATCH (a:Actor)<-[:INITIATED_BY]-(e:Event)
RETURN a.name, count(e) as event_count
ORDER BY event_count DESC
LIMIT 5
```

**Example 7: Actor Relationships**
User: "Which actors did Hamas target most frequently?"
Intent: actor_analysis
Cypher:
```
MATCH (ini:Actor {name: 'Hamas'})<-[:INITIATED_BY]-(e:Event)-[:TARGETED]->(tar:Actor)
RETURN tar.name, count(e) as target_count
ORDER BY target_count DESC
LIMIT 10
```

**Example 8: Temporal Trend**
User: "Show me protest trends over time"
Intent: temporal_analysis
Cypher:
```
MATCH (e:Event)
WHERE e.eventType IN [14, 15]
RETURN e.year, count(e) as protest_count
ORDER BY e.year
```
"""

    SECURITY_RULES = """
# Security Rules
- NEVER use DELETE, REMOVE, DROP, DETACH, SET, CREATE, MERGE statements
- Only use MATCH, OPTIONAL MATCH, RETURN, WHERE, ORDER BY, LIMIT
- Validate all inputs to prevent injection
- Always add LIMIT clause (max 1000)
"""

    def __init__(self, anthropic_api_key: str = None, model: str = None):
        """
        Initialize Cypher generator.

        Args:
            anthropic_api_key: Anthropic API key (defaults to config)
            model: Claude model to use (defaults to config)
        """
        config = get_config()
        self.client = Anthropic(api_key=anthropic_api_key or config.ANTHROPIC_API_KEY)
        self.model = model or config.CLAUDE_MODEL

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Cypher generation attempt {retry_state.attempt_number} failed, retrying..."
        )
    )
    def _call_claude_api(self, system_prompt: str, user_message: str) -> any:
        """
        Call Claude API with retry logic.

        Args:
            system_prompt: System prompt for context
            user_message: User message to send

        Returns:
            Claude API response
        """
        return self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

    def generate(self, query: str, intent: QueryIntent) -> Tuple[str, bool, Optional[str]]:
        """
        Generate Cypher query from natural language.

        Args:
            query: User query in natural language
            intent: Classified query intent

        Returns:
            Tuple of (cypher_query, is_valid, error_message)
        """
        logger.info(f"Generating Cypher for query: {query[:100]}... (intent: {intent.value})")

        system_prompt = f"""{self.SCHEMA_DESCRIPTION}

{self.FEW_SHOT_EXAMPLES}

{self.SECURITY_RULES}

Generate a Cypher query for the user's question. Return ONLY the Cypher query without any explanation, markdown formatting, or backticks.

The query intent is: {intent.value}
"""

        try:
            response = self._call_claude_api(
                system_prompt,
                f"Generate a Cypher query for: {query}"
            )

            cypher = response.content[0].text.strip()

            # Remove markdown code blocks if present
            cypher = re.sub(r'^```(cypher)?\n?', '', cypher)
            cypher = re.sub(r'\n?```$', '', cypher)
            cypher = cypher.strip()

            logger.debug(f"Generated Cypher:\n{cypher}")

            # Validate security
            is_valid, error = self._validate_security(cypher)
            if not is_valid:
                logger.error(f"Security validation failed: {error}")
                return cypher, False, error

            # Auto-add LIMIT if missing
            if 'LIMIT' not in cypher.upper():
                cypher = cypher.rstrip(';') + '\nLIMIT 100'
                logger.info("Added default LIMIT 100")

            logger.info("Cypher generation successful")
            return cypher, True, None

        except Exception as e:
            logger.error(f"Cypher generation failed: {e}", exc_info=True)
            return "", False, str(e)

    def _validate_security(self, cypher: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Cypher query for security issues.

        Args:
            cypher: Cypher query to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        cypher_upper = cypher.upper()

        # Check for destructive operations
        forbidden_keywords = ['DELETE', 'REMOVE', 'DROP', 'DETACH DELETE', 'SET', 'CREATE', 'MERGE']
        for keyword in forbidden_keywords:
            if keyword in cypher_upper:
                return False, f"Forbidden operation: {keyword}"

        # Check for excessive LIMIT
        limit_match = re.search(r'LIMIT\s+(\d+)', cypher_upper)
        if limit_match:
            limit = int(limit_match.group(1))
            if limit > 1000:
                return False, f"LIMIT too high: {limit} (max 1000)"

        return True, None


def main():
    """Test Cypher generator."""
    generator = CypherGenerator()

    test_cases = [
        ("What happened in event EID12345?", QueryIntent.SINGLE_EVENT),
        ("What actions did Hamas take in 2003?", QueryIntent.ACTOR_ANALYSIS),
        ("How many protests occurred each year?", QueryIntent.TEMPORAL_ANALYSIS),
        ("What events occurred in Palestine?", QueryIntent.GEOGRAPHIC_ANALYSIS),
        ("What are the top 5 most active actors?", QueryIntent.PATTERN_ANALYSIS),
    ]

    print("\nCypher Generation Tests\n" + "=" * 80)
    for query, intent in test_cases:
        print(f"\nQuery: {query}")
        print(f"Intent: {intent.value}")
        cypher, is_valid, error = generator.generate(query, intent)
        if is_valid:
            print(f"Cypher:\n{cypher}")
        else:
            print(f"ERROR: {error}")
        print("-" * 80)


if __name__ == "__main__":
    main()
