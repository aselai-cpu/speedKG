"""
Chat Interface Component

Handles user input and message display.
"""

import streamlit as st
from typing import Dict, Any, List


def render_chat_interface():
    """Render the main chat interface."""
    st.title("💬 Ask About Historical Events")
    st.caption("Natural language queries over 62,141 historical events (1946-2008)")

    # Display chat messages
    render_messages()

    # Chat input
    render_chat_input()

    # Example queries
    render_example_queries()


def render_messages():
    """Render all messages in the chat history."""
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # Display messages
    for message in st.session_state.messages:
        render_message(message)


def render_message(message: Dict[str, Any]):
    """
    Render a single message.

    Args:
        message: Message dictionary with role, content, and optional metadata
    """
    role = message.get('role', 'user')
    content = message.get('content', '')

    with st.chat_message(role):
        st.markdown(content)

        # Show metadata for assistant messages
        if role == 'assistant':
            render_message_metadata(message)


def render_message_metadata(message: Dict[str, Any]):
    """
    Render metadata for assistant messages.

    Args:
        message: Message dictionary with metadata
    """
    metadata = message.get('metadata', {})

    if not metadata:
        return

    # Cypher query expander
    cypher = metadata.get('cypher_query')
    if cypher:
        with st.expander("🔍 View Cypher Query"):
            st.code(cypher, language="cypher")

            # Query info
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Intent", metadata.get('intent', 'N/A'))
            with col2:
                st.metric("Results", metadata.get('result_count', 0))
            with col3:
                latency = metadata.get('latency_ms', 0)
                st.metric("Latency", f"{latency:.0f}ms")

    # Citations
    citations = metadata.get('citations', [])
    if citations:
        with st.expander(f"📚 Citations ({len(citations)})"):
            for citation in citations[:10]:  # Show first 10
                st.markdown(f"- {citation}")

    # Trace view
    trace = metadata.get('trace', [])
    if trace:
        render_trace_expander(trace)


def render_trace_expander(trace: List[Dict[str, Any]]):
    """
    Render execution trace as expandable section.

    Args:
        trace: List of trace step dictionaries or TraceStep objects
    """
    with st.expander("🔬 Execution Trace"):
        for i, step in enumerate(trace, 1):
            # Handle both dict and TraceStep object
            if isinstance(step, dict):
                step_name = step.get('step', 'Unknown')
                success = step.get('success', True)
                duration = step.get('duration_ms')
                details = step.get('details', {})
            else:
                # TraceStep object (from dataclass)
                step_name = getattr(step, 'step_name', 'Unknown')
                success = getattr(step, 'success', True)
                duration = getattr(step, 'duration_ms', None)
                details = getattr(step, 'details', {})

            status_icon = "✓" if success else "✗"
            status_color = "green" if success else "red"

            # Format duration safely
            duration_str = f"({duration:.0f}ms)" if duration is not None else ""

            st.markdown(f"**{i}. {status_icon} {step_name}** "
                       f"<span style='color:{status_color}'>{duration_str}</span>",
                       unsafe_allow_html=True)

            # Show details if present
            if details:
                st.json(details, expanded=False)

            # Show error if present
            error = step.get('error') if isinstance(step, dict) else getattr(step, 'error', None)
            if error:
                st.error(f"Error: {error}")


def render_chat_input():
    """Render chat input box."""
    # Chat input
    if prompt := st.chat_input("Ask about historical events..."):
        # Add user message
        add_message('user', prompt)

        # Show user message immediately
        with st.chat_message('user'):
            st.markdown(prompt)

        # Process query
        process_query(prompt)


def add_message(role: str, content: str, metadata: Dict[str, Any] = None):
    """
    Add a message to chat history.

    Args:
        role: 'user' or 'assistant'
        content: Message content
        metadata: Optional metadata (for assistant messages)
    """
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    message = {
        'role': role,
        'content': content
    }

    if metadata:
        message['metadata'] = metadata

    st.session_state.messages.append(message)


def process_query(query: str):
    """
    Process a user query through the agent.

    Args:
        query: User query string
    """
    # Add to history
    if 'query_history' not in st.session_state:
        st.session_state.query_history = []
    st.session_state.query_history.append(query)

    # Get agent from session state
    agent = st.session_state.get('agent')

    if not agent:
        add_message('assistant', "⚠️ Agent not initialized. Please check your configuration.")
        st.rerun()
        return

    # Show thinking indicator
    with st.chat_message('assistant'):
        with st.spinner('Thinking...'):
            try:
                # Query the agent
                result = agent.query(query)

                # Extract response
                response = result.get('final_response', 'No response generated')

                # Prepare metadata
                metadata = {
                    'intent': result.get('intent'),
                    'cypher_query': result.get('cypher_query'),
                    'cypher_valid': result.get('cypher_valid'),
                    'result_count': result.get('result_count', 0),
                    'latency_ms': result.get('total_duration_ms', 0),
                    'citations': result.get('citations', []),
                    'trace': result.get('trace', [])
                }

                # Add assistant message
                add_message('assistant', response, metadata)

                # Rerun to show new message
                st.rerun()

            except Exception as e:
                error_msg = f"❌ Error processing query: {str(e)}"
                add_message('assistant', error_msg)
                st.rerun()


def render_example_queries():
    """Render example queries for users to try."""
    if st.session_state.messages:
        # Only show examples if no messages yet
        return

    st.markdown("---")
    st.subheader("Example Queries")

    examples = [
        "What are the top 5 most active actors?",
        "What events occurred in Palestine in 2003?",
        "How many protests occurred each year?",
        "Show me events linked to coups",
        "What actions did Hamas take between 2000 and 2005?",
        "Which actors targeted Israeli Defense Force most frequently?"
    ]

    cols = st.columns(2)
    for i, example in enumerate(examples):
        col = cols[i % 2]
        with col:
            if st.button(example, key=f"example_{i}", use_container_width=True):
                # Add to input (will be processed on next interaction)
                st.session_state['pending_query'] = example
                st.rerun()


def clear_chat_history():
    """Clear all messages from chat history."""
    if 'messages' in st.session_state:
        st.session_state.messages = []
    st.rerun()
