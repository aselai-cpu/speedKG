# SPEED-CAMEO Quick Start Guide

Get the SPEED-CAMEO Temporal Knowledge Graph Intelligence system running in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Valid Anthropic API key
- ~2GB disk space

## Step 1: Clone and Navigate

```bash
cd /path/to/SpeedKG
```

## Step 2: Configure Environment

Create `.env` file with your credentials:

```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=speedkg123

# Anthropic API - UPDATE THIS!
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here

# Application Settings
LOG_LEVEL=INFO
CLAUDE_MODEL=claude-3-sonnet-20240229
MAX_SUBGRAPH_NODES=500
QUERY_TIMEOUT_SECONDS=30

# Ingestion Settings
BATCH_SIZE=500
CHUNK_SIZE=1000
```

**⚠️ IMPORTANT**: Replace `ANTHROPIC_API_KEY` with your actual key from https://console.anthropic.com/

## Step 3: Start Neo4j

```bash
docker-compose up -d
```

Verify Neo4j is running:
```bash
docker-compose ps
# Should show neo4j as "Up"
```

Access Neo4j Browser: http://localhost:7474
- Username: `neo4j`
- Password: `speedkg123`

## Step 4: Install Dependencies

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Step 5: Verify Data

Check if data is already loaded:

```bash
source .venv/bin/activate
python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'speedkg123'))
with driver.session() as session:
    result = session.run('MATCH (e:Event) RETURN count(e) as count')
    count = result.single()['count']
    print(f'Events in database: {count:,}')
driver.close()
"
```

**If you see 0 events**, load the data:

```bash
# Validate CSV
python scripts/ingest_data.py --validate-only

# Full ingestion (~3 minutes)
python scripts/ingest_data.py --batch-size 500
```

You should see:
```
✅ INGESTION COMPLETE

Database Statistics:
  Event: 62,141
  Actor: 1,707
  Location: 5,783
  ...
```

## Step 6: Launch the UI

```bash
./run_ui.sh
```

Or manually:
```bash
source .venv/bin/activate
streamlit run src/ui/app.py
```

The UI will open at: **http://localhost:8501**

## Step 7: Try Example Queries

In the UI, try these queries:

1. **"What are the top 5 most active actors?"**
   - Tests pattern analysis
   - Should return actor names with event counts

2. **"What events occurred in Palestine in 2003?"**
   - Tests geographic + temporal filtering
   - Should return events from Palestine in 2003

3. **"How many protests occurred each year?"**
   - Tests temporal aggregation
   - Should return year-by-year protest counts

4. **"What actions did Hamas take between 2000 and 2005?"**
   - Tests actor analysis with time range
   - Should return events initiated by Hamas

## Troubleshooting

### Neo4j Connection Failed

```bash
# Check if Neo4j is running
docker-compose ps

# View Neo4j logs
docker-compose logs neo4j

# Restart Neo4j
docker-compose restart neo4j
```

### Agent Initialization Failed

**Check API key:**
```bash
cat .env | grep ANTHROPIC_API_KEY
```

**Test API key:**
```bash
source .venv/bin/activate
python -c "
from anthropic import Anthropic
client = Anthropic(api_key='your-key-here')
response = client.messages.create(
    model='claude-3-sonnet-20240229',
    max_tokens=100,
    messages=[{'role': 'user', 'content': 'Hello'}]
)
print('✓ API key valid')
"
```

### UI Not Loading

```bash
# Check Streamlit is installed
streamlit --version

# Check port 8501 is available
lsof -i :8501

# View detailed logs
streamlit run src/ui/app.py --logger.level=debug
```

### No Results from Queries

**Check data exists:**
```bash
python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'speedkg123'))
with driver.session() as session:
    # Check events
    result = session.run('MATCH (e:Event) RETURN count(e) as count')
    print(f'Events: {result.single()[\"count\"]:,}')

    # Check actors
    result = session.run('MATCH (a:Actor) RETURN count(a) as count')
    print(f'Actors: {result.single()[\"count\"]:,}')
driver.close()
"
```

**If counts are 0**, re-run ingestion (Step 5).

## System Architecture

```
┌─────────────┐
│  Streamlit  │ ← http://localhost:8501
│     UI      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  LangGraph  │
│    Agent    │
├─────────────┤
│  - Intent   │
│  - Cypher   │
│  - Retrieve │
│  - Reason   │
└──────┬──────┘
       │
       ├──────────► Neo4j (localhost:7687)
       │              - 62,141 Events
       │              - CAMEO Ontology
       │
       └──────────► Claude API
                      - Intent classification
                      - Cypher generation
                      - Reasoning
```

## Data Overview

**SPEED Dataset:**
- 62,141 historical events (1946-2008)
- Sources: News articles, historical records
- Coverage: Conflicts, protests, coups, government actions

**CAMEO Ontology:**
- 7,032 actor types (countries, groups, organizations)
- 284 event types (hierarchical classification)
- 20 root event categories (statements, appeals, protests, violence, etc.)

**Graph Structure:**
- **Nodes**: Event, Actor, Location, EventType, CAMEOActorType
- **Relationships**: INITIATED_BY, TARGETED, VICTIMIZED, OCCURRED_AT, OF_TYPE, LINKED_TO

## Next Steps

### 1. Explore the Data

Try diverse query types:
- Pattern analysis: "What are the most common event types?"
- Geographic: "Compare events in Middle East vs South America"
- Temporal: "How did violence trends change over time?"
- Actor relationships: "Which actors targeted each other most?"

### 2. Run Evaluations

Test agent performance:

```bash
python evals/run_evals.py
```

View results:
```bash
python evals/compare_results.py evals/results/*.json
```

### 3. Customize

**Adjust retrieval strategies:**
- Edit `src/intelligence/graph_retrieval.py`
- Modify `RETRIEVAL_STRATEGIES` dict

**Add few-shot examples:**
- Edit `src/intelligence/cypher_gen.py`
- Add to `FEW_SHOT_EXAMPLES`

**Improve reasoning:**
- Edit `src/intelligence/reasoning.py`
- Modify `SYSTEM_PROMPT`

### 4. Deploy

**Docker Compose (Production):**

Update `docker-compose.yml` to include Streamlit:

```yaml
services:
  neo4j:
    # ... existing config

  streamlit:
    build: .
    ports:
      - "8501:8501"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - neo4j
```

Then:
```bash
docker-compose up -d
```

## Documentation

- **Architecture**: `docs/architecture.md`
- **Data Model**: `docs/data_model.md`
- **UI Guide**: `src/ui/README.md`
- **Evaluation**: `evals/README.md`
- **Main README**: `README.md`

## Support

**Common Issues**: Check `TROUBLESHOOTING.md`

**Report Bugs**: GitHub Issues

**Questions**: See documentation in `docs/`

---

## Summary Checklist

- [ ] `.env` file created with valid API key
- [ ] Neo4j running (`docker-compose up -d`)
- [ ] Dependencies installed (`pip install -e .`)
- [ ] Data loaded (62,141 events in Neo4j)
- [ ] UI running at http://localhost:8501
- [ ] Example queries working

**Status Check:**
```bash
# All should show "✓"
docker-compose ps               # ✓ Neo4j Up
source .venv/bin/activate      # ✓ Environment active
streamlit --version            # ✓ Streamlit installed
curl http://localhost:7474     # ✓ Neo4j accessible
curl http://localhost:8501     # ✓ UI accessible
```

If all checks pass, you're ready to explore! 🚀
