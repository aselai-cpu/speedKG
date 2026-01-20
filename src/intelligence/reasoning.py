"""
Claude Reasoning

Uses Claude to reason over retrieved subgraphs and generate natural language responses.
"""

import logging
from typing import Tuple, List
from anthropic import Anthropic, APIError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class ClaudeReasoner:
    """Reasons over subgraphs using Claude."""

    SYSTEM_PROMPT = """You are an expert analyst of historical conflict and mediation events from the SPEED dataset (1946-2008).

Your task is to analyze graph data from a Neo4j knowledge graph and answer user questions about historical events, actors, patterns, and trends.

## Dataset Context

**SPEED Dataset**: Social, Political, and Economic Events Database
- Coverage: 62,141 historical events from 1946-2008
- Sources: News articles and historical records
- Focus: Conflicts, protests, coups, government actions, political events

**CAMEO Ontology**: Conflict and Mediation Event Observations
- Event Types: Hierarchical classification (statements, appeals, protests, violence, etc.)
- Actor Codes: Countries, organizations, ethnic groups, political entities
- Relationship Types: Initiators, targets, victims of events

## Analysis Guidelines

1. **Be Specific**: Cite specific event IDs, dates, actors, and locations
2. **Be Accurate**: Only state facts present in the provided data
3. **Be Comprehensive**: Analyze patterns and trends when relevant
4. **Provide Context**: Explain significance and relationships
5. **Acknowledge Limitations**: Note if data is incomplete or limited

## Response Format

Structure your response as follows:

1. **Direct Answer**: Answer the user's question directly and concisely
2. **Supporting Evidence**: Cite specific events, actors, or data points
3. **Analysis**: Provide insights about patterns, trends, or significance
4. **Citations**: List event IDs and key entities referenced

Always include a "Citations" section at the end listing:
- Event IDs mentioned (e.g., EID12345)
- Key actors referenced
- Locations and time periods covered

## Example Response Format

**Answer**: [Direct answer to the question]

**Evidence**: [Specific data points from the subgraph]

**Analysis**: [Insights about patterns, trends, or context]

**Citations**:
- Events: EID12345, EID67890
- Actors: Hamas, Palestinian Arab
- Locations: Gaza, Palestine
- Time Period: 2003-2005
"""

    def __init__(self, anthropic_api_key: str = None, model: str = None):
        """
        Initialize Claude reasoner.

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
            f"Reasoning attempt {retry_state.attempt_number} failed, retrying..."
        )
    )
    def _call_claude_api(self, user_message: str) -> any:
        """
        Call Claude API with retry logic.

        Args:
            user_message: User message containing query and subgraph data

        Returns:
            Claude API response
        """
        return self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

    def reason(self, user_query: str, subgraph_text: str, cypher_query: str = None) -> Tuple[str, List[str], int]:
        """
        Generate reasoning response from subgraph.

        Args:
            user_query: Original user query
            subgraph_text: Formatted subgraph text
            cypher_query: Optional Cypher query used (for context)

        Returns:
            Tuple of (response_text, citations_list, token_count)
        """
        logger.info(f"Generating reasoning for query: {user_query[:100]}...")

        # Build user message
        user_message = f"""User Question: {user_query}

Graph Data Retrieved:
{subgraph_text}
"""

        if cypher_query:
            user_message += f"\n\nCypher Query Used:\n```\n{cypher_query}\n```"

        user_message += "\n\nPlease analyze this data and answer the user's question following the response format guidelines."

        try:
            response = self._call_claude_api(user_message)

            response_text = response.content[0].text.strip()
            token_count = response.usage.input_tokens + response.usage.output_tokens

            logger.info(f"Reasoning complete. Tokens used: {token_count}")
            logger.debug(f"Response length: {len(response_text)} chars")

            # Extract citations
            citations = self._extract_citations(response_text)
            logger.debug(f"Extracted {len(citations)} citations")

            return response_text, citations, token_count

        except Exception as e:
            logger.error(f"Reasoning failed: {e}", exc_info=True)
            error_response = f"I encountered an error while analyzing the data: {str(e)}"
            return error_response, [], 0

    def _extract_citations(self, response: str) -> List[str]:
        """
        Extract citations from response.

        Args:
            response: Response text

        Returns:
            List of citation strings
        """
        citations = []

        # Extract event IDs (EID followed by digits)
        import re
        event_ids = re.findall(r'EID\d+', response)
        citations.extend(event_ids)

        # Extract citations section
        if 'Citations' in response or 'citations' in response:
            lines = response.split('\n')
            in_citations = False
            for line in lines:
                if 'Citations' in line or 'citations' in line:
                    in_citations = True
                    continue
                if in_citations:
                    # Stop at next major section
                    if line.startswith('#') or line.startswith('**'):
                        if 'Citations' not in line:
                            break
                    # Extract citation items
                    if line.strip().startswith('-') or line.strip().startswith('•'):
                        citations.append(line.strip().lstrip('-•').strip())

        # Remove duplicates while preserving order
        seen = set()
        unique_citations = []
        for citation in citations:
            if citation not in seen:
                seen.add(citation)
                unique_citations.append(citation)

        return unique_citations


def main():
    """Test Claude reasoner."""
    reasoner = ClaudeReasoner()

    # Sample subgraph text
    sample_subgraph = """
# Query Results
Found 3 matching records

## Sample Results:

1. eventId: EID12345, year: 2003, initiator: Hamas, target: Israeli Defense Force, location: Gaza

2. eventId: EID12346, year: 2003, initiator: Hamas, target: Israeli Civilian, location: Jerusalem

3. eventId: EID12347, year: 2003, initiator: Hamas, target: Israeli Government, location: West Bank

# Subgraph Context
Total nodes: 15
Total relationships: 18

## Event Nodes (3):
- Event EID12345 (2003)
- Event EID12346 (2003)
- Event EID12347 (2003)

## Actor Nodes (5):
- Actor: Hamas
- Actor: Israeli Defense Force
- Actor: Israeli Civilian
- Actor: Israeli Government
- Actor: Palestinian Arab
"""

    sample_query = "What actions did Hamas take in 2003?"

    print("\nClaude Reasoning Test\n" + "=" * 80)
    print(f"Query: {sample_query}\n")

    response, citations, tokens = reasoner.reason(sample_query, sample_subgraph)

    print(f"Response:\n{response}\n")
    print(f"\nExtracted Citations: {citations}")
    print(f"Tokens Used: {tokens}")
    print("=" * 80)


if __name__ == "__main__":
    main()
