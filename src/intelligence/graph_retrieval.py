"""
Adaptive Subgraph Retrieval

Executes Cypher queries and expands results into subgraphs based on query intent.
Implements intent-specific retrieval strategies.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from neo4j import GraphDatabase, Driver

from src.intelligence.state import QueryIntent

logger = logging.getLogger(__name__)


class SubgraphRetriever:
    """Retrieves and expands subgraphs from Neo4j based on query intent."""

    # Retrieval strategies per intent
    RETRIEVAL_STRATEGIES = {
        QueryIntent.SINGLE_EVENT: {
            'max_hops': 1,
            'max_nodes': 100,
            'relationships': ['INITIATED_BY', 'TARGETED', 'VICTIMIZED', 'OCCURRED_AT', 'OF_TYPE']
        },
        QueryIntent.EVENT_CHAIN: {
            'max_hops': 2,
            'max_nodes': 300,
            'relationships': ['LINKED_TO', 'INITIATED_BY', 'TARGETED', 'OCCURRED_AT']
        },
        QueryIntent.ACTOR_ANALYSIS: {
            'max_hops': 2,
            'max_nodes': 500,
            'relationships': ['INITIATED_BY', 'TARGETED', 'VICTIMIZED', 'OCCURRED_AT']
        },
        QueryIntent.PATTERN_ANALYSIS: {
            'max_hops': 1,
            'max_nodes': 500,
            'relationships': None,  # Aggregation mode, no expansion
            'aggregation_mode': True
        },
        QueryIntent.TEMPORAL_ANALYSIS: {
            'max_hops': 1,
            'max_nodes': 500,
            'relationships': ['OCCURRED_AT'],
            'aggregation_mode': True
        },
        QueryIntent.GEOGRAPHIC_ANALYSIS: {
            'max_hops': 2,
            'max_nodes': 500,
            'relationships': ['OCCURRED_AT', 'INITIATED_BY', 'TARGETED']
        }
    }

    def __init__(self, driver: Driver):
        """
        Initialize subgraph retriever.

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver

    def retrieve(self, cypher: str, intent: QueryIntent) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Execute Cypher query and retrieve subgraph.

        Args:
            cypher: Cypher query to execute
            intent: Query intent for retrieval strategy

        Returns:
            Tuple of (query_results, subgraph_dict)
        """
        logger.info(f"Retrieving subgraph with intent: {intent.value}")
        logger.debug(f"Executing Cypher:\n{cypher}")

        try:
            with self.driver.session() as session:
                # Execute initial query
                result = session.run(cypher)
                records = [record.data() for record in result]

                logger.info(f"Initial query returned {len(records)} records")

                if not records:
                    logger.warning("No results from initial query")
                    return [], self._empty_subgraph()

                # Get retrieval strategy
                strategy = self.RETRIEVAL_STRATEGIES.get(intent, self.RETRIEVAL_STRATEGIES[QueryIntent.PATTERN_ANALYSIS])

                # Check if aggregation mode (no expansion needed)
                if strategy.get('aggregation_mode', False):
                    logger.info("Aggregation mode - no subgraph expansion")
                    return records, self._create_subgraph_from_records(records)

                # Expand subgraph
                subgraph = self._expand_subgraph(session, records, strategy)

                logger.info(f"Subgraph: {subgraph['node_count']} nodes, {subgraph['relationship_count']} relationships")
                return records, subgraph

        except Exception as e:
            logger.error(f"Subgraph retrieval failed: {e}", exc_info=True)
            raise

    def _expand_subgraph(self, session, records: List[Dict], strategy: Dict) -> Dict[str, Any]:
        """
        Expand initial results into a subgraph.

        Args:
            session: Neo4j session
            records: Initial query results
            strategy: Retrieval strategy config

        Returns:
            Subgraph dictionary
        """
        max_hops = strategy['max_hops']
        max_nodes = strategy['max_nodes']
        relationships = strategy.get('relationships')

        # Extract event IDs from initial results
        event_ids = []
        for record in records:
            for key, value in record.items():
                # Look for event ID fields
                if isinstance(value, str) and value.startswith('EID'):
                    event_ids.append(value)
                elif key in ['eventId', 'e.eventId', 'event_id']:
                    event_ids.append(value)

        if not event_ids:
            logger.warning("No event IDs found in results")
            return self._create_subgraph_from_records(records)

        # Remove duplicates
        event_ids = list(set(event_ids))
        logger.debug(f"Expanding from {len(event_ids)} seed events")

        # Build relationship filter
        rel_filter = ""
        if relationships:
            rel_types = "|".join(relationships)
            rel_filter = f":{rel_types}"

        # Expand subgraph query
        expansion_query = f"""
        MATCH (seed:Event)
        WHERE seed.eventId IN $event_ids
        CALL {{
            WITH seed
            MATCH path = (seed)-[r{rel_filter}*0..{max_hops}]-(connected)
            RETURN path
            LIMIT {max_nodes}
        }}
        WITH collect(path) as paths
        CALL {{
            WITH paths
            UNWIND paths as p
            UNWIND nodes(p) as n
            RETURN collect(DISTINCT n) as all_nodes
        }}
        CALL {{
            WITH paths
            UNWIND paths as p
            UNWIND relationships(p) as r
            RETURN collect(DISTINCT r) as all_rels
        }}
        RETURN all_nodes, all_rels
        """

        try:
            result = session.run(expansion_query, event_ids=event_ids)
            record = result.single()

            if not record:
                return self._create_subgraph_from_records(records)

            nodes = record['all_nodes'] if record['all_nodes'] else []
            rels = record['all_rels'] if record['all_rels'] else []

            # Convert to serializable format
            subgraph = {
                'nodes': [self._serialize_node(n) for n in nodes],
                'relationships': [self._serialize_relationship(r) for r in rels],
                'node_count': len(nodes),
                'relationship_count': len(rels),
                'seed_event_count': len(event_ids)
            }

            return subgraph

        except Exception as e:
            logger.error(f"Subgraph expansion failed: {e}", exc_info=True)
            return self._create_subgraph_from_records(records)

    def _serialize_node(self, node) -> Dict[str, Any]:
        """Convert Neo4j node to serializable dict."""
        return {
            'id': node.id,
            'labels': list(node.labels),
            'properties': dict(node)
        }

    def _serialize_relationship(self, rel) -> Dict[str, Any]:
        """Convert Neo4j relationship to serializable dict."""
        return {
            'id': rel.id,
            'type': rel.type,
            'start_node': rel.start_node.id,
            'end_node': rel.end_node.id,
            'properties': dict(rel)
        }

    def _create_subgraph_from_records(self, records: List[Dict]) -> Dict[str, Any]:
        """
        Create a simple subgraph from query records (aggregation mode).

        Args:
            records: Query result records

        Returns:
            Subgraph dictionary
        """
        return {
            'nodes': [],
            'relationships': [],
            'records': records,
            'node_count': 0,
            'relationship_count': 0,
            'aggregation_mode': True
        }

    def _empty_subgraph(self) -> Dict[str, Any]:
        """Return empty subgraph."""
        return {
            'nodes': [],
            'relationships': [],
            'records': [],
            'node_count': 0,
            'relationship_count': 0
        }

    def format_subgraph_for_llm(self, subgraph: Dict[str, Any], query_results: List[Dict[str, Any]]) -> str:
        """
        Format subgraph into readable text for Claude.

        Args:
            subgraph: Subgraph dictionary
            query_results: Initial query results

        Returns:
            Formatted text representation
        """
        if subgraph.get('aggregation_mode'):
            # Format aggregation results
            return self._format_aggregation_results(query_results)

        # Format full subgraph
        sections = []

        # Query results summary
        sections.append("# Query Results\n")
        sections.append(f"Found {len(query_results)} matching records\n")
        if query_results:
            sections.append("\n## Sample Results:\n")
            for i, record in enumerate(query_results[:10], 1):
                sections.append(f"\n{i}. {self._format_record(record)}")

        # Nodes summary
        if subgraph['nodes']:
            sections.append(f"\n\n# Subgraph Context\n")
            sections.append(f"Total nodes: {subgraph['node_count']}")
            sections.append(f"Total relationships: {subgraph['relationship_count']}\n")

            # Group nodes by label
            nodes_by_label = {}
            for node in subgraph['nodes']:
                label = node['labels'][0] if node['labels'] else 'Unknown'
                if label not in nodes_by_label:
                    nodes_by_label[label] = []
                nodes_by_label[label].append(node)

            for label, nodes in nodes_by_label.items():
                sections.append(f"\n## {label} Nodes ({len(nodes)}):\n")
                for node in nodes[:5]:  # Show first 5
                    sections.append(f"- {self._format_node(node)}")

        return "\n".join(sections)

    def _format_aggregation_results(self, results: List[Dict[str, Any]]) -> str:
        """Format aggregation query results."""
        sections = ["# Aggregation Results\n"]

        for i, record in enumerate(results, 1):
            sections.append(f"\n{i}. {self._format_record(record)}")

        return "\n".join(sections)

    def _format_record(self, record: Dict[str, Any]) -> str:
        """Format a single query result record."""
        parts = []
        for key, value in record.items():
            if value is not None:
                parts.append(f"{key}: {value}")
        return ", ".join(parts)

    def _format_node(self, node: Dict[str, Any]) -> str:
        """Format a node for display."""
        props = node['properties']
        label = node['labels'][0] if node['labels'] else 'Node'

        if label == 'Event':
            return f"Event {props.get('eventId', 'N/A')} ({props.get('year', 'N/A')})"
        elif label == 'Actor':
            return f"Actor: {props.get('name', 'N/A')}"
        elif label == 'Location':
            return f"Location: {props.get('name', 'N/A')}, {props.get('country', 'N/A')}"
        else:
            return f"{label}: {str(props)[:100]}"
