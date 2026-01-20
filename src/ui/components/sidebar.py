"""
Sidebar Component

Displays schema information, connection status, and query history.
"""

import streamlit as st
from typing import Dict, Any, List
from neo4j import GraphDatabase


def render_sidebar(agent=None):
    """
    Render sidebar with schema, status, and history.

    Args:
        agent: IntelligenceAgent instance (optional)
    """
    with st.sidebar:
        st.title("🔍 SPEED-CAMEO")
        st.caption("Temporal Knowledge Graph Intelligence")

        st.markdown("---")

        # Connection Status
        render_connection_status(agent)

        st.markdown("---")

        # Schema Information
        render_schema_info(agent)

        st.markdown("---")

        # Query History
        render_query_history()

        st.markdown("---")

        # About
        render_about()


def render_connection_status(agent):
    """Render connection status."""
    st.subheader("Connection Status")

    if agent:
        try:
            # Test Neo4j connection
            with agent.driver.session() as session:
                result = session.run("RETURN 1")
                result.single()

            st.success("✅ Neo4j Connected")

            # Get database stats
            with agent.driver.session() as session:
                result = session.run("""
                    MATCH (n)
                    RETURN count(n) as node_count
                """)
                node_count = result.single()['node_count']
                st.metric("Total Nodes", f"{node_count:,}")

        except Exception as e:
            st.error(f"❌ Neo4j Error: {str(e)[:50]}")

    else:
        st.warning("⚠️  Agent Not Initialized")


def render_schema_info(agent):
    """Render schema information."""
    st.subheader("Graph Schema")

    if agent:
        try:
            with agent.driver.session() as session:
                # Get node labels
                result = session.run("""
                    CALL db.labels() YIELD label
                    RETURN label
                    ORDER BY label
                """)
                labels = [record['label'] for record in result]

                st.markdown("**Node Types:**")
                for label in labels[:6]:  # Show first 6
                    st.markdown(f"- `{label}`")

                if len(labels) > 6:
                    st.markdown(f"- ... and {len(labels) - 6} more")

                # Get relationship types
                result = session.run("""
                    CALL db.relationshipTypes() YIELD relationshipType
                    RETURN relationshipType
                    ORDER BY relationshipType
                """)
                rel_types = [record['relationshipType'] for record in result]

                st.markdown("**Relationships:**")
                for rel in rel_types[:6]:  # Show first 6
                    st.markdown(f"- `{rel}`")

                if len(rel_types) > 6:
                    st.markdown(f"- ... and {len(rel_types) - 6} more")

        except Exception as e:
            st.error(f"Error loading schema: {str(e)[:50]}")
    else:
        st.info("Connect to view schema")


def render_query_history():
    """Render query history."""
    st.subheader("Recent Queries")

    # Get history from session state
    if 'query_history' in st.session_state and st.session_state.query_history:
        history = st.session_state.query_history[-5:]  # Last 5

        for i, query in enumerate(reversed(history), 1):
            with st.expander(f"{i}. {query[:30]}..."):
                st.code(query, language=None)
    else:
        st.info("No queries yet")


def render_about():
    """Render about section."""
    st.subheader("About")

    st.markdown("""
**SPEED Dataset**
- 62,141 events (1946-2008)
- Conflicts, protests, coups
- News-sourced data

**CAMEO Ontology**
- Event classification
- Actor taxonomy
- Relationship types

**Powered by:**
- Neo4j Knowledge Graph
- LangGraph Agent
- Claude AI
""")

    st.markdown("[Documentation](https://github.com/)")


def get_database_stats(agent) -> Dict[str, Any]:
    """
    Get database statistics.

    Args:
        agent: IntelligenceAgent instance

    Returns:
        Dictionary with stats
    """
    if not agent:
        return {}

    try:
        with agent.driver.session() as session:
            # Node counts by label
            result = session.run("""
                CALL db.labels() YIELD label
                CALL {
                    WITH label
                    MATCH (n)
                    WHERE label IN labels(n)
                    RETURN count(n) as count
                }
                RETURN label, count
                ORDER BY count DESC
            """)
            node_counts = {record['label']: record['count'] for record in result}

            # Relationship counts
            result = session.run("""
                CALL db.relationshipTypes() YIELD relationshipType
                CALL {
                    WITH relationshipType
                    MATCH ()-[r]->()
                    WHERE type(r) = relationshipType
                    RETURN count(r) as count
                }
                RETURN relationshipType, count
                ORDER BY count DESC
            """)
            rel_counts = {record['relationshipType']: record['count'] for record in result}

            return {
                'nodes': node_counts,
                'relationships': rel_counts
            }

    except Exception as e:
        st.error(f"Error fetching stats: {e}")
        return {}
