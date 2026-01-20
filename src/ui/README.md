# SPEED-CAMEO Intelligence UI

Streamlit-based natural language interface for querying the SPEED-CAMEO temporal knowledge graph.

## Features

### 💬 Chat Interface
- Natural language query input
- Message history with context
- Example queries for quick start
- Streaming responses (when agent is ready)

### 📊 Response Display
- **Answer**: Natural language response from Claude
- **Cypher Query**: Expandable view of generated query
- **Citations**: Event IDs, actors, locations referenced
- **Execution Trace**: Step-by-step agent workflow
- **Metadata**: Intent, result count, latency

### 🗂️ Sidebar
- **Connection Status**: Neo4j connectivity indicator
- **Database Stats**: Node and relationship counts
- **Schema Info**: Node labels and relationship types
- **Query History**: Last 5 queries
- **About**: Dataset and system information

### 🔬 Trace View
- Real-time execution steps
- Duration per step
- Success/failure indicators
- Detailed step metadata
- Downloadable trace JSON

## Running the UI

### Quick Start

```bash
# Make sure Neo4j is running
docker-compose up -d

# Launch the UI
./run_ui.sh
```

Or manually:

```bash
# Activate environment
source .venv/bin/activate

# Run Streamlit
streamlit run src/ui/app.py
```

The UI will open at: http://localhost:8501

### Configuration

UI settings in `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#FF6B35"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F5F5F5"
textColor = "#262730"

[server]
port = 8501
```

## Usage

### Basic Query Flow

1. **Enter Query**: Type natural language question
2. **View Response**: See analysis with citations
3. **Expand Details**: Click to see Cypher, trace, citations
4. **Follow Up**: Ask related questions

### Example Queries

**Pattern Analysis:**
- "What are the top 5 most active actors?"
- "What were the deadliest events?"

**Geographic:**
- "What events occurred in Palestine?"
- "Show me events in the Middle East in 1990"

**Actor Analysis:**
- "What actions did Hamas take in 2003?"
- "Which actors targeted Israeli Defense Force?"

**Temporal:**
- "How many protests occurred each year?"
- "Compare violence levels between 1990-2000 and 2000-2005"

**Event Chains:**
- "Show me events linked to coups"
- "What happened after the Iraq invasion?"

### Understanding Results

**Intent Classification:**
- Determines retrieval strategy
- Shown in metadata section

**Result Count:**
- Number of records from Cypher query
- 0 results may indicate data availability issue

**Latency:**
- Total query processing time
- Target: <3000ms P95

**Citations:**
- Event IDs (e.g., EID12345)
- Actor names
- Locations
- Time periods

## UI Components

### app.py
Main application entry point
- Session state management
- Agent initialization
- Layout orchestration

### components/chat.py
Chat interface and message handling
- Message rendering
- Query processing
- Example queries
- History management

### components/sidebar.py
Sidebar with system information
- Connection status
- Schema display
- Query history
- Database stats

### components/trace_view.py
Execution trace visualization
- Step-by-step workflow
- Timing information
- Error display
- Timeline view

## Troubleshooting

### Agent Not Initialized

**Symptoms:**
- "Agent not initialized" error
- Red connection status

**Solutions:**
1. Check `.env` file has valid credentials
2. Verify Neo4j is running: `docker-compose ps`
3. Test Neo4j connection: `http://localhost:7474`
4. Verify Anthropic API key is valid
5. Click "Retry Initialization" in UI

### No Results

**Possible Causes:**
1. **Invalid Cypher**: Check generated query in expander
2. **No Matching Data**: Query filters too restrictive
3. **Wrong Actor/Location Name**: Use exact names from data
4. **Date Out of Range**: SPEED covers 1946-2008

### Slow Performance

**Optimization Steps:**
1. Check subgraph size (should be <500 nodes)
2. Review Cypher query complexity
3. Verify Neo4j indexes exist
4. Reduce `max_subgraph_nodes` in config

### UI Not Loading

**Check:**
```bash
# Verify Streamlit is installed
streamlit --version

# Check port availability
lsof -i :8501

# View Streamlit logs
streamlit run src/ui/app.py --logger.level=debug
```

## Development

### Adding New Components

Create in `src/ui/components/`:

```python
# my_component.py
import streamlit as st

def render_my_component():
    st.subheader("My Component")
    # Component logic
```

Import in `app.py`:

```python
from src.ui.components.my_component import render_my_component
```

### Customizing Theme

Edit `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#your_color"
backgroundColor = "#your_bg"
```

### Session State

Available in `st.session_state`:
- `agent`: IntelligenceAgent instance
- `messages`: Chat message history
- `query_history`: Query strings
- `initialized`: Agent initialization status

## Known Limitations

1. **API Key Required**: Valid Anthropic API key needed for queries
2. **No Streaming**: Responses shown after completion (SSE not implemented)
3. **No Multi-User**: Session state per browser tab
4. **No Persistence**: Messages cleared on page refresh
5. **Limited Viz**: No graph visualization (could add with Neo4j Bloom)

## Future Enhancements

### Near Term
- [ ] Add session persistence
- [ ] Implement response streaming (SSE)
- [ ] Add graph visualization
- [ ] Export conversation to PDF

### Long Term
- [ ] Multi-user support with auth
- [ ] Query builder UI
- [ ] Custom dashboard creation
- [ ] Collaborative annotations
- [ ] Query templates library

## Architecture

```
app.py (Main)
├── Session State Management
├── Agent Initialization
├── Layout
│   ├── Sidebar (sidebar.py)
│   │   ├── Connection Status
│   │   ├── Schema Info
│   │   └── Query History
│   └── Main Content (chat.py)
│       ├── Message Display
│       ├── Chat Input
│       ├── Trace View (trace_view.py)
│       └── Example Queries
└── Agent Integration
    └── IntelligenceAgent
```

## Screenshots

*Screenshots would go here showing:*
- Main chat interface
- Expanded Cypher query
- Execution trace
- Sidebar with schema
- Example queries

---

**For Issues**: Report at [GitHub Issues](https://github.com/)

**Documentation**: See main project README
