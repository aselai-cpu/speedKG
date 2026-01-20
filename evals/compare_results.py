"""
Compare Evaluation Results

Compares evaluation results across multiple runs to track improvements.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


def load_results(filepath: Path) -> Dict[str, Any]:
    """Load evaluation results from JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def compare_metrics(results_list: List[Dict[str, Any]]):
    """
    Compare metrics across multiple evaluation runs.

    Args:
        results_list: List of evaluation result dictionaries
    """
    if not results_list:
        print("No results to compare")
        return

    print("\n" + "=" * 100)
    print("EVALUATION RESULTS COMPARISON")
    print("=" * 100)

    # Extract timestamps and summaries
    runs = []
    for i, results in enumerate(results_list, 1):
        timestamp = results.get('timestamp', f'Run {i}')
        summary = results.get('summary', {})

        runs.append({
            'id': i,
            'timestamp': timestamp,
            'overall_success': summary.get('overall_success_rate', 0),
            'cypher_accuracy': summary.get('cypher_accuracy', 0),
            'coverage': summary.get('coverage', 0),
            'latency_p50': summary.get('latency_p50', 0),
            'latency_p95': summary.get('latency_p95', 0),
            'latency_p99': summary.get('latency_p99', 0),
        })

    # Print comparison table
    print(f"\n{'Run':<6} {'Timestamp':<20} {'Success':<10} {'Cypher':<10} {'Coverage':<10} {'P50':<8} {'P95':<8} {'P99':<8}")
    print("-" * 100)

    for run in runs:
        print(f"{run['id']:<6} "
              f"{run['timestamp'][:19]:<20} "
              f"{run['overall_success']:>8.1%}  "
              f"{run['cypher_accuracy']:>8.1%}  "
              f"{run['coverage']:>8.1%}  "
              f"{run['latency_p50']:>6.0f}ms "
              f"{run['latency_p95']:>6.0f}ms "
              f"{run['latency_p99']:>6.0f}ms")

    # Print improvements
    if len(runs) >= 2:
        print("\n" + "=" * 100)
        print("IMPROVEMENTS (Latest vs Baseline)")
        print("=" * 100)

        baseline = runs[0]
        latest = runs[-1]

        metrics = [
            ('Overall Success Rate', 'overall_success', '%'),
            ('Cypher Accuracy', 'cypher_accuracy', '%'),
            ('Coverage', 'coverage', '%'),
            ('Latency P50', 'latency_p50', 'ms'),
            ('Latency P95', 'latency_p95', 'ms'),
            ('Latency P99', 'latency_p99', 'ms'),
        ]

        for name, key, unit in metrics:
            baseline_val = baseline[key]
            latest_val = latest[key]

            if unit == '%':
                diff = (latest_val - baseline_val) * 100
                print(f"{name:<25}: {baseline_val:>8.1%} → {latest_val:>8.1%}  "
                      f"({'+'if diff >= 0 else ''}{diff:+.1f} pp)")
            else:
                diff = latest_val - baseline_val
                print(f"{name:<25}: {baseline_val:>6.0f}{unit} → {latest_val:>6.0f}{unit}  "
                      f"({'+'if diff >= 0 else ''}{diff:+.0f}{unit})")

        # Target achievement
        print("\n" + "=" * 100)
        print("TARGET ACHIEVEMENT")
        print("=" * 100)

        targets = {
            'Cypher Accuracy': (latest['cypher_accuracy'], 0.90),
            'Coverage': (latest['coverage'], 0.85),
            'Latency P95': (latest['latency_p95'], 3000, 'inverse'),
        }

        all_met = True
        for name, values in targets.items():
            if len(values) == 2:
                actual, target = values
                met = actual >= target
                status = "✓" if met else "✗"
                print(f"{status} {name:<20}: {actual:>8.1%} (target: {target:.1%})")
            else:
                actual, target, _ = values
                met = actual < target
                status = "✓" if met else "✗"
                print(f"{status} {name:<20}: {actual:>6.0f}ms (target: <{target}ms)")

            all_met = all_met and met

        if all_met:
            print("\n✅ All targets achieved!")
        else:
            print("\n⚠️  Some targets not yet achieved")

    print("\n" + "=" * 100)


def analyze_failure_patterns(results_list: List[Dict[str, Any]]):
    """Analyze common failure patterns across runs."""
    print("\n" + "=" * 100)
    print("FAILURE PATTERN ANALYSIS")
    print("=" * 100)

    for i, results in enumerate(results_list, 1):
        print(f"\n### Run {i}: {results.get('timestamp', 'N/A')[:19]}")

        test_eval = results.get('test_query_evaluation', {})
        query_results = test_eval.get('results', [])

        # Count failures by type
        cypher_invalid = sum(1 for r in query_results if not r.get('cypher_valid'))
        no_results = sum(1 for r in query_results if r.get('result_count', 0) == 0)
        errors = sum(1 for r in query_results if 'error' in r)

        print(f"  Cypher Invalid: {cypher_invalid}")
        print(f"  No Results: {no_results}")
        print(f"  Errors: {errors}")

        # Show sample failures
        failures = [r for r in query_results if not r.get('success', True)]
        if failures:
            print(f"\n  Sample Failures:")
            for failure in failures[:3]:
                query_id = failure.get('query_id', 'N/A')
                query = failure.get('query', 'N/A')[:60]
                print(f"    {query_id}: {query}...")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python compare_results.py <result_file1> [result_file2] ...")
        print("\nExample:")
        print("  python compare_results.py evals/results/*.json")
        sys.exit(1)

    # Load all result files
    results_list = []
    for filepath in sys.argv[1:]:
        path = Path(filepath)
        if not path.exists():
            print(f"Warning: File not found: {filepath}")
            continue

        try:
            results = load_results(path)
            results_list.append(results)
            print(f"Loaded: {filepath}")
        except Exception as e:
            print(f"Error loading {filepath}: {e}")

    if not results_list:
        print("No valid result files loaded")
        sys.exit(1)

    # Sort by timestamp
    results_list.sort(key=lambda r: r.get('timestamp', ''))

    # Compare metrics
    compare_metrics(results_list)

    # Analyze failures
    analyze_failure_patterns(results_list)


if __name__ == "__main__":
    main()
