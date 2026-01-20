"""
Intent Classifier

Classifies user queries into intent categories for adaptive retrieval.
Uses Claude to analyze queries and determine the best retrieval strategy.
"""

import logging
from typing import Tuple
from anthropic import Anthropic, APIError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.intelligence.state import QueryIntent
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classifies user queries into intent categories."""

    SYSTEM_PROMPT = """You are an expert at analyzing user queries about historical conflict and mediation events.

Your task is to classify queries into one of these intent categories:

1. **single_event**: Query asks about a specific event or small set of events
   - Example: "What happened in event EID12345?"
   - Example: "Tell me about the protest in Cairo on January 25, 2011"

2. **event_chain**: Query asks about sequences of linked events or event progressions
   - Example: "What events led to the coup in Chile?"
   - Example: "Show me the chain of events after the assassination"

3. **actor_analysis**: Query focuses on actors (people, groups, organizations) and their activities
   - Example: "What actions did Hamas take in 2003?"
   - Example: "Which actors were most active in Lebanon?"

4. **pattern_analysis**: Query asks about patterns, trends, or comparisons across many events
   - Example: "What are the most common types of protests?"
   - Example: "Compare violent vs non-violent events"

5. **temporal_analysis**: Query focuses on time-based trends or temporal patterns
   - Example: "How did protest activity change over time?"
   - Example: "What happened in the Middle East between 1990 and 2000?"

6. **geographic_analysis**: Query focuses on geographic patterns or specific locations
   - Example: "What events occurred in Palestine?"
   - Example: "Compare conflict patterns between regions"

Respond with ONLY the intent category name (single_event, event_chain, actor_analysis, pattern_analysis, temporal_analysis, or geographic_analysis) and a confidence score (0.0-1.0) in this format:

intent: <category>
confidence: <score>

If the query is ambiguous, choose the most likely intent and lower the confidence score."""

    def __init__(self, anthropic_api_key: str = None, model: str = None):
        """
        Initialize intent classifier.

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
            f"Intent classification attempt {retry_state.attempt_number} failed, retrying..."
        )
    )
    def _call_claude_api(self, query: str) -> any:
        """
        Call Claude API with retry logic.

        Args:
            query: User query string

        Returns:
            Claude API response
        """
        return self.client.messages.create(
            model=self.model,
            max_tokens=200,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": query}
            ]
        )

    def classify(self, query: str) -> Tuple[QueryIntent, float]:
        """
        Classify a user query into an intent category.

        Args:
            query: User query string

        Returns:
            Tuple of (intent, confidence_score)
        """
        logger.info(f"Classifying query intent: {query[:100]}...")

        try:
            response = self._call_claude_api(query)

            # Parse response
            content = response.content[0].text.strip()
            logger.debug(f"Intent classification response: {content}")

            # Extract intent and confidence
            intent_str = None
            confidence = 0.8  # Default confidence

            for line in content.split('\n'):
                line = line.strip().lower()
                if line.startswith('intent:'):
                    intent_str = line.split('intent:')[1].strip()
                elif line.startswith('confidence:'):
                    try:
                        confidence = float(line.split('confidence:')[1].strip())
                    except ValueError:
                        logger.warning(f"Could not parse confidence: {line}")

            # Map to QueryIntent enum
            if not intent_str:
                logger.warning("No intent found in response, defaulting to pattern_analysis")
                return QueryIntent.PATTERN_ANALYSIS, 0.5

            intent_map = {
                'single_event': QueryIntent.SINGLE_EVENT,
                'event_chain': QueryIntent.EVENT_CHAIN,
                'actor_analysis': QueryIntent.ACTOR_ANALYSIS,
                'pattern_analysis': QueryIntent.PATTERN_ANALYSIS,
                'temporal_analysis': QueryIntent.TEMPORAL_ANALYSIS,
                'geographic_analysis': QueryIntent.GEOGRAPHIC_ANALYSIS,
            }

            intent = intent_map.get(intent_str)
            if not intent:
                logger.warning(f"Unknown intent: {intent_str}, defaulting to pattern_analysis")
                return QueryIntent.PATTERN_ANALYSIS, 0.5

            logger.info(f"Classified as {intent.value} with confidence {confidence:.2f}")
            return intent, confidence

        except Exception as e:
            logger.error(f"Intent classification failed: {e}", exc_info=True)
            # Default to pattern_analysis with low confidence
            return QueryIntent.PATTERN_ANALYSIS, 0.5


def main():
    """Test intent classifier."""
    classifier = IntentClassifier()

    test_queries = [
        "What happened in event EID12345?",
        "What events led to the coup in Chile?",
        "What actions did Hamas take in 2003?",
        "What are the most common types of protests?",
        "How did protest activity change over time?",
        "What events occurred in Palestine?",
    ]

    print("\nIntent Classification Tests\n" + "=" * 60)
    for query in test_queries:
        intent, confidence = classifier.classify(query)
        print(f"\nQuery: {query}")
        print(f"Intent: {intent.value}")
        print(f"Confidence: {confidence:.2f}")
        print("-" * 60)


if __name__ == "__main__":
    main()
