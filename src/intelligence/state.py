"""
Agent State Models

Defines the state structure for the LangGraph agent workflow.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class QueryIntent(str, Enum):
    """Types of query intents for adaptive retrieval."""
    SINGLE_EVENT = "single_event"  # Query about a specific event
    EVENT_CHAIN = "event_chain"  # Query about linked events or sequences
    ACTOR_ANALYSIS = "actor_analysis"  # Query about actors and their activities
    PATTERN_ANALYSIS = "pattern_analysis"  # Query about patterns, trends, aggregations
    TEMPORAL_ANALYSIS = "temporal_analysis"  # Query about time-based trends
    GEOGRAPHIC_ANALYSIS = "geographic_analysis"  # Query about locations


@dataclass
class TraceStep:
    """Single step in the agent execution trace."""
    step_name: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class AgentState:
    """
    State for the LangGraph agent workflow.

    This state is passed through all nodes in the graph and accumulates
    information as the agent processes a query.
    """
    # Input
    user_query: str
    session_id: Optional[str] = None

    # Intent classification
    intent: Optional[QueryIntent] = None
    intent_confidence: float = 0.0

    # Cypher generation
    cypher_query: Optional[str] = None
    cypher_valid: bool = False
    cypher_error: Optional[str] = None
    cypher_attempts: int = 0

    # Query execution
    query_results: Optional[List[Dict[str, Any]]] = None
    result_count: int = 0

    # Subgraph retrieval
    subgraph: Optional[Dict[str, Any]] = None
    subgraph_nodes: int = 0
    subgraph_relationships: int = 0

    # Reasoning
    reasoning: Optional[str] = None
    final_response: Optional[str] = None
    citations: List[str] = field(default_factory=list)

    # Trace and monitoring
    trace: List[TraceStep] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_tokens: int = 0

    # Error handling
    error: Optional[str] = None
    retry_count: int = 0

    def add_trace(self, step_name: str, details: Dict[str, Any] = None,
                  success: bool = True, error: Optional[str] = None):
        """Add a step to the execution trace."""
        step = TraceStep(
            step_name=step_name,
            timestamp=datetime.now(),
            details=details or {},
            success=success,
            error=error
        )

        # Calculate duration from last step
        if self.trace:
            last_step = self.trace[-1]
            duration = (step.timestamp - last_step.timestamp).total_seconds() * 1000
            step.duration_ms = duration

        self.trace.append(step)

    def get_total_duration_ms(self) -> float:
        """Get total execution duration in milliseconds."""
        if not self.end_time:
            self.end_time = datetime.now()
        return (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "user_query": self.user_query,
            "session_id": self.session_id,
            "intent": self.intent.value if self.intent else None,
            "intent_confidence": self.intent_confidence,
            "cypher_query": self.cypher_query,
            "cypher_valid": self.cypher_valid,
            "cypher_error": self.cypher_error,
            "result_count": self.result_count,
            "subgraph_nodes": self.subgraph_nodes,
            "subgraph_relationships": self.subgraph_relationships,
            "final_response": self.final_response,
            "citations": self.citations,
            "trace": [
                {
                    "step": t.step_name,
                    "timestamp": t.timestamp.isoformat(),
                    "duration_ms": t.duration_ms,
                    "success": t.success,
                    "error": t.error,
                    "details": t.details
                }
                for t in self.trace
            ],
            "total_duration_ms": self.get_total_duration_ms(),
            "total_tokens": self.total_tokens,
            "error": self.error
        }
