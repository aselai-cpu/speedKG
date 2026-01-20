# Contributing to SPEED-CAMEO

Thank you for your interest in contributing to the SPEED-CAMEO Temporal Knowledge Graph & Intelligence System! This guide will help you get started with development, testing, and submitting contributions.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Structure](#project-structure)
3. [Coding Standards](#coding-standards)
4. [Testing Guidelines](#testing-guidelines)
5. [Evaluation-Driven Development](#evaluation-driven-development)
6. [Pull Request Process](#pull-request-process)
7. [Documentation Standards](#documentation-standards)
8. [Common Tasks](#common-tasks)
9. [Troubleshooting](#troubleshooting)

---

## Development Setup

### Prerequisites

- **Python**: 3.11+ (tested with 3.11, 3.12)
- **Docker**: For Neo4j database
- **uv**: Fast Python package manager ([installation guide](https://github.com/astral-sh/uv))
- **Git**: Version control

### Initial Setup

1. **Clone the repository**:
```bash
git clone <repository-url>
cd SpeedKG
```

2. **Create virtual environment with uv**:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**:
```bash
uv pip install -e ".[dev]"
```

4. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env with your configuration:
# - ANTHROPIC_API_KEY (required - get from https://console.anthropic.com/)
# - NEO4J_PASSWORD (default: speedkg123)
# - CLAUDE_MODEL (recommended: claude-3-haiku-20240307 for development)
```

5. **Start Neo4j**:
```bash
docker-compose up -d
```

6. **Verify setup**:
```bash
# Test API key
python scripts/test_api_key.py

# Check Neo4j connection
curl http://localhost:7474
```

7. **Ingest data** (first time only):
```bash
python scripts/ingest_data.py
# Expected: ~5-10 minutes, 62,141 events loaded
```

8. **Run tests**:
```bash
pytest
```

---

## Project Structure

```
SpeedKG/
├── data/                          # Data files (not in git)
│   ├── cameo/                     # CAMEO ontology reference files
│   └── SPEED_1.0/                 # SPEED CSV data
├── docs/                          # Documentation
│   ├── architecture.md            # C4 diagrams, system design
│   ├── data_model.md             # Neo4j schema, CAMEO mapping
│   └── walkthrough.md            # Code walkthrough
├── evals/                         # Evaluation framework
│   ├── test_queries.json         # 25 test queries
│   ├── cypher_generation.json    # Cypher reference tests
│   ├── run_evals.py              # Evaluation runner
│   └── results/                  # Timestamped evaluation results
├── logs/                          # Application logs (not in git)
├── scripts/                       # Utility scripts
│   ├── ingest_data.py            # Data ingestion CLI
│   └── test_api_key.py           # API key validation
├── src/
│   ├── domain/                    # Domain models (DDD)
│   │   ├── actors.py             # Actor utilities
│   │   ├── cameo.py              # CAMEO ontology models
│   │   └── events.py             # Event domain models
│   ├── ingestion/                 # Data ingestion pipeline
│   │   ├── cameo_parser.py       # CAMEO file parsing
│   │   ├── csv_parser.py         # SPEED CSV parsing
│   │   ├── neo4j_loader.py       # Two-pass Neo4j loading
│   │   └── schema_validator.py   # Pre-ingestion validation
│   ├── intelligence/              # LangGraph agent
│   │   ├── agent.py              # Workflow orchestration
│   │   ├── cypher_gen.py         # Cypher generation
│   │   ├── graph_retrieval.py    # Adaptive subgraph retrieval
│   │   ├── intent_classifier.py  # Intent classification
│   │   ├── reasoning.py          # Claude reasoning
│   │   └── state.py              # Agent state management
│   ├── ui/                        # Streamlit interface
│   │   ├── app.py                # Main application
│   │   └── components/           # UI components
│   │       ├── chat.py           # Chat interface
│   │       ├── sidebar.py        # Schema/status sidebar
│   │       └── trace_view.py     # Agent trace visualization
│   └── utils/                     # Shared utilities
│       ├── config.py             # Configuration management
│       └── logging.py            # Structured logging
├── tests/
│   ├── unit/                      # Unit tests (fast, isolated)
│   ├── integration/               # Integration tests (require Neo4j)
│   └── e2e/                       # End-to-end tests (UI + Agent)
├── .env.example                   # Environment variable template
├── docker-compose.yml             # Neo4j container configuration
├── pyproject.toml                 # Python project configuration
├── README.md                      # Quick start guide
├── QUICKSTART.md                  # 5-minute setup guide
└── STATUS.md                      # System operational status

```

**Key Files** (prioritize understanding these):
1. `src/ingestion/neo4j_loader.py` - Data loading with two-pass strategy
2. `src/intelligence/agent.py` - LangGraph workflow orchestration
3. `src/intelligence/cypher_gen.py` - Cypher generation with few-shot prompting
4. `src/intelligence/graph_retrieval.py` - Adaptive subgraph retrieval
5. `src/ui/app.py` - Main Streamlit application

---

## Coding Standards

### Python Style

**Formatter**: `black` (line length: 100)
```bash
black src/ tests/
```

**Linter**: `ruff`
```bash
ruff check src/ tests/
```

**Type Checking**: `mypy` (gradual typing)
```bash
mypy src/
```

### Code Conventions

1. **Domain-Driven Design (DDD)**:
   - Keep domain models pure (no external dependencies in `src/domain/`)
   - Business logic in domain layer, infrastructure in separate modules

2. **Type Hints**:
   ```python
   def generate_actor_id(name: str) -> str:
       """Generate stable actor ID from name."""
       ...
   ```

3. **Docstrings** (Google style):
   ```python
   def parse_cameo_actors(file_path: str) -> list[CAMEOActorType]:
       """Parse CAMEO actor ontology from file.

       Args:
           file_path: Path to CAMEO actors file

       Returns:
           List of CAMEOActorType domain objects

       Raises:
           FileNotFoundError: If file doesn't exist
           ValueError: If file format is invalid
       """
       ...
   ```

4. **Error Handling**:
   ```python
   # Specific exceptions
   try:
       result = api_call()
   except AuthenticationError as e:
       logger.error(f"API auth failed: {e}")
       raise
   except APIError as e:
       logger.warning(f"API error, retrying: {e}")
       # Retry logic
   ```

5. **Logging** (use structlog):
   ```python
   import structlog

   logger = structlog.get_logger(__name__)

   logger.info("event_created", event_id=event.eventId, year=event.year)
   logger.error("cypher_invalid", query=cypher, error=str(e))
   ```

6. **Configuration**:
   - Never hardcode values - use `src/utils/config.py`
   - All secrets in environment variables
   - Use `pydantic` for config validation

### File Organization

- **One class per file** (unless closely related)
- **Max file length**: ~500 lines (refactor if longer)
- **Module imports**:
  ```python
  # Standard library
  import hashlib
  from datetime import datetime

  # Third-party
  import pandas as pd
  from neo4j import GraphDatabase

  # Local
  from src.domain.events import Event
  from src.utils.logging import get_logger
  ```

---

## Testing Guidelines

### Test Pyramid

Target distribution:
- **70% Unit Tests**: Fast, isolated, no external dependencies
- **20% Integration Tests**: Require Neo4j, test interactions
- **10% E2E Tests**: Full workflow tests (UI → Agent → Neo4j)

### Writing Unit Tests

**Location**: `tests/unit/`

```python
# tests/unit/test_actors.py
import pytest
from src.domain.actors import generate_actor_id

def test_generate_actor_id_consistent():
    """Actor ID should be consistent for same name."""
    assert generate_actor_id("Hamas") == generate_actor_id("Hamas")

def test_generate_actor_id_case_insensitive():
    """Actor ID should be case-insensitive."""
    assert generate_actor_id("Hamas") == generate_actor_id("hamas")

def test_generate_actor_id_whitespace_normalized():
    """Whitespace should be normalized."""
    assert generate_actor_id("  Hamas  ") == generate_actor_id("Hamas")
```

**Best Practices**:
- One assertion per test (or closely related assertions)
- Descriptive test names: `test_<what>_<condition>_<expected>`
- Use fixtures for common setup
- Mock external dependencies (API calls, database)

### Writing Integration Tests

**Location**: `tests/integration/`

```python
# tests/integration/test_neo4j_loader.py
import pytest
from neo4j import GraphDatabase
from src.ingestion.neo4j_loader import Neo4jLoader
from src.utils.config import get_config

@pytest.fixture
def neo4j_driver():
    """Provide Neo4j driver for tests."""
    config = get_config()
    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    )
    yield driver
    driver.close()

def test_load_events_creates_nodes(neo4j_driver):
    """Loading events should create Event nodes in Neo4j."""
    loader = Neo4jLoader()
    # Load test data
    loader.load_events(test_events)

    # Verify in database
    with neo4j_driver.session() as session:
        result = session.run("MATCH (e:Event) RETURN count(e) as count")
        count = result.single()["count"]
        assert count > 0
```

**Best Practices**:
- Use fixtures for database setup/teardown
- Clean up test data after each test
- Test actual database state, not just mocks
- Mark slow tests: `@pytest.mark.slow`

### Writing E2E Tests

**Location**: `tests/e2e/`

```python
# tests/e2e/test_query_workflow.py
from src.intelligence.agent import IntelligenceAgent

def test_actor_analysis_query_e2e():
    """Full workflow: query → intent → Cypher → retrieval → reasoning."""
    agent = IntelligenceAgent()

    result = agent.query("What are the top 5 most active actors?")

    # Verify workflow completion
    assert result['final_response'] is not None
    assert result['cypher_query'] is not None
    assert 'Hamas' in result['final_response'] or 'Israeli' in result['final_response']

    # Verify trace
    trace = result['trace']
    assert any(step['step'] == 'parse_intent' for step in trace)
    assert any(step['step'] == 'generate_cypher' for step in trace)

    agent.close()
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only (fast)
pytest tests/unit/

# Integration tests (requires Neo4j)
pytest tests/integration/

# E2E tests
pytest tests/e2e/

# With coverage report
pytest --cov=src --cov-report=html

# Specific test
pytest tests/unit/test_actors.py::test_generate_actor_id_consistent

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Coverage Requirements

- **Minimum**: 80% overall coverage
- **Critical paths**: 90%+ coverage
  - `src/ingestion/` (data integrity critical)
  - `src/intelligence/cypher_gen.py` (security critical)
  - `src/domain/` (core business logic)

**Check coverage**:
```bash
pytest --cov=src --cov-report=term-missing
# View HTML report
open htmlcov/index.html
```

---

## Evaluation-Driven Development

The project uses **Evaluation-Driven Development (EDD)** to continuously measure and improve quality.

### Running Evaluations

```bash
# Full evaluation suite
python evals/run_evals.py

# Results saved to: evals/results/eval_YYYYMMDD_HHMMSS.json
```

**Evaluation Metrics**:
1. **Cypher Accuracy**: % of syntactically valid queries (target: >90%)
2. **Answer Accuracy**: Manually evaluated correctness (target: >70%)
3. **Latency**: P50, P95, P99 response times (target P95: <3000ms)
4. **Coverage**: % of test queries successfully answered (target: >85%)

### Adding Test Queries

Edit `evals/test_queries.json`:

```json
{
  "queries": [
    {
      "id": "TQ026",
      "query": "What events involved Hamas in 2000?",
      "intent": "actor_analysis",
      "difficulty": "medium",
      "expected_criteria": {
        "should_mention": ["Hamas", "2000"],
        "should_include_cypher": true,
        "min_events": 10
      }
    }
  ]
}
```

### Adding Cypher Reference Tests

Edit `evals/cypher_generation.json`:

```json
{
  "cypher_tests": [
    {
      "id": "CQ013",
      "natural_query": "Find events in Jerusalem during 1990s",
      "reference_cypher": "MATCH (e:Event)-[:OCCURRED_AT]->(l:Location {name: 'Jerusalem'}) WHERE e.year >= 1990 AND e.year < 2000 RETURN e ORDER BY e.year",
      "validation_criteria": {
        "must_have_location_filter": true,
        "must_have_temporal_filter": true
      }
    }
  ]
}
```

### Iteration Process

1. **Run baseline evaluation**: `python evals/run_evals.py`
2. **Analyze failures**: Review `evals/results/` for error patterns
3. **Make improvements**:
   - Update few-shot examples in `src/intelligence/cypher_gen.py`
   - Adjust retrieval strategies in `src/intelligence/graph_retrieval.py`
   - Refine system prompts
4. **Re-evaluate**: Run evals again, compare with baseline
5. **Document**: Update `evals/iteration_log.md` with changes and results

**Example Iteration**:
```markdown
## Iteration 2 - 2026-01-21

### Changes
- Added 2 new few-shot examples for temporal queries
- Increased event_chain max_nodes from 300 to 400
- Refined intent classifier prompt for geographic queries

### Results
- Cypher Accuracy: 87% → 93% (+6%)
- Answer Accuracy: 68% → 74% (+6%)
- Avg Latency: 450ms → 520ms (+70ms, acceptable)

### Next Steps
- Investigate 3 remaining Cypher failures
- Add few-shot example for location hierarchy queries
```

---

## Pull Request Process

### Before Submitting

1. **Ensure all tests pass**:
   ```bash
   pytest
   ```

2. **Check code quality**:
   ```bash
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

3. **Run evaluations** (for intelligence layer changes):
   ```bash
   python evals/run_evals.py
   ```

4. **Update documentation** if needed:
   - Add docstrings to new functions/classes
   - Update `docs/` if architecture/schema changed
   - Update `README.md` if user-facing changes

### PR Checklist

- [ ] Code follows style guidelines (black, ruff, mypy pass)
- [ ] Tests added/updated for new functionality
- [ ] All tests pass (`pytest`)
- [ ] Coverage remains >80% (`pytest --cov=src`)
- [ ] Evaluations run (if intelligence changes)
- [ ] Documentation updated
- [ ] No sensitive data (API keys, credentials) committed
- [ ] Descriptive commit messages
- [ ] PR description explains changes and motivation

### PR Template

```markdown
## Description
Brief description of changes and why they're needed.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix/feature causing existing functionality to break)
- [ ] Documentation update

## Changes Made
- Changed X to improve Y
- Added Z for better performance
- Refactored W for clarity

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] E2E tests pass (if applicable)
- [ ] Manual testing performed: [describe]

## Evaluation Results (if applicable)
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Cypher Accuracy | 90% | 93% | +3% |
| Answer Accuracy | 70% | 72% | +2% |
| Avg Latency | 450ms | 470ms | +20ms |

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No breaking changes (or documented in description)
```

### Review Process

1. **Automated checks**: CI runs tests, linters, coverage
2. **Code review**: Maintainer reviews for:
   - Correctness and quality
   - Test coverage
   - Documentation
   - Performance implications
3. **Evaluation review**: For intelligence changes, check metrics
4. **Approval**: At least 1 maintainer approval required
5. **Merge**: Squash and merge to main branch

---

## Documentation Standards

### Code Documentation

**Module Docstrings**:
```python
"""
CAMEO Ontology Parser

Parses CAMEO reference files (actors, verbs, options) into domain models.
Handles hierarchical codes, temporal markers, and validation.

See Also:
    - docs/data_model.md for CAMEO schema details
    - data/cameo/ for reference files
"""
```

**Class Docstrings**:
```python
class Neo4jLoader:
    """
    Loads SPEED event data into Neo4j using two-pass strategy.

    Pass 1 creates all Event, Actor, Location nodes and their relationships.
    Pass 2 creates LINKED_TO relationships between events (requires all events to exist).

    Attributes:
        driver: Neo4j driver instance
        batch_size: Events per transaction (default: 500)

    Example:
        loader = Neo4jLoader()
        loader.load_events(events)
        loader.load_linked_events(events)
        loader.close()
    """
```

**Function Docstrings**:
```python
def generate_cypher(
    query: str,
    intent: QueryIntent,
    schema: str
) -> tuple[str, bool]:
    """
    Generate Cypher query from natural language using Claude with few-shot prompting.

    Args:
        query: Natural language query from user
        intent: Classified intent (actor_analysis, temporal_analysis, etc.)
        schema: Neo4j schema description for context

    Returns:
        Tuple of (generated_cypher, is_valid):
            - generated_cypher: Cypher query string
            - is_valid: Whether query passed security validation

    Raises:
        AnthropicAPIError: If Claude API call fails

    Example:
        cypher, valid = generate_cypher(
            "What are the top 5 actors?",
            QueryIntent.ACTOR_ANALYSIS,
            schema_description
        )
    """
```

### Architecture Documentation

When making architectural changes, update:

1. **docs/architecture.md**:
   - Update C4 diagrams if components/containers change
   - Document new patterns or decisions
   - Update technology stack table

2. **docs/data_model.md**:
   - Add new node/relationship types
   - Update example queries
   - Document schema evolution steps

3. **docs/walkthrough.md**:
   - Add walkthroughs for new major features
   - Update code snippets if implementation changes

### User-Facing Documentation

1. **README.md**: Quick start and overview
2. **QUICKSTART.md**: Step-by-step setup (keep to 5 minutes)
3. **STATUS.md**: Current operational status and test results

---

## Common Tasks

### Adding a New Intent Type

1. **Update `src/intelligence/state.py`**:
   ```python
   class QueryIntent(str, Enum):
       # ... existing intents ...
       NEW_INTENT = "new_intent"
   ```

2. **Update `src/intelligence/intent_classifier.py`**:
   ```python
   # Add to system prompt
   "- new_intent: For queries about XYZ"
   ```

3. **Add retrieval strategy in `src/intelligence/graph_retrieval.py`**:
   ```python
   RETRIEVAL_STRATEGIES = {
       # ... existing strategies ...
       QueryIntent.NEW_INTENT: {
           'max_hops': 2,
           'max_nodes': 400,
           # ... strategy details
       }
   }
   ```

4. **Add few-shot examples in `src/intelligence/cypher_gen.py`**:
   ```python
   FEW_SHOT_EXAMPLES = """
   # ... existing examples ...

   **Example 9: New Intent Type**
   User: "Example query for new intent"
   Cypher:
   MATCH ...
   RETURN ...
   """
   ```

5. **Add test queries in `evals/test_queries.json`**:
   ```json
   {
     "id": "TQ_NEW_001",
     "query": "Example query",
     "intent": "new_intent",
     "difficulty": "medium"
   }
   ```

6. **Run evaluations**: `python evals/run_evals.py`

### Adding a New Data Source

1. **Update domain models** in `src/domain/` if schema differs
2. **Create parser** in `src/ingestion/` (follow `csv_parser.py` pattern)
3. **Update `neo4j_loader.py`** to handle new source:
   ```python
   # Use labels to distinguish sources
   CREATE (e:Event:NewSource {...})
   ```
4. **Update `docs/data_model.md`** with new schema elements
5. **Add integration tests** for new ingestion path
6. **Update `scripts/ingest_data.py`** CLI

### Optimizing Query Performance

1. **Profile query**:
   ```cypher
   PROFILE
   MATCH (e:Event)-[:INITIATED_BY]->(a:Actor)
   WHERE e.year = 2000
   RETURN a.name, count(e)
   ```

2. **Check index usage**: Look for "NodeByLabelScan" (bad) vs "NodeIndexSeek" (good)

3. **Add indexes if needed**:
   ```cypher
   CREATE INDEX event_year IF NOT EXISTS
   FOR (e:Event) ON (e.year);
   ```

4. **Update retrieval strategy** in `graph_retrieval.py` if needed

5. **Document in `docs/data_model.md`** under Schema Evolution

### Debugging Agent Failures

1. **Check trace**:
   ```python
   result = agent.query("query")
   for step in result['trace']:
       print(f"{step['step']}: {step.get('error', 'OK')}")
   ```

2. **Enable debug logging**:
   ```python
   # In .env
   LOG_LEVEL=DEBUG

   # Check logs/
   tail -f logs/speedkg.log
   ```

3. **Test Cypher directly**:
   ```python
   # Copy Cypher from trace
   # Run in Neo4j Browser at http://localhost:7474
   ```

4. **Check subgraph retrieval**:
   ```python
   from src.intelligence.graph_retrieval import GraphRetrieval

   retriever = GraphRetrieval()
   subgraph = retriever.retrieve(cypher_query, intent)
   print(f"Nodes: {len(subgraph['nodes'])}")
   print(f"Rels: {len(subgraph['relationships'])}")
   ```

---

## Troubleshooting

### Tests Failing

**Issue**: `ImportError: cannot import name 'X'`
- **Fix**: Ensure virtual environment activated, dependencies installed
  ```bash
  source .venv/bin/activate
  uv pip install -e ".[dev]"
  ```

**Issue**: Integration tests fail with connection error
- **Fix**: Verify Neo4j running
  ```bash
  docker-compose ps
  docker-compose up -d  # If not running
  ```

**Issue**: `pytest: command not found`
- **Fix**: Install dev dependencies
  ```bash
  uv pip install -e ".[dev]"
  ```

### Evaluation Issues

**Issue**: Cypher accuracy dropped after changes
- **Diagnosis**: Review `evals/results/` for specific failures
- **Fix**: Add few-shot examples for failing patterns

**Issue**: Latency increased significantly
- **Diagnosis**: Check if retrieval strategy changed (max_nodes, max_hops)
- **Fix**: Profile Neo4j queries, optimize indexes

### Development Setup

**Issue**: `docker-compose up` fails
- **Fix**: Check port conflicts (7474, 7687, 8501)
  ```bash
  lsof -i :7474
  lsof -i :7687
  # Kill conflicting processes or change ports in docker-compose.yml
  ```

**Issue**: API calls fail with authentication error
- **Fix**: Verify API key in `.env`
  ```bash
  python scripts/test_api_key.py
  ```

**Issue**: Ingestion fails with encoding error
- **Fix**: Ensure CSV files use latin1 encoding (already handled in `csv_parser.py`)

---

## Additional Resources

- **Architecture**: `docs/architecture.md` (C4 diagrams, design decisions)
- **Data Model**: `docs/data_model.md` (Neo4j schema, CAMEO mapping)
- **Code Walkthrough**: `docs/walkthrough.md` (detailed implementation guide)
- **Quick Start**: `QUICKSTART.md` (5-minute setup)
- **Status**: `STATUS.md` (current system health)

---

## Getting Help

- **Documentation**: Check `docs/` directory first
- **Logs**: Review `logs/speedkg.log` for errors
- **Neo4j Browser**: http://localhost:7474 (explore data directly)
- **Issues**: Check existing issues before creating new ones
- **Debugging**: Use `LOG_LEVEL=DEBUG` in `.env` for verbose output

---

## License

[Add license information here]

---

**Last Updated**: 2026-01-20
**Maintainers**: SPEED-CAMEO Team

Thank you for contributing to SPEED-CAMEO! Your efforts help improve historical event analysis and knowledge graph intelligence.
