# SPEED-CAMEO Code Walkthrough

This document provides a detailed walkthrough of the SPEED-CAMEO system implementation, explaining key design decisions and code patterns.

## Table of Contents

1. [Data Ingestion Pipeline](#data-ingestion-pipeline)
2. [CAMEO Ontology Integration](#cameo-ontology-integration)
3. [LangGraph State Machine](#langgraph-state-machine)
4. [Cypher Generation with Few-Shot Prompting](#cypher-generation-with-few-shot-prompting)
5. [Adaptive Subgraph Retrieval](#adaptive-subgraph-retrieval)
6. [Claude Reasoning](#claude-reasoning)
7. [Streamlit UI Integration](#streamlit-ui-integration)
8. [Key Design Decisions](#key-design-decisions)

---

## Data Ingestion Pipeline

### Overview

The ingestion pipeline loads SPEED CSV data (62,141 events) and CAMEO ontology into Neo4j with validation, error handling, and two-pass loading.

### File: `src/ingestion/csv_parser.py`

**Purpose**: Parse SPEED CSV with robust error handling for high missing data rates (93-100%).

**Key Implementation Details**:

```python
class SPEEDCSVParser:
    MISSING_VALUES = [".", "", "nan", "NaN", None]  # SPEED sentinels

    def parse(self, chunk_size: int = 1000):
        """Chunked parsing for memory efficiency."""
        for chunk_idx, df_chunk in enumerate(pd.read_csv(
            self.csv_path,
            chunksize=chunk_size,
            na_values=self.MISSING_VALUES,
            keep_default_na=True,
            low_memory=False,
            encoding='latin1'  # SPEED uses latin1, not UTF-8
        )):
            for idx, row in df_chunk.iterrows():
                try:
                    event = self._parse_row(row)
                    if event:
                        yield event
                except Exception as e:
                    self._log_error(idx, row, e)  # Log and continue
```

**Design Rationale**:
- **Chunked Reading**: 1000 rows/chunk to handle large dataset without memory issues
- **Generator Pattern**: Yields events one at a time for streaming ingestion
- **latin1 Encoding**: SPEED data predates UTF-8 standardization
- **Error Tolerance**: Logs malformed records but continues processing (required for 62K events)

**Event Parsing Logic**:

```python
def _parse_row(self, row: pd.Series) -> Optional[Event]:
    """Parse single row into Event domain model."""
    # Required fields
    event_id = self._safe_get(row, 'eventid')
    if not event_id:
        return None  # Skip rows without event ID

    # Parse temporal info (multiple date formats)
    temporal = self._parse_temporal(row)

    # Parse actors (initiator, target, victim)
    initiator = self._parse_actor(row, 'INI', ActorRole.INITIATOR)
    target = self._parse_actor(row, 'TAR', ActorRole.TARGET)
    victim = self._parse_actor(row, 'VIC', ActorRole.VICTIM)

    # Parse location
    location = self._parse_location(row)

    # Create event with core fields
    event = Event(
        event_id=event_id,
        temporal=temporal,
        event_type=self._safe_int(row, 'EV_TYPE'),
        initiator=initiator,
        target=target,
        # ... other fields
    )

    # Store sparse fields (93-100% missing) in properties dict
    self._extract_properties(row, event)

    return event
```

**Why Separate Properties Dict?**
- 106 CSV columns with very high missing rates
- Creating 106 node properties would waste space
- JSON properties field stores only non-null sparse data

### File: `src/ingestion/neo4j_loader.py`

**Purpose**: Two-pass loading strategy for events and relationships.

**Two-Pass Strategy**:

**Pass 1**: Create nodes and most relationships
```python
def load_events(self, csv_path: Path, batch_size: int = 500):
    """Load events in batches."""
    batch = []
    for event in parser.parse():
        batch.append(event)

        if len(batch) >= batch_size:
            self._load_batch(batch)  # Transaction per batch
            batch = []
```

**Pass 2**: Create event-to-event linkages
```python
def _create_event_links(self):
    """Create LINKED_TO relationships after all events exist."""
    # Find linked events
    result = session.run("""
        MATCH (e:Event)
        WHERE e.isLinked = true
        RETURN e.eventId, e.linkedFrom, e.linkedTo
    """)

    # Create relationships
    for record in result:
        # Create LINKED_TO edges between events
        # ...
```

**Why Two-Pass?**
- Events can link to other events (forward/backward references)
- Can't create relationship before both nodes exist
- Pass 1 ensures all events loaded before Pass 2 creates links

**Critical Implementation: JSON Serialization**:

```python
def _create_event_node(self, tx, event: Event):
    """Create Event node with JSON properties."""
    import json

    # Convert properties dict to JSON string
    properties_json = json.dumps(event.properties) if event.properties else None

    tx.run("""
        CREATE (e:Event {
            eventId: $event_id,
            year: $year,
            # ... other fields
            propertiesJson: $properties_json  # Store as JSON string
        })
    """, properties_json=properties_json)
```

**Why JSON String?**
- Neo4j doesn't accept nested dictionaries as properties
- Solution: Serialize to JSON string, deserialize when reading
- Allows flexible schema for sparse fields

---

## CAMEO Ontology Integration

### File: `src/ingestion/cameo_parser.py`

**Purpose**: Parse CAMEO reference files into ontology structures.

**Actor Parsing**:

```python
def parse_actors(self, file_path: Path) -> List[CAMEOActorType]:
    """Parse CAMEO actor codes with hierarchies."""
    actors = []
    for line in open(file_path, 'r', encoding='latin1'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        # Format: ACTOR_NAME [CODE] ;metadata
        match = re.match(r'([^\[]+)\s*\[([^\]]+)\]', line)
        if match:
            name = match.group(1).strip()
            code = match.group(2).strip()

            # Parse temporal restrictions: [CODE <date] or [CODE >date]
            temporal_info = self._parse_temporal_restriction(code)

            actors.append(CAMEOActorType(
                code=code,
                description=name,
                is_temporally_restricted=temporal_info is not None,
                # ...
            ))
    return actors
```

**Verb Parsing (20 Root Categories)**:

```python
def parse_verbs(self, file_path: Path) -> List[CAMEOVerb]:
    """Parse 4-level hierarchical verb codes."""
    verbs = []
    for line in open(file_path):
        # Format: CODE LABEL
        # Hierarchy: 01 -> 010 -> 0111 -> 01111
        parts = line.split(maxsplit=1)
        code = parts[0]
        label = parts[1] if len(parts) > 1 else ""

        # Determine hierarchy level by code length
        level = self._determine_level(code)
        category = self._extract_category(code)  # 01-20

        verbs.append(CAMEOVerb(
            code=code,
            label=label,
            level=level,
            category=category
        ))
    return verbs
```

**Design Decision**: CAMEO as First-Class Neo4j Nodes

Instead of storing CAMEO codes as simple properties, we create EventType and CAMEOActorType nodes:

```cypher
// EventType hierarchy
(et:EventType {cameoCode: '01', label: 'Make statement', level: 1})
(et2:EventType {cameoCode: '010', label: 'Make public statement', level: 2})
(et2)-[:PARENT_TYPE]->(et)

// Link events to CAMEO types
(e:Event)-[:OF_TYPE]->(et:EventType)
```

**Why?**
- Enables graph-based queries: "Find all violent events" → traverse EventType hierarchy
- Supports semantic search: Find events similar by CAMEO classification
- Facilitates reasoning: Claude can see event type relationships

---

## LangGraph State Machine

### File: `src/intelligence/agent.py`

**Purpose**: Orchestrate query workflow with explicit state transitions.

**State Definition**:

```python
@dataclass
class AgentState:
    """State passed through workflow."""
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

    # Query execution
    query_results: Optional[List[Dict]] = None
    subgraph: Optional[Dict] = None

    # Reasoning
    final_response: Optional[str] = None
    citations: List[str] = field(default_factory=list)

    # Trace
    trace: List[TraceStep] = field(default_factory=list)
```

**Workflow Construction**:

```python
def _build_graph(self) -> StateGraph:
    """Build LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Add nodes (functions that transform state)
    workflow.add_node("parse_intent", self._parse_intent)
    workflow.add_node("generate_cypher", self._generate_cypher)
    workflow.add_node("execute_query", self._execute_query)
    workflow.add_node("reason", self._reason)
    workflow.add_node("handle_error", self._handle_error)

    # Define edges (state transitions)
    workflow.set_entry_point("parse_intent")
    workflow.add_edge("parse_intent", "generate_cypher")

    # Conditional edge: valid Cypher → execute, invalid → error
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
```

**Node Implementation**:

```python
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
    except Exception as e:
        # Fallback to default intent
        state.intent = QueryIntent.PATTERN_ANALYSIS
        state.intent_confidence = 0.5
        state.add_trace("parse_intent_error", {"error": str(e)}, success=False)

    return state  # State flows to next node
```

**Why LangGraph?**
- **Explicit Control Flow**: Clear visualization of agent logic
- **State Persistence**: Full agent history accessible for debugging
- **Conditional Branching**: Handle errors without try/catch spaghetti
- **Trace Generation**: Every state transition logged automatically
- **Testability**: Easy to test individual nodes in isolation

---

## Cypher Generation with Few-Shot Prompting

### File: `src/intelligence/cypher_gen.py`

**Purpose**: Generate syntactically valid, secure Cypher from natural language.

**System Prompt Structure**:

```python
system_prompt = f"""
{SCHEMA_DESCRIPTION}  # Full Neo4j schema

{FEW_SHOT_EXAMPLES}  # 8 example Query → Cypher pairs

{SECURITY_RULES}  # Validation constraints

Generate a Cypher query for the user's question.
Return ONLY the Cypher query without explanation.

The query intent is: {intent.value}
"""
```

**Few-Shot Examples** (Critical for Accuracy):

```python
FEW_SHOT_EXAMPLES = """
**Example 1: Pattern Analysis**
User: "What are the top 5 most active actors?"
Intent: pattern_analysis
Cypher:
MATCH (a:Actor)<-[:INITIATED_BY]-(e:Event)
RETURN a.name, count(e) as event_count
ORDER BY event_count DESC
LIMIT 5

**Example 2: Geographic Analysis**
User: "What events occurred in Gaza?"
Intent: geographic_analysis
Cypher:
MATCH (e:Event)-[:OCCURRED_AT]->(l:Location)
WHERE l.name CONTAINS 'Gaza' OR l.country CONTAINS 'Gaza'
RETURN e.eventId, e.year, l.name
ORDER BY e.year DESC
LIMIT 100

# ... 6 more examples covering all intent types
"""
```

**Why Few-Shot?**
- Claude learns schema patterns from examples
- Reduces syntax errors (MATCH vs. OPTIONAL MATCH, proper WHERE clauses)
- Teaches best practices (LIMIT, ORDER BY, indexable filters)
- Intent-aware: Different examples per query type

**Security Validation**:

```python
def _validate_security(self, cypher: str) -> Tuple[bool, Optional[str]]:
    """Prevent Cypher injection."""
    cypher_upper = cypher.upper()

    # Block destructive operations
    forbidden = ['DELETE', 'REMOVE', 'DROP', 'DETACH', 'SET', 'CREATE', 'MERGE']
    for keyword in forbidden:
        if keyword in cypher_upper:
            return False, f"Forbidden operation: {keyword}"

    # Enforce LIMIT (prevent resource exhaustion)
    if 'LIMIT' not in cypher_upper:
        cypher += '\nLIMIT 100'  # Auto-add

    limit_match = re.search(r'LIMIT\s+(\d+)', cypher_upper)
    if limit_match and int(limit_match.group(1)) > 1000:
        return False, f"LIMIT too high (max 1000)"

    return True, None
```

**Why This Matters**:
- User input → Claude → Cypher → Neo4j (potential injection path)
- Validation ensures read-only, bounded queries
- Protects production Neo4j instance

---

## Adaptive Subgraph Retrieval

### File: `src/intelligence/graph_retrieval.py`

**Purpose**: Expand query results into context-rich subgraphs based on intent.

**Retrieval Strategies**:

```python
RETRIEVAL_STRATEGIES = {
    QueryIntent.SINGLE_EVENT: {
        'max_hops': 1,
        'max_nodes': 100,
        'relationships': ['INITIATED_BY', 'TARGETED', 'OCCURRED_AT']
    },
    QueryIntent.EVENT_CHAIN: {
        'max_hops': 2,
        'max_nodes': 300,
        'relationships': ['LINKED_TO', 'INITIATED_BY', 'OCCURRED_AT']
    },
    QueryIntent.ACTOR_ANALYSIS: {
        'max_hops': 2,
        'max_nodes': 500,
        'relationships': ['INITIATED_BY', 'TARGETED', 'VICTIMIZED']
    },
    QueryIntent.PATTERN_ANALYSIS: {
        'max_hops': 1,
        'max_nodes': 500,
        'aggregation_mode': True  # No expansion, just aggregates
    }
}
```

**Subgraph Expansion Logic**:

```python
def _expand_subgraph(self, session, records, strategy):
    """Expand initial results into subgraph."""
    max_hops = strategy['max_hops']
    max_nodes = strategy['max_nodes']
    relationships = strategy.get('relationships')

    # Extract event IDs from query results
    event_ids = self._extract_event_ids(records)

    # Build relationship filter
    rel_filter = f":{  '|'.join(relationships)}" if relationships else ""

    # Expansion query (variable-length path)
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
    # Extract all unique nodes and relationships
    UNWIND paths as p
    UNWIND nodes(p) as n
    WITH collect(DISTINCT n) as all_nodes, paths
    UNWIND paths as p
    UNWIND relationships(p) as r
    RETURN all_nodes, collect(DISTINCT r) as all_rels
    """

    result = session.run(expansion_query, event_ids=event_ids)
    # Serialize to JSON for Claude
    return self._serialize_subgraph(result)
```

**Why Adaptive?**
- **Single Event**: Small context (1 hop) → fast response
- **Event Chain**: More hops (2-3) → capture sequences
- **Actor Analysis**: Focus on actor relationships → filter to actor edges
- **Pattern Analysis**: No expansion → just aggregated stats

**Trade-off**: Context size vs. response time
- More hops = richer context but slower queries
- Intent-based strategy balances both

**Serialization for Claude**:

```python
def format_subgraph_for_llm(self, subgraph, query_results):
    """Convert graph to readable text."""
    sections = []

    sections.append("# Query Results\n")
    sections.append(f"Found {len(query_results)} matching records\n")
    for i, record in enumerate(query_results[:10], 1):
        sections.append(f"{i}. {self._format_record(record)}")

    sections.append("\n# Subgraph Context\n")
    sections.append(f"Total nodes: {subgraph['node_count']}\n")

    # Group nodes by type
    for label, nodes in nodes_by_label.items():
        sections.append(f"\n## {label} Nodes:\n")
        for node in nodes[:5]:
            sections.append(f"- {self._format_node(node)}")

    return "\n".join(sections)
```

**Why Text Format?**
- Claude accepts text, not JSON
- Structured format makes parsing easy
- Shows relationships and properties clearly

---

## Claude Reasoning

### File: `src/intelligence/reasoning.py`

**Purpose**: Generate natural language responses grounded in graph data.

**System Prompt**:

```python
SYSTEM_PROMPT = """You are an expert analyst of historical conflict and mediation events.

## Dataset Context
- SPEED Dataset: 62,141 events (1946-2008)
- CAMEO Ontology: Event classification framework
- Focus: Conflicts, protests, coups, government actions

## Analysis Guidelines
1. **Be Specific**: Cite event IDs, dates, actors, locations
2. **Be Accurate**: Only state facts present in data
3. **Be Comprehensive**: Analyze patterns when relevant
4. **Acknowledge Limitations**: Note incomplete data

## Response Format
**Answer**: [Direct answer]
**Evidence**: [Specific data points]
**Analysis**: [Insights about patterns/significance]
**Citations**:
- Events: EID12345, EID67890
- Actors: Hamas, Palestinian Arab
- Time Period: 2003-2005
"""
```

**Reasoning Call**:

```python
def reason(self, user_query: str, subgraph_text: str, cypher_query: str):
    """Generate response from subgraph."""
    user_message = f"""
User Question: {user_query}

Graph Data Retrieved:
{subgraph_text}

Cypher Query Used:
{cypher_query}

Analyze this data and answer the question following the response format.
"""

    response = self.client.messages.create(
        model=self.model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    response_text = response.content[0].text
    citations = self._extract_citations(response_text)
    token_count = response.usage.input_tokens + response.usage.output_tokens

    return response_text, citations, token_count
```

**Citation Extraction**:

```python
def _extract_citations(self, response: str) -> List[str]:
    """Extract citations from structured response."""
    citations = []

    # Extract event IDs (EID\d+)
    event_ids = re.findall(r'EID\d+', response)
    citations.extend(event_ids)

    # Extract Citations section
    if 'Citations' in response:
        lines = response.split('\n')
        in_citations = False
        for line in lines:
            if 'Citations' in line:
                in_citations = True
            elif in_citations and (line.startswith('-') or line.startswith('•')):
                citations.append(line.strip().lstrip('-•').strip())

    return list(set(citations))  # Deduplicate
```

**Why This Approach?**
- **Grounded**: All facts come from subgraph, not hallucinated
- **Structured**: Format ensures consistent responses
- **Citable**: Event IDs traceable to Neo4j
- **Transparent**: User sees Cypher query that generated data

---

## Streamlit UI Integration

### File: `src/ui/app.py`

**Purpose**: Main application orchestrating UI components.

**Session State Management**:

```python
def initialize_session_state():
    """Initialize Streamlit session state."""
    if 'agent' not in st.session_state:
        st.session_state.agent = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'query_history' not in st.session_state:
        st.session_state.query_history = []
```

**Why Session State?**
- Streamlit re-runs entire script on every interaction
- Session state persists across re-runs (like React state)
- Avoids re-initializing agent on every query

**Agent Integration**:

```python
def initialize_agent():
    """Initialize agent (cached in session state)."""
    if st.session_state.agent is not None:
        return True

    try:
        config = get_config()
        agent = IntelligenceAgent(
            neo4j_uri=config.NEO4J_URI,
            neo4j_user=config.NEO4J_USER,
            neo4j_password=config.NEO4J_PASSWORD,
            anthropic_api_key=config.ANTHROPIC_API_KEY
        )
        st.session_state.agent = agent
        return True
    except Exception as e:
        st.error(f"Failed to initialize agent: {e}")
        return False
```

### File: `src/ui/components/chat.py`

**Query Processing**:

```python
def process_query(query: str):
    """Process query through agent."""
    agent = st.session_state.get('agent')

    with st.chat_message('assistant'):
        with st.spinner('Thinking...'):
            try:
                # Query agent
                result = agent.query(query)

                # Extract response and metadata
                response = result.get('final_response')
                metadata = {
                    'intent': result.get('intent'),
                    'cypher_query': result.get('cypher_query'),
                    'result_count': result.get('result_count'),
                    'latency_ms': result.get('total_duration_ms'),
                    'citations': result.get('citations'),
                    'trace': result.get('trace')
                }

                # Add to message history
                add_message('assistant', response, metadata)

                # Rerun to show new message
                st.rerun()

            except Exception as e:
                add_message('assistant', f"Error: {e}")
                st.rerun()
```

**Why st.rerun()?**
- Streamlit doesn't auto-update UI after state changes
- st.rerun() triggers re-render to show new message
- Required after adding to st.session_state.messages

**Expandable Sections**:

```python
def render_message_metadata(message):
    """Render metadata for assistant messages."""
    metadata = message.get('metadata', {})

    # Cypher query expander
    if cypher := metadata.get('cypher_query'):
        with st.expander("🔍 View Cypher Query"):
            st.code(cypher, language="cypher")

            col1, col2, col3 = st.columns(3)
            col1.metric("Intent", metadata.get('intent'))
            col2.metric("Results", metadata.get('result_count'))
            col3.metric("Latency", f"{metadata.get('latency_ms'):.0f}ms")

    # Citations expander
    if citations := metadata.get('citations'):
        with st.expander(f"📚 Citations ({len(citations)})"):
            for citation in citations[:10]:
                st.markdown(f"- {citation}")

    # Trace expander
    if trace := metadata.get('trace'):
        with st.expander("🔬 Execution Trace"):
            for step in trace:
                st.markdown(f"**{step['step']}** ({step['duration_ms']:.0f}ms)")
                if step.get('details'):
                    st.json(step['details'])
```

**Why Expanders?**
- Keeps UI clean (details hidden by default)
- User controls information density
- Technical users can deep-dive, others get clean answer

---

## Key Design Decisions

### 1. Why Haiku Model?

**Decision**: Use `claude-3-haiku-20240307` instead of Sonnet.

**Rationale**:
- Sonnet models not available with provided API key
- Haiku works well for structured tasks (Cypher generation)
- Faster responses (<500ms vs. 2-3s)
- Lower cost for development/testing

**Trade-off**:
- Simpler responses (less nuanced analysis)
- May need more few-shot examples
- Consider upgrading to Sonnet for production

### 2. Why Two-Pass Loading?

**Decision**: Load events first, then create linkages.

**Rationale**:
- Events reference other events (linked_from, linked_to fields)
- Can't create relationship before both nodes exist
- Single-pass would require complex dependency resolution

**Alternative Considered**:
- Load events with placeholders, fill in later → complex, error-prone

### 3. Why JSON Properties Field?

**Decision**: Store sparse fields as JSON string in `propertiesJson`.

**Rationale**:
- 106 CSV columns with 93-100% missing rates
- Creating 106 Neo4j properties wastes space
- Neo4j doesn't accept nested dicts as properties
- JSON string is flexible, queryable (via APOC)

**Trade-off**:
- Slightly slower to query properties
- But avoids 100+ mostly-null fields

### 4. Why Intent-Based Retrieval?

**Decision**: Different subgraph strategies per query intent.

**Rationale**:
- Single-event queries need minimal context (1 hop, 100 nodes)
- Chain queries need more hops (2-3) to capture sequences
- Pattern queries don't need expansion (aggregation only)
- Adaptive approach balances context richness vs. speed

**Alternative Considered**:
- Fixed 2-hop expansion for all → slower, noisier context

### 5. Why LangGraph?

**Decision**: Use LangGraph state machine instead of plain function calls.

**Rationale**:
- Explicit workflow visualization
- Built-in state persistence (trace generation)
- Conditional branching without nested try/catch
- Easier to test individual nodes
- Framework handles state threading

**Alternative Considered**:
- Sequential function calls → works but loses workflow clarity

### 6. Why Streamlit?

**Decision**: Use Streamlit for UI instead of React/Next.js.

**Rationale**:
- Python-native (no context switch)
- Rapid prototyping (no API layer needed)
- Built-in state management
- Chat UI components (st.chat_message)
- Easy integration with Python backend

**Trade-off**:
- Less customizable than React
- Slower for production scale
- But perfect for research/prototype

### 7. Why structlog?

**Decision**: Use structlog instead of standard logging.

**Rationale**:
- JSON-formatted logs (machine-readable)
- Structured data (not string interpolation)
- Context propagation (add fields throughout call chain)
- Better for log aggregation (ELK, Splunk)

**Example**:
```python
logger.info("query_complete",
    query=query,
    intent=intent,
    result_count=count,
    latency_ms=latency
)
# → {"event": "query_complete", "query": "...", "intent": "...", ...}
```

### 8. Why No Streaming (Yet)?

**Decision**: Show response after completion, not real-time streaming.

**Rationale**:
- SSE/WebSocket adds complexity
- Haiku model is fast enough (<500ms)
- Trace view still shows all steps
- Can add streaming in Phase 5

**Current Implementation**:
- Query → wait → show complete response
- Trace populated after completion

**Future Enhancement**:
- SSE stream trace steps in real-time
- Stream Claude token-by-token

---

## Performance Optimizations

### 1. Chunked CSV Reading

```python
# Memory-efficient: stream 1000 rows at a time
for chunk in pd.read_csv(path, chunksize=1000):
    process_chunk(chunk)
```

### 2. Batch Event Loading

```python
# Network-efficient: 500 events per transaction
batch = []
for event in events:
    batch.append(event)
    if len(batch) >= 500:
        load_batch(batch)  # Single transaction
        batch = []
```

### 3. Neo4j Indexes

```cypher
// Speed up temporal queries
CREATE INDEX event_temporal FOR (e:Event) ON (e.year, e.month, e.day);

// Speed up actor lookups
CREATE INDEX actor_cameo FOR (a:Actor) ON (a.cameoCode);

// Enforce uniqueness
CREATE CONSTRAINT event_id_unique FOR (e:Event) REQUIRE e.eventId IS UNIQUE;
```

### 4. Query Result Limits

```python
# Auto-add LIMIT to prevent runaway queries
if 'LIMIT' not in cypher:
    cypher += '\nLIMIT 100'
```

---

## Testing Strategy

### Unit Tests

Test individual components in isolation:

```python
def test_csv_parser():
    """Test CSV parsing with mock data."""
    parser = SPEEDCSVParser('test.csv')
    events = list(parser.parse())
    assert len(events) > 0
    assert events[0].event_id is not None
```

### Integration Tests

Test component interactions:

```python
def test_neo4j_loader():
    """Test loading events into Neo4j."""
    loader = Neo4jLoader(uri, user, password)
    loader.create_schema()
    loader.load_events('test.csv', batch_size=10)

    # Verify
    with loader.driver.session() as session:
        count = session.run("MATCH (e:Event) RETURN count(e)").single()[0]
        assert count == 10
```

### E2E Tests

Test full user workflows:

```python
def test_query_workflow():
    """Test end-to-end query processing."""
    agent = IntelligenceAgent()
    result = agent.query("What are the top 5 most active actors?")

    assert result['cypher_valid'] is True
    assert result['result_count'] == 5
    assert result['final_response'] is not None
```

---

## Next Steps

This walkthrough covered the core implementation. For more details:

- **Schema Design**: See [data_model.md](data_model.md)
- **Architecture**: See [architecture.md](architecture.md)
- **Setup Guide**: See [QUICKSTART.md](../QUICKSTART.md)
- **Contributing**: See [CONTRIBUTING.md](../CONTRIBUTING.md)
