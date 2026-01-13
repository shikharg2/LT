#!/usr/bin/env python3
"""
Metrics Collector
Unified interface for collecting, aggregating, and evaluating test metrics
"""

from typing import List, Dict, Union, Optional, Any
from datetime import datetime
import json
import logging
from pathlib import Path

from .aggregation import Aggregation
from .operator import Operator
from .evaluation_scope import EvaluationScope, DataPoint

logger = logging.getLogger(__name__)


class MetricsCollectorError(Exception):
    """Custom exception for metrics collector errors"""
    pass


class MetricsCollector:
    """
    Unified metrics collection and evaluation system

    Combines aggregation, operators, and evaluation scopes to provide
    comprehensive test result analysis and expectation validation.
    """

    def __init__(self):
        """Initialize the metrics collector"""
        self.data_points: Dict[str, List[DataPoint]] = {}
        self.evaluations: List[Dict] = []

    def add_data_point(
        self,
        metric_name: str,
        value: Union[int, float],
        timestamp: Optional[datetime] = None,
        iteration: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Add a data point for a specific metric

        Args:
            metric_name: Name of the metric (e.g., 'download_speed', 'latency')
            value: Measured value
            timestamp: When the measurement was taken
            iteration: Iteration number
            metadata: Additional metadata
        """
        if metric_name not in self.data_points:
            self.data_points[metric_name] = []

        data_point = DataPoint(
            value=value,
            timestamp=timestamp or datetime.now(),
            iteration=iteration,
            metadata=metadata or {}
        )

        self.data_points[metric_name].append(data_point)

        logger.debug(
            f"Added data point for {metric_name}: {value} "
            f"(iteration={iteration}, timestamp={timestamp})"
        )

    def add_multiple_data_points(
        self,
        metric_name: str,
        values: List[Union[int, float, Dict]],
        base_iteration: Optional[int] = None
    ) -> None:
        """
        Add multiple data points for a metric

        Args:
            metric_name: Name of the metric
            values: List of values or data point dictionaries
            base_iteration: Base iteration number (auto-incremented for each value)
        """
        for i, value in enumerate(values):
            if isinstance(value, dict):
                self.add_data_point(
                    metric_name=metric_name,
                    value=value.get('value'),
                    timestamp=value.get('timestamp'),
                    iteration=value.get('iteration', base_iteration + i if base_iteration else None),
                    metadata=value.get('metadata')
                )
            else:
                self.add_data_point(
                    metric_name=metric_name,
                    value=value,
                    iteration=base_iteration + i if base_iteration else None
                )

    def get_metric_data(
        self,
        metric_name: str,
        scope: str = 'aggregate',
        **scope_kwargs
    ) -> List[float]:
        """
        Get metric data with specified evaluation scope

        Args:
            metric_name: Name of the metric
            scope: Evaluation scope (per_iteration, aggregate, windowed)
            **scope_kwargs: Scope-specific arguments

        Returns:
            List of values matching the scope

        Raises:
            MetricsCollectorError: If metric not found
        """
        if metric_name not in self.data_points:
            raise MetricsCollectorError(
                f"Metric '{metric_name}' not found. "
                f"Available metrics: {list(self.data_points.keys())}"
            )

        data = self.data_points[metric_name]

        return EvaluationScope.apply_scope(data, scope, **scope_kwargs)

    def evaluate_expectation(
        self,
        expectation: Dict[str, Any],
        iteration: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a single expectation against collected metrics

        Args:
            expectation: Expectation configuration with keys:
                - metric: Metric name
                - aggregation: Aggregation method (avg, p95, etc.)
                - operator: Comparison operator (gte, lte, etc.)
                - value: Expected value
                - evaluation_scope: Scope (per_iteration, aggregate, windowed)
                - unit: Unit of measurement (optional)
            iteration: Current iteration number (required for per_iteration scope)

        Returns:
            Evaluation result dictionary

        Example expectation:
            {
                "metric": "download_speed",
                "aggregation": "p95",
                "operator": "gte",
                "value": 50,
                "unit": "mbps",
                "evaluation_scope": "aggregate"
            }
        """
        # Extract expectation parameters
        metric = expectation.get('metric')
        aggregation = expectation.get('aggregation', 'mean')
        operator = expectation.get('operator')
        expected_value = expectation.get('value')
        scope = expectation.get('evaluation_scope', 'aggregate')
        unit = expectation.get('unit', '')

        # Validate required fields
        if not metric:
            raise MetricsCollectorError("Expectation missing 'metric' field")
        if not operator:
            raise MetricsCollectorError("Expectation missing 'operator' field")
        if expected_value is None:
            raise MetricsCollectorError("Expectation missing 'value' field")

        # Convert expected_value to numeric if it's a string
        if isinstance(expected_value, str):
            try:
                expected_value = float(expected_value)
            except ValueError:
                # Might be a list for 'between' operator
                try:
                    expected_value = json.loads(expected_value)
                except:
                    pass

        # Prepare scope kwargs
        scope_kwargs = {}
        if scope == 'per_iteration':
            scope_kwargs['iteration'] = iteration
        elif scope == 'windowed':
            scope_kwargs['window_minutes'] = expectation.get('window_minutes', 60)

        try:
            # Get metric data with specified scope
            metric_values = self.get_metric_data(metric, scope, **scope_kwargs)

            # Apply aggregation
            aggregated_value = Aggregation.aggregate(metric_values, aggregation)

            # Evaluate using operator
            operator_kwargs = {}
            if operator == 'between':
                operator_kwargs['inclusive'] = expectation.get('inclusive', 'neither')
            elif operator in ['eq', 'neq']:
                operator_kwargs['tolerance'] = expectation.get('tolerance', 0.0)

            passed = Operator.evaluate(
                aggregated_value,
                operator,
                expected_value,
                **operator_kwargs
            )

            # Build result
            result = {
                'metric': metric,
                'aggregation': aggregation,
                'evaluation_scope': scope,
                'operator': operator,
                'expected_value': expected_value,
                'actual_value': aggregated_value,
                'unit': unit,
                'passed': passed,
                'verdict': 'PASS' if passed else 'FAIL',
                'timestamp': datetime.now().isoformat(),
                'iteration': iteration,
                'data_points_evaluated': len(metric_values),
                'raw_values': metric_values if len(metric_values) <= 10 else f"{len(metric_values)} values"
            }

            # Add to evaluations history
            self.evaluations.append(result)

            logger.info(
                f"Evaluation: {metric} {aggregation} {operator} {expected_value} "
                f"= {aggregated_value:.2f} [{result['verdict']}]"
            )

            return result

        except Exception as e:
            logger.error(f"Error evaluating expectation for {metric}: {e}")
            raise MetricsCollectorError(f"Evaluation failed for {metric}: {e}")

    def evaluate_multiple_expectations(
        self,
        expectations: List[Dict[str, Any]],
        iteration: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate multiple expectations

        Args:
            expectations: List of expectation configurations
            iteration: Current iteration number

        Returns:
            List of evaluation results
        """
        results = []

        for expectation in expectations:
            try:
                result = self.evaluate_expectation(expectation, iteration)
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Failed to evaluate expectation {expectation.get('metric')}: {e}"
                )
                # Add failed evaluation result
                results.append({
                    'metric': expectation.get('metric', 'unknown'),
                    'passed': False,
                    'verdict': 'ERROR',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })

        return results

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of collected metrics and evaluations

        Returns:
            Summary dictionary
        """
        summary = {
            'total_metrics': len(self.data_points),
            'metrics': {},
            'total_evaluations': len(self.evaluations),
            'passed_evaluations': sum(1 for e in self.evaluations if e.get('passed')),
            'failed_evaluations': sum(1 for e in self.evaluations if not e.get('passed')),
            'success_rate': 0.0
        }

        # Calculate success rate
        if summary['total_evaluations'] > 0:
            summary['success_rate'] = (
                summary['passed_evaluations'] / summary['total_evaluations']
            ) * 100

        # Add per-metric statistics
        for metric_name, data_points in self.data_points.items():
            values = [dp.value for dp in data_points]

            if values:
                summary['metrics'][metric_name] = {
                    'count': len(values),
                    'min': Aggregation.min(values),
                    'max': Aggregation.max(values),
                    'mean': Aggregation.mean(values),
                    'median': Aggregation.median(values),
                    'p95': Aggregation.p95(values) if len(values) >= 2 else values[0],
                    'std_dev': Aggregation.std_dev(values) if len(values) >= 2 else 0.0
                }

        return summary

    def export_to_dict(self) -> Dict[str, Any]:
        """
        Export all data to dictionary

        Returns:
            Dictionary with all metrics and evaluations
        """
        return {
            'metrics': {
                name: [dp.to_dict() for dp in points]
                for name, points in self.data_points.items()
            },
            'evaluations': self.evaluations,
            'summary': self.get_summary()
        }

    def export_to_json(self, file_path: str) -> None:
        """
        Export metrics and evaluations to JSON file

        Args:
            file_path: Path to output JSON file
        """
        data = self.export_to_dict()

        output_path = Path(file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported metrics to {file_path}")

    def clear(self) -> None:
        """Clear all collected data and evaluations"""
        self.data_points.clear()
        self.evaluations.clear()
        logger.info("Cleared all metrics and evaluations")

    def get_metric_names(self) -> List[str]:
        """Get list of all metric names"""
        return list(self.data_points.keys())

    def get_evaluation_history(
        self,
        metric: Optional[str] = None,
        passed_only: bool = False
    ) -> List[Dict]:
        """
        Get evaluation history

        Args:
            metric: Filter by specific metric (optional)
            passed_only: Only return passed evaluations

        Returns:
            List of evaluation results
        """
        results = self.evaluations

        if metric:
            results = [e for e in results if e.get('metric') == metric]

        if passed_only:
            results = [e for e in results if e.get('passed')]

        return results


if __name__ == '__main__':
    # Example usage
    print("Metrics Collector Module - Example Usage")
    print("=" * 70)

    # Create collector
    collector = MetricsCollector()

    # Add sample data for download speed
    print("\nAdding download speed measurements...")
    for i in range(1, 11):
        speed = 45 + (i * 5)  # 50, 55, 60, ..., 95, 100
        collector.add_data_point(
            metric_name='download_speed',
            value=speed,
            iteration=i
        )
        print(f"  Iteration {i}: {speed} Mbps")

    # Add sample data for latency
    print("\nAdding latency measurements...")
    latencies = [25, 30, 28, 32, 27, 29, 35, 26, 31, 28]
    collector.add_multiple_data_points(
        metric_name='latency',
        values=latencies,
        base_iteration=1
    )

    # Define expectations
    expectations = [
        {
            "metric": "download_speed",
            "aggregation": "p95",
            "operator": "gte",
            "value": 80,
            "unit": "mbps",
            "evaluation_scope": "aggregate"
        },
        {
            "metric": "download_speed",
            "aggregation": "mean",
            "operator": "gte",
            "value": 70,
            "unit": "mbps",
            "evaluation_scope": "aggregate"
        },
        {
            "metric": "latency",
            "aggregation": "p95",
            "operator": "lte",
            "value": 35,
            "unit": "ms",
            "evaluation_scope": "aggregate"
        }
    ]

    # Evaluate expectations
    print("\n" + "-" * 70)
    print("Evaluating Expectations:")
    print("-" * 70)

    results = collector.evaluate_multiple_expectations(expectations)

    for result in results:
        print(f"\nMetric: {result['metric']}")
        print(f"  Aggregation: {result['aggregation']}")
        print(f"  Expected: {result['operator']} {result['expected_value']} {result['unit']}")
        print(f"  Actual: {result['actual_value']:.2f} {result['unit']}")
        print(f"  Verdict: {result['verdict']}")

    # Print summary
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)

    summary = collector.get_summary()
    print(f"Total Metrics: {summary['total_metrics']}")
    print(f"Total Evaluations: {summary['total_evaluations']}")
    print(f"Passed: {summary['passed_evaluations']}")
    print(f"Failed: {summary['failed_evaluations']}")
    print(f"Success Rate: {summary['success_rate']:.2f}%")

    print("\nMetric Statistics:")
    for metric_name, stats in summary['metrics'].items():
        print(f"\n{metric_name}:")
        print(f"  Count: {stats['count']}")
        print(f"  Min: {stats['min']:.2f}")
        print(f"  Max: {stats['max']:.2f}")
        print(f"  Mean: {stats['mean']:.2f}")
        print(f"  Median: {stats['median']:.2f}")
        print(f"  P95: {stats['p95']:.2f}")
        print(f"  Std Dev: {stats['std_dev']:.2f}")
