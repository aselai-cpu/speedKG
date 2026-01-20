"""
LangGraph Intelligence Agent

Orchestrates the query processing workflow using LangGraph.
Workflow: Parse Intent → Generate Cypher → Execute → Retrieve Subgraph → Reason → Respond
"""

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from neo4j import GraphDatabase

from src.intelligence.state import AgentState, QueryIntent
from src.intelligence.intent_classifier import IntentClassifier
from src.intelligence.cypher_gen import CypherGenerator
from src.intelligence.graph_retrieval import SubgraphRetriever
from src.intelligence.reasoning import ClaudeReasoner
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class IntelligenceAgent:
    """
    LangGraph-based intelligence agent for SPEED-CAMEO knowledge graph.

    Workflow nodes:
    1. parse_intent: Classify query intent
    2. generate_cypher: Generate Cypher from natural language
    3. execute_query: Execute Cypher and retrieve subgraph
    4. reason: Use Claude to analyze and respond
    5. format_response: Format final response
    """

    def __init__(self, neo4j_uri: str = None, neo4j_user: str = None,
                 neo4j_password: str = None, anthropic_api_key: str = None):
        """
        Initialize intelligence agent.

        Args:
            neo4j_uri: Neo4j connection URI (defaults to config)
            neo4j_user: Neo4j username (defaults to config)
            neo4j_password: Neo4j password (defaults to config)
            anthropic_api_key: Anthropic API key (defaults to config)
        """
        config = get_config()

        # Initialize components
        self.intent_classifier = IntentClassifier(anthropic_api_key=anthropic_api_key)
        self.cypher_generator = CypherGenerator(anthropic_api_key=anthropic_api_key)
        self.reasoner = ClaudeReasoner(anthropic_api_key=anthropic_api_key)

        # Neo4j connection
        self.driver = GraphDatabase.driver(
            neo4j_uri or config.NEO4J_URI,
            auth=(neo4j_user or config.NEO4J_USER, neo4j_password or config.NEO4J_PASSWORD)
        )
        self.retriever = SubgraphRetriever(self.driver)

        # Build LangGraph workflow
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("parse_intent", self._parse_intent)
        workflow.add_node("generate_cypher", self._generate_cypher)
        workflow.add_node("execute_query", self._execute_query)
        workflow.add_node("reason", self._reason)
        workflow.add_node("handle_error", self._handle_error)

        # Define edges
        workflow.set_entry_point("parse_intent")
        workflow.add_edge("parse_intent", "generate_cypher")

        # Conditional edge from generate_cypher
        workflow.add_conditional_edges(
            "generate_cypher",
            self._should_execute_or_error,
            {
                "execute": "execute_query",
                "error": "handle_error"
            }
        )

        workflow.add_edge("execute_query", "reason")
        workflow.add_edge("reason", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    def _should_execute_or_error(self, state: AgentState) -> str:
        """Decision function: execute query or handle error."""
        if state.cypher_valid:
            return "execute"
        else:
            return "error"

    def query(self, user_query: str, session_id: str = None) -> Dict[str, Any]:
        """
        Process a user query through the agent workflow.

        Args:
            user_query: Natural language query
            session_id: Optional session identifier

        Returns:
            Agent state as dictionary
        """
        logger.info(f"Processing query: {user_query[:100]}...")

        # Initialize state
        initial_state = AgentState(
            user_query=user_query,
            session_id=session_id
        )

        try:
            # Run through workflow
            final_state = self.graph.invoke(initial_state)

            # LangGraph may return dict or AgentState depending on version
            if isinstance(final_state, dict):
                # Calculate duration manually
                if 'start_time' in final_state and final_state['start_time']:
                    from datetime import datetime
                    duration = (datetime.now() - final_state['start_time']).total_seconds() * 1000
                    logger.info(f"Query processed in {duration:.0f}ms")
                return final_state
            else:
                # It's an AgentState object
                logger.info(f"Query processed in {final_state.get_total_duration_ms():.0f}ms")
                return final_state.to_dict()

        except Exception as e:
            logger.error(f"Query processing failed: {e}", exc_info=True)
            initial_state.error = str(e)
            initial_state.add_trace("error", {"error": str(e)}, success=False, error=str(e))
            return initial_state.to_dict()

    # Workflow node implementations

    def _parse_intent(self, state: AgentState) -> AgentState:
        """Node: Parse query intent."""
        state.add_trace("parse_intent", {"query": state.user_query})

        try:
            intent, confidence = self.intent_classifier.classify(state.user_query)
            state.intent = intent
            state.intent_confidence = confidence

            state.add_trace("parse_intent_complete", {
                "intent": intent.value,
                "confidence": confidence
            })
            logger.info(f"Intent: {intent.value} (confidence: {confidence:.2f})")

        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            state.intent = QueryIntent.PATTERN_ANALYSIS  # Default fallback
            state.intent_confidence = 0.5
            state.add_trace("parse_intent_error", {"error": str(e)}, success=False)

        return state

    def _generate_cypher(self, state: AgentState) -> AgentState:
        """Node: Generate Cypher query."""
        state.add_trace("generate_cypher", {
            "intent": state.intent.value,
            "query": state.user_query
        })

        try:
            cypher, is_valid, error = self.cypher_generator.generate(
                state.user_query,
                state.intent
            )

            state.cypher_query = cypher
            state.cypher_valid = is_valid
            state.cypher_error = error
            state.cypher_attempts += 1

            state.add_trace("generate_cypher_complete", {
                "cypher": cypher,
                "valid": is_valid,
                "error": error
            }, success=is_valid, error=error)

            logger.info(f"Cypher generated: valid={is_valid}")

        except Exception as e:
            logger.error(f"Cypher generation failed: {e}")
            state.cypher_valid = False
            state.cypher_error = str(e)
            state.add_trace("generate_cypher_error", {"error": str(e)}, success=False, error=str(e))

        return state

    def _execute_query(self, state: AgentState) -> AgentState:
        """Node: Execute Cypher query and retrieve subgraph."""
        state.add_trace("execute_query", {"cypher": state.cypher_query})

        try:
            query_results, subgraph = self.retriever.retrieve(
                state.cypher_query,
                state.intent
            )

            state.query_results = query_results
            state.result_count = len(query_results)
            state.subgraph = subgraph
            state.subgraph_nodes = subgraph.get('node_count', 0)
            state.subgraph_relationships = subgraph.get('relationship_count', 0)

            state.add_trace("execute_query_complete", {
                "result_count": state.result_count,
                "subgraph_nodes": state.subgraph_nodes,
                "subgraph_relationships": state.subgraph_relationships
            })

            logger.info(f"Query executed: {state.result_count} results, "
                       f"{state.subgraph_nodes} nodes, {state.subgraph_relationships} relationships")

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            state.error = str(e)
            state.add_trace("execute_query_error", {"error": str(e)}, success=False, error=str(e))

        return state

    def _reason(self, state: AgentState) -> AgentState:
        """Node: Reason over subgraph and generate response."""
        state.add_trace("reason", {
            "result_count": state.result_count,
            "subgraph_nodes": state.subgraph_nodes
        })

        try:
            # Format subgraph for LLM
            subgraph_text = self.retriever.format_subgraph_for_llm(
                state.subgraph,
                state.query_results
            )

            # Generate reasoning
            response, citations, tokens = self.reasoner.reason(
                state.user_query,
                subgraph_text,
                state.cypher_query
            )

            state.reasoning = response
            state.final_response = response
            state.citations = citations
            state.total_tokens = tokens

            state.add_trace("reason_complete", {
                "response_length": len(response),
                "citations": len(citations),
                "tokens": tokens
            })

            logger.info(f"Reasoning complete: {len(response)} chars, {len(citations)} citations, {tokens} tokens")

        except Exception as e:
            logger.error(f"Reasoning failed: {e}")
            state.error = str(e)
            state.final_response = f"I encountered an error while analyzing the data: {str(e)}"
            state.add_trace("reason_error", {"error": str(e)}, success=False, error=str(e))

        return state

    def _handle_error(self, state: AgentState) -> AgentState:
        """Node: Handle errors."""
        state.add_trace("handle_error", {
            "cypher_error": state.cypher_error,
            "error": state.error
        })

        error_msg = state.cypher_error or state.error or "Unknown error occurred"
        state.final_response = f"I encountered an error processing your query: {error_msg}"

        logger.error(f"Error handled: {error_msg}")
        return state

    def close(self):
        """Close Neo4j connection."""
        self.driver.close()
        logger.info("Agent closed")


def main():
    """Test the intelligence agent."""
    agent = IntelligenceAgent()

    test_queries = [
        "What are the top 5 most active actors?",
        "What events occurred in Palestine in 2003?",
        "How many protests occurred each year?",
    ]

    print("\n" + "=" * 80)
    print("INTELLIGENCE AGENT TEST")
    print("=" * 80)

    for query in test_queries:
        print(f"\n\nQuery: {query}")
        print("-" * 80)

        result = agent.query(query)

        print(f"Intent: {result['intent']} (confidence: {result['intent_confidence']:.2f})")
        print(f"Cypher Valid: {result['cypher_valid']}")
        print(f"Results: {result['result_count']} records")
        print(f"Subgraph: {result['subgraph_nodes']} nodes, {result['subgraph_relationships']} relationships")
        print(f"Duration: {result['total_duration_ms']:.0f}ms")
        print(f"\nResponse:\n{result['final_response'][:500]}...")
        print(f"\nCitations: {result['citations'][:5]}")

    agent.close()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
