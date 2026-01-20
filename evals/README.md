# Evaluation Framework

Evaluation-Driven Development (EDD) framework for the SPEED-CAMEO Intelligence Agent.

## Overview

This directory contains the evaluation infrastructure for measuring and improving the intelligence agent's performance. We follow an EDD methodology: measure baseline, identify failures, improve, re-measure, repeat.

## Directory Structure

```
evals/
├── README.md                    # This file
├── test_queries.json            # 25 test queries covering all intents
├── cypher_generation.json       # 12 Cypher generation test cases
├── iteration_log.md             # Tracks iterations and improvements
├── run_evals.py                 # Main evaluation runner
└── results/                     # Timestamped evaluation results
    └── eval_results_YYYYMMDD_HHMMSS.json
```

## Test Datasets

### test_queries.json

Contains 25 diverse test queries covering:
- **Pattern Analysis** (6 queries): Aggregations, comparisons, trends
- **Geographic Analysis** (5 queries): Location-based queries
- **Actor Analysis** (7 queries): Actor actions, relationships, targeting
- **Temporal Analysis** (5 queries): Time-based trends, year-over-year
- **Event Chain** (2 queries): Linked events, sequences

Each test case includes:
- Query text
- Expected intent
- Expected Cypher criteria (keywords, filters, aggregations)
- Difficulty level (easy/medium/hard)

### cypher_generation.json

Contains 12 reference Cypher queries with:
- Natural language query
- Reference Cypher implementation
- Validation criteria (must_have, should_not_have, semantic checks)

Used to evaluate Cypher generation accuracy against known-good queries.

## Evaluation Metrics

### 1. Cypher Generation Accuracy
**Target: >90%**

Percentage of queries that produce syntactically and semantically valid Cypher.

**Measured by:**
- Syntax validation (no Neo4j errors)
- Presence of expected keywords (MATCH, WHERE, etc.)
- Correct filtering and aggregation
- Security validation (no DELETE/DROP/etc.)

### 2. Answer Accuracy
**Target: >70%**

Percentage of queries that produce factually correct answers.

**Measured by:**
- Factual correctness against expected results
- Citation accuracy
- Completeness of answer
- Relevance to query

### 3. Latency
**Target: P95 <3000ms**

Response time performance.

**Measured by:**
- P50 (median)
- P95 (95th percentile)
- P99 (99th percentile)
- Mean latency

### 4. Coverage
**Target: >85%**

Percentage of test queries successfully answered (no errors).

**Measured by:**
- Successful completion rate
- Error rate by category
- Intent coverage (all intents tested)

## Running Evaluations

### Full Evaluation Suite

```bash
# Run all evaluations
python evals/run_evals.py
```

This will:
1. Load test datasets
2. Run queries through the agent
3. Measure all metrics
4. Save results to `results/eval_results_<timestamp>.json`
5. Print summary report

### Expected Output

```
================================================================================
SPEED-CAMEO INTELLIGENCE AGENT EVALUATION
================================================================================
Timestamp: 2026-01-20T10:30:00

Initializing agent...
✓ Agent initialized

Evaluating 25 test queries...
--------------------------------------------------------------------------------

[1/25] Q001: What are the top 5 most active actors?...
  ✓ Cypher valid: True, Results: 5, Latency: 1234ms

...

================================================================================
EVALUATION SUMMARY
================================================================================

Overall Success Rate: 88.0%
Cypher Accuracy:      92.0%
Coverage:             88.0%

Latency:
  P50: 1500ms
  P95: 2800ms
  P99: 3200ms

Target Achievement:
  ✓ cypher_accuracy
  ✓ coverage
  ✓ latency

================================================================================

✓ Results saved to: evals/results/eval_results_20260120_103000.json
```

### Interpreting Results

**Results JSON Structure:**
```json
{
  "timestamp": "2026-01-20T10:30:00",
  "test_query_evaluation": {
    "total_queries": 25,
    "successful": 22,
    "success_rate": 0.88,
    "cypher_accuracy": 0.92,
    "latencies": {...},
    "results": [...]
  },
  "cypher_generation_evaluation": {
    "total_cases": 12,
    "passed": 11,
    "accuracy": 0.917,
    "results": [...]
  },
  "summary": {
    "overall_success_rate": 0.88,
    "cypher_accuracy": 0.92,
    "meets_targets": {...}
  }
}
```

