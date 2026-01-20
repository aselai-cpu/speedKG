"""
SPEED-CAMEO Temporal Knowledge Graph Intelligence

Streamlit UI for natural language queries over historical event data.
"""

import streamlit as st
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.intelligence.agent import IntelligenceAgent
from src.ui.components.sidebar import render_sidebar
from src.ui.components.chat import render_chat_interface, clear_chat_history, process_query
from src.utils.config import get_config


# Page configuration
st.set_page_config(
    page_title="SPEED-CAMEO Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)


def initialize_session_state():
    """Initialize Streamlit session state."""
    if 'agent' not in st.session_state:
        st.session_state.agent = None

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    if 'query_history' not in st.session_state:
        st.session_state.query_history = []

    if 'initialized' not in st.session_state:
        st.session_state.initialized = False


def initialize_agent():
    """Initialize the intelligence agent."""
    if st.session_state.agent is not None:
        return True

    try:
        with st.spinner("Initializing intelligence agent..."):
            config = get_config()
            agent = IntelligenceAgent(
                neo4j_uri=config.NEO4J_URI,
                neo4j_user=config.NEO4J_USER,
                neo4j_password=config.NEO4J_PASSWORD,
                anthropic_api_key=config.ANTHROPIC_API_KEY
            )

            st.session_state.agent = agent
            st.session_state.initialized = True
            return True

    except Exception as e:
        st.error(f"❌ Failed to initialize agent: {str(e)}")
        st.info("Please check your configuration in .env file")
        return False


def render_header():
    """Render page header with controls."""
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.title("🔍 SPEED-CAMEO Intelligence")
        st.caption("Natural Language Interface for Historical Event Analysis")

    with col2:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            clear_chat_history()

    with col3:
        if st.session_state.agent:
            st.success("✓ Connected")
        else:
            st.error("✗ Not Connected")


def render_error_state():
    """Render error state when agent fails to initialize."""
    st.error("⚠️ Agent Not Initialized")

    st.markdown("""
    ### Troubleshooting

    Please check your `.env` file contains:

    ```env
    # Neo4j Configuration
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_password

    # Anthropic API
    ANTHROPIC_API_KEY=your_api_key

    # Application Settings
    LOG_LEVEL=INFO
    CLAUDE_MODEL=claude-3-sonnet-20240229
    ```

    ### Common Issues

    1. **Neo4j not running**: Start with `docker-compose up -d`
    2. **Invalid API key**: Update ANTHROPIC_API_KEY in .env
    3. **Wrong credentials**: Check NEO4J_PASSWORD matches your setup
    """)

    if st.button("🔄 Retry Initialization"):
        st.session_state.agent = None
        st.session_state.initialized = False
        st.rerun()


def main():
    """Main application entry point."""
    # Initialize session state
    initialize_session_state()

    # Render sidebar
    render_sidebar(st.session_state.agent)

    # Main content area
    if not st.session_state.initialized:
        # Try to initialize agent
        if not initialize_agent():
            render_error_state()
            return

    # Render main chat interface
    render_chat_interface()

    # Handle pending query (from example buttons)
    if 'pending_query' in st.session_state:
        query = st.session_state.pending_query
        del st.session_state.pending_query

        # Add user message
        from src.ui.components.chat import add_message
        add_message('user', query)

        # Show user message
        with st.chat_message('user'):
            st.markdown(query)

        # Process query
        process_query(query)

    # Footer
    render_footer()


def render_footer():
    """Render page footer."""
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("**Dataset**: SPEED (62,141 events, 1946-2008)")

    with col2:
        st.caption("**Ontology**: CAMEO Conflict & Mediation")

    with col3:
        st.caption("**Powered by**: Neo4j + LangGraph + Claude")


if __name__ == "__main__":
    main()
