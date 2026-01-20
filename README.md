# SPEED-CAMEO Temporal Knowledge Graph & Intelligence System

A production-grade knowledge graph system that ingests SPEED historical event data (62,141 events spanning 1946-2008), integrates CAMEO ontology, and provides an intelligent GraphRAG interface using LangGraph and Claude for natural language queries.

## Features

- **Comprehensive Event Database**: 62,141 historical events with actors, locations, and temporal data
- **CAMEO Ontology Integration**: Hierarchical event classification with 20 root categories
- **Natural Language Queries**: Ask questions in plain English about historical events
- **GraphRAG Intelligence**: LangGraph agent workflow with adaptive subgraph retrieval
- **Interactive UI**: Streamlit interface with chat, schema view, and real-time agent trace
- **Evaluation-Driven**: Continuous accuracy measurement and improvement tracking

## Quick Start

**⚡ New to this project?** See [QUICKSTART.md](QUICKSTART.md) for a 5-minute setup guide.

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Anthropic API key ([get one here](https://console.anthropic.com/))

### Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   cd SpeedKG
   ```

2. Create a `.env` file from the template:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and add your Anthropic API key:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

4. Ensure your data files are in place:
   ```
   data/
   ├── SPEED-Codebook.xls
   ├── ssp_public.csv
   └── cameo/
       ├── Levant.080629.actors
       ├── CAMEO.080612.verbs
       └── CAMEO.09b5.options
   ```

### Option 1: Run with Docker Compose (Recommended)

1. Start Neo4j and the application:
   ```bash
   docker-compose up -d
   ```

2. Wait for Neo4j to be ready (check with `docker-compose logs -f neo4j`)

3. Access the application:
   - Streamlit UI: http://localhost:8501
   - Neo4j Browser: http://localhost:7474

4. Stop the application:
   ```bash
   docker-compose down
   ```

### Option 2: Run Locally with uv

1. Install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

2. Start Neo4j (via Docker or local installation):
   ```bash
   docker run -d \
     --name speedkg-neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/speedkg123 \
     -e NEO4J_PLUGINS='["apoc"]' \
     neo4j:5.16-community
   ```

3. Ingest data into Neo4j:
   ```bash
   python scripts/ingest_data.py
   ```

4. Run the Streamlit application:
   ```bash
   streamlit run src/ui/app.py
   ```

5. Access the UI at http://localhost:8501

## Data Ingestion

The ingestion pipeline loads SPEED CSV data and CAMEO ontology into Neo4j with validation and error handling.

### Manual Ingestion

```bash
python scripts/ingest_data.py
```

This will:
1. Validate CSV schema (106 expected columns)
2. Parse CAMEO ontology (actors, verbs, event types)
3. Load events in batches (500 events/batch)
4. Create actor and location nodes
5. Link events to actors, locations, and event types
6. Create event-to-event linkages (second pass)

**Expected duration**: ~5-10 minutes for full 62,141 events

### Verify Ingestion

Check the Neo4j Browser (http://localhost:7474) or run:

```cypher
// Count nodes
MATCH (n) RETURN labels(n) as Label, count(n) as Count

// Sample events
MATCH (e:Event)-[:INITIATED_BY]->(a:Actor)
RETURN e.eventId, e.year, a.name
LIMIT 10
```

## Example Queries

Try these queries in the Streamlit UI:

1. **Temporal Query**:
   - "What events occurred in 1950?"
   - "Show me events between 1960 and 1970"

2. **Actor Analysis**:
   - "Which actors initiated the most events?"
   - "What did the United States do in the 1980s?"

3. **Event Chains**:
   - "Show me events linked to EID40124"
   - "Find sequences of events in the Middle East"

4. **Pattern Analysis**:
   - "What types of events happened most frequently?"
   - "Which regions had the most violent events?"

## Project Structure

```
SpeedKG/
├── src/
│   ├── domain/           # Domain models (Event, Actor, CAMEO)
│   ├── ingestion/        # CSV parsing, schema validation, Neo4j loading
│   ├── intelligence/     # LangGraph agent, Cypher generation, reasoning
│   ├── ui/               # Streamlit interface
│   └── utils/            # Configuration, logging
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── evals/                # Evaluation datasets and runners
├── docs/                 # Architecture and walkthrough documentation
├── data/                 # SPEED CSV and CAMEO files (not committed)
├── logs/                 # Structured logs (not committed)
├── docker-compose.yml    # Container orchestration
└── pyproject.toml        # Python dependencies
```

## Development

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test types
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Generate coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Running Evaluations

```bash
# Run evaluation suite
python evals/run_evals.py

# View results
cat evals/results/results_<timestamp>.json
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/
```

## Architecture

The system follows a layered architecture with domain-driven design principles:

- **UI Layer**: Streamlit interface with chat, sidebar, and trace view
- **Intelligence Layer**: LangGraph agent orchestrating query workflow
- **Data Layer**: Neo4j graph database with CAMEO ontology
- **Integration**: Claude API for Cypher generation and reasoning

See [docs/architecture.md](docs/architecture.md) for detailed C4 diagrams and design decisions.

## Configuration

All configuration is managed via environment variables in `.env`:

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=speedkg123

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Application
LOG_LEVEL=INFO
MAX_SUBGRAPH_NODES=500
QUERY_TIMEOUT_SECONDS=30
```

## Troubleshooting

### Neo4j Connection Issues

**Problem**: "Failed to connect to Neo4j"

**Solution**:
1. Verify Neo4j is running: `docker ps` or `docker-compose ps`
2. Check logs: `docker-compose logs neo4j`
3. Ensure correct credentials in `.env`
4. Try accessing Neo4j Browser: http://localhost:7474

### Ingestion Errors

**Problem**: "CSV validation failed"

**Solution**:
1. Verify `data/ssp_public.csv` has 106 columns
2. Check logs in `logs/` for specific error messages
3. Ensure CAMEO files exist in `data/cameo/`

### Claude API Errors

**Problem**: "Invalid API key"

**Solution**:
1. Verify API key in `.env` is correct
2. Check Anthropic account has credits
3. Ensure no trailing spaces in `.env` file

### Empty Query Results

**Problem**: Queries return no results

**Solution**:
1. Verify data was ingested: `MATCH (n) RETURN count(n)`
2. Check Cypher query in expanded section of UI
3. Review agent trace for errors
4. Try simpler queries first

## Performance

Target metrics:
- Query response time (P95): <3 seconds
- Cypher generation accuracy: >90%
- Answer accuracy: >70%
- Ingestion time: <10 minutes

Current performance can be measured with:
```bash
python evals/run_evals.py
```

## Documentation

- [Architecture](docs/architecture.md) - C4 diagrams, design decisions, technology stack
- [Code Walkthrough](docs/walkthrough.md) - Implementation details (coming soon)
- [Data Model](docs/data_model.md) - Neo4j schema, CAMEO mapping (coming soon)
- [Contributing](CONTRIBUTING.md) - Development workflow (coming soon)

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.11+ |
| LLM | Claude 3.5 Sonnet | Latest |
| Graph DB | Neo4j | 5.16+ |
| Agent Framework | LangGraph | 0.2+ |
| UI | Streamlit | 1.31+ |
| Data Processing | Pandas | 2.2+ |
| Testing | pytest | 8.0+ |
| Logging | structlog | 24.1+ |
| Containers | Docker Compose | - |

## License

This project is for educational and research purposes.

## Acknowledgments

- **SPEED Dataset**: Social, Political and Economic Event Database from Cline Center for Advanced Social Research
- **CAMEO Framework**: Conflict and Mediation Event Observations ontology
- **Anthropic**: Claude API for language understanding and generation
- **Neo4j**: Graph database platform

## Contact

For questions or issues, please open an issue on GitHub or contact the development team.

---

**Status**: Phases 1-4 Complete ✅

- ✅ Phase 1: Data Ingestion & Schema Creation (62,141 events loaded)
- ✅ Phase 2: LangGraph Intelligence Layer (Complete implementation)
- ✅ Phase 3: Evaluation Framework (25 test queries, automated runner)
- ✅ Phase 4: Streamlit UI (Chat interface, trace view, sidebar)
- ⏳ Phase 5: Documentation & Polish (In progress)

**Ready to use!** See [QUICKSTART.md](QUICKSTART.md) for setup instructions.

**⚠️ Note**: Valid Anthropic API key required for queries. Update `.env` with your key.