## Iteration Workflow

### 1. Run Baseline

```bash
python evals/run_evals.py
```

### 2. Analyze Failures

Look at results JSON:
- Which queries failed?
- What were the error types?
- Are there common patterns?

### 3. Identify Root Causes

Common failure modes:
- **Intent misclassification**: Wrong retrieval strategy
- **Cypher syntax errors**: Missing schema info in prompt
- **Cypher semantic errors**: Wrong logic despite valid syntax
- **Empty results**: Valid Cypher but wrong query
- **Reasoning failures**: Poor subgraph formatting or unclear instructions

### 4. Implement Improvements

Targeted fixes:
- Add few-shot examples for failing patterns
- Clarify schema descriptions
- Adjust retrieval strategies
- Improve reasoning prompts
- Add query preprocessing

### 5. Re-evaluate

```bash
python evals/run_evals.py
```

### 6. Document in iteration_log.md

Record:
- Changes made
- Metrics before/after
- Lessons learned
- Next steps

### 7. Repeat

Continue until all targets met.

## Failure Mode Analysis

### Common Patterns

**Pattern 1: Complex Multi-Actor Queries**
- Example: "What was the relationship between Hamas and Israel?"
- Failure: Incorrect Cypher with multiple MATCH clauses
- Fix: Add few-shot example with actor-actor relationships

**Pattern 2: Temporal Range Queries**
- Example: "Events between 2000 and 2005"
- Failure: Using `year = 2000` instead of `year >= 2000 AND year <= 2005`
- Fix: Add few-shot example with range filtering

**Pattern 3: Ambiguous Location Names**
- Example: "What happened in Georgia?" (country or US state?)
- Failure: Wrong disambiguation
- Fix: Add query preprocessing or clarification in reasoning

**Pattern 4: Property Access in JSON**
- Example: "Events where property was damaged"
- Failure: Incorrect propertiesJson access
- Fix: Add few-shot example with JSON property access

## Best Practices

1. **Run evaluations frequently**: After every significant change
2. **Track all iterations**: Document in iteration_log.md
3. **Focus on patterns**: Don't optimize for individual failures
4. **Prioritize improvements**: High-impact, low-effort first
5. **Version control**: Tag commits with evaluation results
6. **Compare across iterations**: Track progress over time

## Extending Evaluations

### Adding New Test Cases

Edit `test_queries.json`:
```json
{
  "id": "Q026",
  "query": "Your new test query",
  "intent": "pattern_analysis",
  "expected_criteria": {
    "cypher_contains": ["MATCH", "WHERE"],
    "should_return_actors": true
  },
  "difficulty": "medium"
}
```

### Adding Custom Metrics

Edit `run_evals.py`:
```python
def _evaluate_custom_metric(self, results):
    # Your custom evaluation logic
    return metric_value
```

### Comparing Iterations

```bash
# List all evaluation results
ls -lt evals/results/

# Compare two specific runs
diff evals/results/eval_results_20260120_100000.json \
     evals/results/eval_results_20260120_110000.json
```

## Troubleshooting

**Evaluation hangs:**
- Check Neo4j connection
- Check Anthropic API key
- Verify no infinite loops in Cypher

**Low Cypher accuracy:**
- Review failed queries in results JSON
- Check if schema description is accurate
- Add more few-shot examples

**High latency:**
- Check subgraph expansion (too many nodes?)
- Optimize Cypher queries (add indexes)
- Consider reducing max_tokens for reasoning

**Empty results:**
- Verify data exists in Neo4j for test queries
- Check filters are correct (exact match vs CONTAINS)
- Validate event IDs and actor names in test cases

## Next Steps

1. **Update API key** in `.env` to run evaluations
2. **Run baseline** evaluation to establish metrics
3. **Analyze failures** and identify top 3 patterns
4. **Implement improvements** targeting those patterns
5. **Re-evaluate** and compare to baseline
6. **Iterate** until targets achieved

---

**Target Achievement:**
- Cypher Accuracy: >90%
- Answer Accuracy: >70%
- Latency P95: <3000ms
- Coverage: >85%

Track progress in `iteration_log.md`.
