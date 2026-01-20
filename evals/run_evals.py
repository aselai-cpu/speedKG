"""
Evaluation Runner

Runs evaluation tests against the intelligence agent and measures metrics:
- Cypher Generation Accuracy
- Answer Accuracy
- Latency (P50, P95, P99)
- Coverage
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime
import statistics

from src.intelligence.agent import IntelligenceAgent
from src.intelligence.state import QueryIntent

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Runs evaluations and tracks metrics."""

    def __init__(self, output_dir: Path = None):
        """
        Initialize evaluation runner.

        Args:
            output_dir: Directory to save results (default: evals/results)
        """
        self.output_dir = output_dir or Path("evals/results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.agent = None

    def run_full_evaluation(self) -> Dict[str, Any]:
        """
        Run complete evaluation suite.

        Returns:
            Evaluation results dictionary
        """
        print("\n" + "=" * 80)
        print("SPEED-CAMEO INTELLIGENCE AGENT EVALUATION")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().isoformat()}\n")

        try:
            # Initialize agent
            print("Initializing agent...")
            self.agent = IntelligenceAgent()
            print("✓ Agent initialized\n")

            # Load test datasets
            test_queries = self._load_json("evals/test_queries.json")
            cypher_tests = self._load_json("evals/cypher_generation.json")

            # Run evaluations
            results = {
                "timestamp": datetime.now().isoformat(),
                "test_query_evaluation": self._evaluate_test_queries(test_queries),
                "cypher_generation_evaluation": self._evaluate_cypher_generation(cypher_tests),
                "summary": {}
            }

            # Compute summary metrics
            results["summary"] = self._compute_summary(results)

            # Save results
            self._save_results(results)

            # Print summary
            self._print_summary(results)

            return results

        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            print(f"\n❌ Evaluation failed: {e}")
            return {"error": str(e)}

        finally:
            if self.agent:
                self.agent.close()
                print("\n✓ Agent closed")

    def _evaluate_test_queries(self, test_data: Dict) -> Dict[str, Any]:
        """
        Evaluate agent on test queries.

        Args:
            test_data: Test queries from test_queries.json

        Returns:
            Evaluation results
        """
        print(f"Evaluating {len(test_data['queries'])} test queries...")
        print("-" * 80)

        results = []
        latencies = []

        for i, test_case in enumerate(test_data['queries'], 1):
            query_id = test_case['id']
            query = test_case['query']

            print(f"\n[{i}/{len(test_data['queries'])}] {query_id}: {query[:60]}...")

            try:
                # Run query through agent
                result = self.agent.query(query)

                # Record latency
                latency_ms = result.get('total_duration_ms', 0)
                latencies.append(latency_ms)

                # Evaluate result
                evaluation = self._evaluate_query_result(test_case, result)

                results.append({
                    "query_id": query_id,
                    "query": query,
                    "intent": result.get('intent'),
                    "cypher_valid": result.get('cypher_valid', False),
                    "result_count": result.get('result_count', 0),
                    "latency_ms": latency_ms,
                    "evaluation": evaluation,
                    "success": evaluation['passed']
                })

                status = "✓" if evaluation['passed'] else "✗"
                print(f"  {status} Cypher valid: {result.get('cypher_valid')}, "
                      f"Results: {result.get('result_count', 0)}, "
                      f"Latency: {latency_ms:.0f}ms")

            except Exception as e:
                logger.error(f"Query {query_id} failed: {e}")
                results.append({
                    "query_id": query_id,
                    "query": query,
                    "error": str(e),
                    "success": False
                })
                print(f"  ✗ Error: {e}")

        # Compute metrics
        successful = sum(1 for r in results if r.get('success'))
        cypher_valid_count = sum(1 for r in results if r.get('cypher_valid'))

        return {
            "total_queries": len(test_data['queries']),
            "successful": successful,
            "success_rate": successful / len(test_data['queries']) if test_data['queries'] else 0,
            "cypher_valid_count": cypher_valid_count,
            "cypher_accuracy": cypher_valid_count / len(test_data['queries']) if test_data['queries'] else 0,
            "latencies": {
                "p50": statistics.median(latencies) if latencies else 0,
                "p95": self._percentile(latencies, 0.95) if latencies else 0,
                "p99": self._percentile(latencies, 0.99) if latencies else 0,
                "mean": statistics.mean(latencies) if latencies else 0
            },
            "results": results
        }

    def _evaluate_cypher_generation(self, cypher_data: Dict) -> Dict[str, Any]:
        """
        Evaluate Cypher generation accuracy.

        Args:
            cypher_data: Cypher test cases from cypher_generation.json

        Returns:
            Evaluation results
        """
        print(f"\n\nEvaluating Cypher generation on {len(cypher_data['test_cases'])} cases...")
        print("-" * 80)

        results = []

        for i, test_case in enumerate(cypher_data['test_cases'], 1):
            cypher_id = test_case['id']
            query = test_case['query']

            print(f"\n[{i}/{len(cypher_data['test_cases'])}] {cypher_id}: {query[:60]}...")

            try:
                # Run query to get generated Cypher
                result = self.agent.query(query)

                generated_cypher = result.get('cypher_query', '')
                cypher_valid = result.get('cypher_valid', False)

                # Validate against reference
                validation = self._validate_cypher(generated_cypher, test_case['validation_criteria'])

                results.append({
                    "cypher_id": cypher_id,
                    "query": query,
                    "generated_cypher": generated_cypher,
                    "reference_cypher": test_case['reference_cypher'],
                    "cypher_valid": cypher_valid,
                    "validation": validation,
                    "passed": cypher_valid and validation['passed']
                })

                status = "✓" if cypher_valid and validation['passed'] else "✗"
                print(f"  {status} Valid: {cypher_valid}, "
                      f"Criteria passed: {validation['passed']}, "
                      f"Score: {validation['score']:.2f}")

            except Exception as e:
                logger.error(f"Cypher test {cypher_id} failed: {e}")
                results.append({
                    "cypher_id": cypher_id,
                    "query": query,
                    "error": str(e),
                    "passed": False
                })
                print(f"  ✗ Error: {e}")

        # Compute metrics
        passed = sum(1 for r in results if r.get('passed'))

        return {
            "total_cases": len(cypher_data['test_cases']),
            "passed": passed,
            "accuracy": passed / len(cypher_data['test_cases']) if cypher_data['test_cases'] else 0,
            "results": results
        }

    def _evaluate_query_result(self, test_case: Dict, result: Dict) -> Dict[str, Any]:
        """
        Evaluate a query result against expected criteria.

        Args:
            test_case: Test case with expected criteria
            result: Agent result

        Returns:
            Evaluation dict with passed/failed and details
        """
        criteria = test_case.get('expected_criteria', {})
        checks = []

        # Check: Cypher contains expected keywords
        if 'cypher_contains' in criteria:
            cypher = result.get('cypher_query', '').upper()
            for keyword in criteria['cypher_contains']:
                contains = keyword.upper() in cypher
                checks.append({
                    "check": f"Cypher contains '{keyword}'",
                    "passed": contains
                })

        # Check: Minimum results
        if 'min_results' in criteria:
            result_count = result.get('result_count', 0)
            passed = result_count >= criteria['min_results']
            checks.append({
                "check": f"At least {criteria['min_results']} results",
                "passed": passed,
                "actual": result_count
            })

        # Check: Valid Cypher
        checks.append({
            "check": "Valid Cypher generated",
            "passed": result.get('cypher_valid', False)
        })

        # Check: No errors
        checks.append({
            "check": "No errors",
            "passed": result.get('error') is None
        })

        passed_count = sum(1 for c in checks if c.get('passed', False))
        total_checks = len(checks)

        return {
            "checks": checks,
            "passed": passed_count == total_checks,
            "score": passed_count / total_checks if total_checks > 0 else 0
        }

    def _validate_cypher(self, generated: str, criteria: Dict) -> Dict[str, Any]:
        """
        Validate generated Cypher against criteria.

        Args:
            generated: Generated Cypher query
            criteria: Validation criteria

        Returns:
            Validation result
        """
        generated_upper = generated.upper()
        checks = []

        # Must have keywords
        if 'must_have' in criteria:
            for keyword in criteria['must_have']:
                contains = keyword.upper() in generated_upper
                checks.append({
                    "check": f"Contains '{keyword}'",
                    "passed": contains
                })

        # Should not have keywords
        if 'should_not_have' in criteria:
            for keyword in criteria['should_not_have']:
                not_contains = keyword.upper() not in generated_upper
                checks.append({
                    "check": f"Does not contain '{keyword}'",
                    "passed": not_contains
                })

        # Additional criteria (simplified checks)
        if 'must_filter' in criteria:
            # Just check if WHERE clause exists
            has_where = 'WHERE' in generated_upper
            checks.append({
                "check": "Has filtering (WHERE clause)",
                "passed": has_where
            })

        if 'must_aggregate' in criteria:
            # Check for aggregation functions
            has_agg = any(agg in generated_upper for agg in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN'])
            checks.append({
                "check": "Has aggregation",
                "passed": has_agg
            })

        passed_count = sum(1 for c in checks if c.get('passed', False))
        total_checks = len(checks)

        return {
            "checks": checks,
            "passed": passed_count == total_checks,
            "score": passed_count / total_checks if total_checks > 0 else 0
        }

    def _compute_summary(self, results: Dict) -> Dict[str, Any]:
        """Compute summary metrics."""
        query_eval = results.get('test_query_evaluation', {})
        cypher_eval = results.get('cypher_generation_evaluation', {})

        return {
            "overall_success_rate": query_eval.get('success_rate', 0),
            "cypher_accuracy": cypher_eval.get('accuracy', 0),
            "coverage": query_eval.get('success_rate', 0),
            "latency_p50": query_eval.get('latencies', {}).get('p50', 0),
            "latency_p95": query_eval.get('latencies', {}).get('p95', 0),
            "latency_p99": query_eval.get('latencies', {}).get('p99', 0),
            "target_metrics": {
                "cypher_accuracy_target": 0.90,
                "answer_accuracy_target": 0.70,
                "latency_p95_target_ms": 3000,
                "coverage_target": 0.85
            },
            "meets_targets": {
                "cypher_accuracy": cypher_eval.get('accuracy', 0) >= 0.90,
                "coverage": query_eval.get('success_rate', 0) >= 0.85,
                "latency": query_eval.get('latencies', {}).get('p95', 0) < 3000
            }
        }

    def _print_summary(self, results: Dict):
        """Print evaluation summary."""
        summary = results.get('summary', {})

        print("\n\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)

        print(f"\nOverall Success Rate: {summary.get('overall_success_rate', 0):.1%}")
        print(f"Cypher Accuracy:      {summary.get('cypher_accuracy', 0):.1%}")
        print(f"Coverage:             {summary.get('coverage', 0):.1%}")

        print(f"\nLatency:")
        print(f"  P50: {summary.get('latency_p50', 0):.0f}ms")
        print(f"  P95: {summary.get('latency_p95', 0):.0f}ms")
        print(f"  P99: {summary.get('latency_p99', 0):.0f}ms")

        print(f"\nTarget Achievement:")
        meets_targets = summary.get('meets_targets', {})
        for metric, passed in meets_targets.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {metric}")

        print("\n" + "=" * 80)

    def _save_results(self, results: Dict):
        """Save results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"eval_results_{timestamp}.json"

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n✓ Results saved to: {filepath}")

    def _load_json(self, filepath: str) -> Dict:
        """Load JSON file."""
        with open(filepath, 'r') as f:
            return json.load(f)

    def _percentile(self, data: List[float], p: float) -> float:
        """Calculate percentile."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * p)
        return sorted_data[min(index, len(sorted_data) - 1)]


def main():
    """Run evaluations."""
    runner = EvaluationRunner()
    results = runner.run_full_evaluation()

    # Exit with status code based on results
    summary = results.get('summary', {})
    meets_targets = summary.get('meets_targets', {})

    if all(meets_targets.values()):
        print("\n✅ All target metrics achieved!")
        exit(0)
    else:
        print("\n⚠️  Some target metrics not achieved")
        exit(1)


if __name__ == "__main__":
    main()
