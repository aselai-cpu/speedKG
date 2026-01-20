"""
Trace View Component

Real-time visualization of agent execution steps.
"""

import streamlit as st
from typing import List, Dict, Any
from datetime import datetime


def render_trace_panel(trace: List[Dict[str, Any]], title: str = "Agent Execution Trace"):
    """
    Render execution trace in a panel.

    Args:
        trace: List of trace step dictionaries
        title: Panel title
    """
    st.subheader(title)

    if not trace:
        st.info("No execution trace available")
        return

    # Summary metrics
    render_trace_summary(trace)

    st.markdown("---")

    # Step-by-step trace
    render_trace_steps(trace)


def render_trace_summary(trace: List[Dict[str, Any]]):
    """
    Render trace summary metrics.

    Args:
        trace: List of trace steps
    """
    total_duration = sum(step.get('duration_ms', 0) for step in trace)
    successful_steps = sum(1 for step in trace if step.get('success', True))
    total_steps = len(trace)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Steps", total_steps)

    with col2:
        st.metric("Successful", f"{successful_steps}/{total_steps}")

    with col3:
        st.metric("Duration", f"{total_duration:.0f}ms")


def render_trace_steps(trace: List[Dict[str, Any]]):
    """
    Render individual trace steps.

    Args:
        trace: List of trace steps
    """
    for i, step in enumerate(trace, 1):
        render_trace_step(i, step)


def render_trace_step(index: int, step: Dict[str, Any]):
    """
    Render a single trace step.

    Args:
        index: Step number
        step: Step dictionary
    """
    step_name = step.get('step', 'Unknown')
    success = step.get('success', True)
    duration = step.get('duration_ms', 0)
    timestamp = step.get('timestamp', '')
    details = step.get('details', {})
    error = step.get('error')

    # Status indicator
    if success:
        status_icon = "✓"
        status_color = "green"
    else:
        status_icon = "✗"
        status_color = "red"

    # Format timestamp
    if timestamp:
        try:
            ts = datetime.fromisoformat(timestamp)
            time_str = ts.strftime("%H:%M:%S.%f")[:-3]
        except:
            time_str = timestamp[:12]
    else:
        time_str = "N/A"

    # Step header
    st.markdown(
        f"**{index}. {status_icon} {step_name}**  \n"
        f"<span style='color:gray; font-size:0.9em'>{time_str} | "
        f"<span style='color:{status_color}'>{duration:.0f}ms</span></span>",
        unsafe_allow_html=True
    )

    # Show details if present
    if details:
        with st.expander("Details", expanded=False):
            st.json(details)

    # Show error if present
    if error:
        st.error(f"❌ {error}")

    st.markdown("")  # Spacing


def render_live_trace(container, trace_placeholder):
    """
    Render live updating trace.

    Args:
        container: Streamlit container
        trace_placeholder: Placeholder for trace updates
    """
    # This would be used for SSE streaming in a full implementation
    # For now, trace is shown after query completes
    pass


def format_trace_for_download(trace: List[Dict[str, Any]]) -> str:
    """
    Format trace for download as JSON.

    Args:
        trace: List of trace steps

    Returns:
        JSON string
    """
    import json
    return json.dumps(trace, indent=2)


def render_trace_download_button(trace: List[Dict[str, Any]]):
    """
    Render download button for trace.

    Args:
        trace: List of trace steps
    """
    if not trace:
        return

    trace_json = format_trace_for_download(trace)

    st.download_button(
        label="Download Trace",
        data=trace_json,
        file_name=f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )


def render_trace_timeline(trace: List[Dict[str, Any]]):
    """
    Render trace as a timeline visualization.

    Args:
        trace: List of trace steps
    """
    if not trace:
        return

    st.markdown("### Timeline")

    # Calculate cumulative time
    cumulative_time = 0
    timeline_data = []

    for step in trace:
        duration = step.get('duration_ms', 0)
        step_name = step.get('step', 'Unknown')
        success = step.get('success', True)

        timeline_data.append({
            'step': step_name,
            'start': cumulative_time,
            'end': cumulative_time + duration,
            'duration': duration,
            'success': success
        })

        cumulative_time += duration

    # Simple text-based timeline (could be enhanced with charts)
    for i, data in enumerate(timeline_data, 1):
        bar_length = int((data['duration'] / cumulative_time) * 50) if cumulative_time > 0 else 0
        bar = "█" * bar_length if data['success'] else "▓" * bar_length

        st.text(f"{i}. {data['step'][:20]:20} {bar} {data['duration']:.0f}ms")
