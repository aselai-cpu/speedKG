# Evaluation Iteration Log

This log tracks evaluation results and improvements over time following the Evaluation-Driven Development (EDD) methodology.

## Target Metrics

| Metric | Target | Priority |
|--------|--------|----------|
| Cypher Accuracy | >90% | High |
| Answer Accuracy | >70% | High |
| Latency P95 | <3000ms | Medium |
| Coverage | >85% | High |

---

## Baseline (Iteration 0)

**Date**: 2026-01-20
**Status**: ⏳ Pending - Blocked by API key
**Branch**: `main`

### Configuration
- Model: claude-3-sonnet-20240229
- Few-shot examples: 8
- Retrieval strategies: 6 intent-based
- Max subgraph nodes: 500

### Metrics
- Cypher Accuracy: **N/A** (API key issue)
- Answer Accuracy: **N/A**
- Latency P50: **N/A**
- Latency P95: **N/A**
- Coverage: **N/A**

### Observations
- All Phase 2 components implemented
- Unable to test due to invalid Anthropic API key
- Test infrastructure ready

### Next Steps
1. Update API key to valid credentials
2. Run baseline evaluation
3. Analyze failure modes
4. Plan first iteration improvements

---

## Iteration 1

**Date**: [TBD]
**Status**: 🔄 Planned
**Branch**: [TBD]

### Planned Changes
- [ ] Update API key
- [ ] Run baseline evaluation
- [ ] Identify top 3 failure modes
- [ ] Improve Cypher few-shot examples based on failures
- [ ] Adjust retrieval strategies if needed

### Expected Improvements
- Target Cypher Accuracy: 70-80%
- Target Coverage: 60-70%

---

## Iteration 2

**Date**: [TBD]
**Status**: 🔄 Planned

### Planned Changes
- [ ] Enhance intent classification with more examples
- [ ] Add query preprocessing (spelling, normalization)
- [ ] Improve error messages and fallback handling
- [ ] Add query expansion for ambiguous terms

### Expected Improvements
- Target Cypher Accuracy: 85%
- Target Coverage: 75%

---

## Iteration 3

**Date**: [TBD]
**Status**: 🔄 Planned

### Planned Changes
- [ ] Optimize subgraph retrieval (reduce noise)
- [ ] Improve reasoning prompt structure
- [ ] Add citation validation
- [ ] Fine-tune retrieval hop depths

### Expected Improvements
- Target Answer Accuracy: 70%+
- Target Latency P95: <3000ms

---

## Analysis Framework

For each iteration, analyze:

1. **Failure Modes**: What types of queries fail?
   - Intent classification errors
   - Cypher syntax errors
   - Cypher semantic errors (wrong logic)
   - Empty results (valid Cypher, wrong query)
   - Reasoning failures

2. **Patterns**: Are there common failure patterns?
   - Specific intents failing more
   - Complex queries vs simple queries
   - Temporal queries issues
   - Multi-actor relationship queries

3. **Root Causes**: Why do failures occur?
   - Insufficient few-shot examples
   - Schema mismatch in prompt
   - Retrieval strategy too narrow/broad
   - Reasoning prompt unclear

4. **Improvement Strategies**:
   - Add targeted few-shot examples
   - Clarify schema descriptions
   - Adjust retrieval parameters
   - Enhance reasoning instructions
   - Add preprocessing/postprocessing

---

## Evaluation Commands

### Run full evaluation
```bash
python evals/run_evals.py
```

### Run specific test subset
```python
from evals.run_evals import EvaluationRunner

runner = EvaluationRunner()
# Custom evaluation logic here
```

### Compare iterations
```bash
python evals/compare_results.py results/eval_results_20260120_*.json
```

---

## Notes

- All evaluation runs saved in `evals/results/`
- Compare results across iterations to track progress
- Focus on systematic improvement, not one-off fixes
- Document all changes and their rationale
- Prioritize high-impact, low-effort improvements first
