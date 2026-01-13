#!/usr/bin/env python3
"""
Evaluation Scope Utilities
Provides different scopes for evaluating test expectations
"""

from typing import List, Dict, Union, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class EvaluationScopeError(Exception):
    """Custom exception for evaluation scope errors"""
    pass


class DataPoint:
    """
    Represents a single test data point with metadata
    """

    def __init__(
        self,
        value: Union[int, float],
        timestamp: Optional[datetime] = None,
        iteration: Optional[int] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Initialize a data point

        Args:
            value: The measured value
            timestamp: When the measurement was taken
            iteration: Iteration number
            metadata: Additional metadata
        """
        self.value = value
        self.timestamp = timestamp or datetime.now()
        self.iteration = iteration
        self.metadata = metadata or {}

    def __repr__(self):
        return f"DataPoint(value={self.value}, timestamp={self.timestamp}, iteration={self.iteration})"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'value': self.value,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'iteration': self.iteration,
            'metadata': self.metadata
        }


class EvaluationScope:
    """
    Evaluation scope methods for filtering and scoping test data

    Supported scopes:
    - per_iteration: Evaluates the single current test run
    - aggregate: Evaluates all data points from start until now
    - windowed: Evaluates data within a rolling time window
    - cumulative_success_rate: Calculates percentage of passed tests
    """

    @staticmethod
    def validate_data_points(data: List[Union[DataPoint, Dict, float]]) -> List[DataPoint]:
        """
        Validate and normalize data points

        Args:
            data: List of data points (DataPoint objects, dicts, or raw values)

        Returns:
            List of DataPoint objects

        Raises:
            EvaluationScopeError: If data is invalid
        """
        if not isinstance(data, list):
            raise EvaluationScopeError(
                f"Data must be a list, got {type(data).__name__}"
            )

        normalized = []

        for i, item in enumerate(data):
            if isinstance(item, DataPoint):
                normalized.append(item)
            elif isinstance(item, dict):
                # Convert dict to DataPoint
                try:
                    normalized.append(DataPoint(
                        value=item.get('value'),
                        timestamp=item.get('timestamp'),
                        iteration=item.get('iteration'),
                        metadata=item.get('metadata', {})
                    ))
                except Exception as e:
                    raise EvaluationScopeError(
                        f"Invalid data point dict at index {i}: {e}"
                    )
            elif isinstance(item, (int, float)):
                # Convert raw value to DataPoint
                normalized.append(DataPoint(value=item, iteration=i))
            else:
                raise EvaluationScopeError(
                    f"Invalid data point type at index {i}: {type(item).__name__}"
                )

        return normalized

    @staticmethod
    def per_iteration(
        data: List[Union[DataPoint, Dict, float]],
        iteration: Optional[int] = None
    ) -> List[float]:
        """
        Per-iteration scope: Evaluates the single current test run

        Use Case: "Did the website load under 5s right now?"

        Args:
            data: List of data points
            iteration: Specific iteration to extract (default: latest)

        Returns:
            List with single value from the specified iteration

        Example:
            >>> data = [
            ...     DataPoint(value=100, iteration=1),
            ...     DataPoint(value=150, iteration=2),
            ...     DataPoint(value=120, iteration=3)
            ... ]
            >>> EvaluationScope.per_iteration(data, iteration=2)
            [150]
        """
        data_points = EvaluationScope.validate_data_points(data)

        if not data_points:
            raise EvaluationScopeError("No data points available")

        if iteration is None:
            # Use the latest iteration
            if data_points[-1].iteration is not None:
                iteration = data_points[-1].iteration
            else:
                # If no iteration info, return last value
                return [data_points[-1].value]

        # Find all data points for the specified iteration
        iteration_data = [
            dp.value for dp in data_points
            if dp.iteration == iteration
        ]

        if not iteration_data:
            raise EvaluationScopeError(
                f"No data found for iteration {iteration}"
            )

        logger.debug(
            f"Per-iteration scope: iteration={iteration}, "
            f"data_points={len(iteration_data)}"
        )

        return iteration_data

    @staticmethod
    def aggregate(
        data: List[Union[DataPoint, Dict, float]],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[float]:
        """
        Aggregate scope: Evaluates all data points from start until now

        Use Case: "Is the P95 load time under 5s for all tests run this week?"

        Args:
            data: List of data points
            start_time: Start of time range (optional)
            end_time: End of time range (optional, defaults to now)

        Returns:
            List of all values in the specified range

        Example:
            >>> data = [
            ...     DataPoint(value=100, iteration=1),
            ...     DataPoint(value=150, iteration=2),
            ...     DataPoint(value=120, iteration=3)
            ... ]
            >>> EvaluationScope.aggregate(data)
            [100, 150, 120]
        """
        data_points = EvaluationScope.validate_data_points(data)

        if not data_points:
            raise EvaluationScopeError("No data points available")

        # Filter by time range if specified
        filtered = data_points

        if start_time is not None:
            filtered = [dp for dp in filtered if dp.timestamp >= start_time]

        if end_time is not None:
            filtered = [dp for dp in filtered if dp.timestamp <= end_time]

        if not filtered:
            raise EvaluationScopeError(
                f"No data points found in specified time range"
            )

        values = [dp.value for dp in filtered]

        logger.debug(
            f"Aggregate scope: total_points={len(data_points)}, "
            f"filtered_points={len(values)}"
        )

        return values

    @staticmethod
    def windowed(
        data: List[Union[DataPoint, Dict, float]],
        window_minutes: int = 60,
        reference_time: Optional[datetime] = None
    ) -> List[float]:
        """
        Windowed scope: Evaluates data within a rolling time window

        Use Case: "Is the network stable recently?" (Ignores failures from 3 days ago)

        Args:
            data: List of data points
            window_minutes: Size of the time window in minutes
            reference_time: Reference time (default: now)

        Returns:
            List of values within the time window

        Example:
            >>> from datetime import datetime, timedelta
            >>> now = datetime.now()
            >>> data = [
            ...     DataPoint(value=100, timestamp=now - timedelta(hours=2)),
            ...     DataPoint(value=150, timestamp=now - timedelta(minutes=30)),
            ...     DataPoint(value=120, timestamp=now - timedelta(minutes=10))
            ... ]
            >>> EvaluationScope.windowed(data, window_minutes=60)
            [150, 120]
        """
        data_points = EvaluationScope.validate_data_points(data)

        if not data_points:
            raise EvaluationScopeError("No data points available")

        if window_minutes <= 0:
            raise EvaluationScopeError(
                f"Window size must be positive, got {window_minutes}"
            )

        # Use provided reference time or current time
        ref_time = reference_time or datetime.now()

        # Calculate window start time
        window_start = ref_time - timedelta(minutes=window_minutes)

        # Filter data points within the window
        windowed_data = [
            dp.value for dp in data_points
            if dp.timestamp >= window_start and dp.timestamp <= ref_time
        ]

        if not windowed_data:
            raise EvaluationScopeError(
                f"No data points found in {window_minutes}-minute window"
            )

        logger.debug(
            f"Windowed scope: window={window_minutes}min, "
            f"data_points={len(windowed_data)}, "
            f"window_start={window_start}"
        )

        return windowed_data

    @staticmethod
    def cumulative_success_rate(
        results: List[Dict[str, Any]],
        pass_key: str = 'passed'
    ) -> float:
        """
        Cumulative success rate: Calculates percentage of passed tests

        Use Case: "Did 99% of the individual tests pass?"

        Args:
            results: List of test results (each must have a pass/fail indicator)
            pass_key: Key in result dict indicating pass/fail (default: 'passed')

        Returns:
            Success rate as a percentage (0-100)

        Example:
            >>> results = [
            ...     {'passed': True, 'value': 100},
            ...     {'passed': True, 'value': 150},
            ...     {'passed': False, 'value': 50},
            ...     {'passed': True, 'value': 120}
            ... ]
            >>> EvaluationScope.cumulative_success_rate(results)
            75.0
        """
        if not results:
            raise EvaluationScopeError("No results available")

        if not isinstance(results, list):
            raise EvaluationScopeError(
                f"Results must be a list, got {type(results).__name__}"
            )

        # Count passed tests
        total = len(results)
        passed = 0

        for i, result in enumerate(results):
            if not isinstance(result, dict):
                raise EvaluationScopeError(
                    f"Result at index {i} must be a dict, got {type(result).__name__}"
                )

            if pass_key not in result:
                raise EvaluationScopeError(
                    f"Result at index {i} missing '{pass_key}' key"
                )

            if result[pass_key]:
                passed += 1

        success_rate = (passed / total) * 100

        logger.debug(
            f"Cumulative success rate: passed={passed}/{total} = {success_rate:.2f}%"
        )

        return success_rate

    @staticmethod
    def apply_scope(
        data: List[Union[DataPoint, Dict, float]],
        scope: str,
        **kwargs
    ) -> List[float]:
        """
        Apply evaluation scope by name

        Args:
            data: List of data points
            scope: Scope name (per_iteration, aggregate, windowed)
            **kwargs: Additional scope-specific arguments

        Returns:
            Filtered data values

        Raises:
            EvaluationScopeError: If scope is unknown

        Example:
            >>> data = [DataPoint(value=100), DataPoint(value=150)]
            >>> EvaluationScope.apply_scope(data, 'aggregate')
            [100, 150]
        """
        scope = scope.lower().strip()

        scope_map = {
            'per_iteration': EvaluationScope.per_iteration,
            'aggregate': EvaluationScope.aggregate,
            'windowed': EvaluationScope.windowed,
        }

        if scope not in scope_map:
            raise EvaluationScopeError(
                f"Unknown scope: '{scope}'. "
                f"Available scopes: {', '.join(scope_map.keys())}"
            )

        try:
            result = scope_map[scope](data, **kwargs)
            logger.debug(
                f"Applied scope '{scope}': {len(data)} points -> {len(result)} values"
            )
            return result
        except EvaluationScopeError:
            raise
        except Exception as e:
            logger.error(f"Error applying scope {scope}: {e}")
            raise EvaluationScopeError(f"Error applying scope {scope}: {e}")

    @staticmethod
    def get_available_scopes() -> List[str]:
        """
        Get list of available evaluation scopes

        Returns:
            List of scope names
        """
        return ['per_iteration', 'aggregate', 'windowed', 'cumulative_success_rate']

    @staticmethod
    def get_scope_info(scope: str) -> Dict:
        """
        Get information about an evaluation scope

        Args:
            scope: Scope name

        Returns:
            Dictionary with scope information
        """
        info_map = {
            'per_iteration': {
                'name': 'Per Iteration',
                'description': 'Evaluates the result of the single current test run',
                'use_case': '"Did the website load under 5s right now?"',
                'parameters': ['iteration (optional)']
            },
            'aggregate': {
                'name': 'Aggregate',
                'description': 'Evaluates all data points collected from the start until now',
                'use_case': '"Is the P95 load time under 5s for all tests run this week?"',
                'parameters': ['start_time (optional)', 'end_time (optional)']
            },
            'windowed': {
                'name': 'Windowed',
                'description': 'Evaluates data points within a rolling time window',
                'use_case': '"Is the network stable recently?" (Ignores failures from 3 days ago)',
                'parameters': ['window_minutes', 'reference_time (optional)']
            },
            'cumulative_success_rate': {
                'name': 'Cumulative Success Rate',
                'description': 'Calculates the percentage of passed per_iteration tests',
                'use_case': '"Did 99% of the individual tests pass?"',
                'parameters': ['pass_key (optional)']
            }
        }

        scope = scope.lower().strip()
        return info_map.get(scope, {
            'name': scope,
            'description': 'Unknown scope'
        })


# Convenience functions
def per_iteration(data: List[Union[DataPoint, Dict, float]], iteration: Optional[int] = None) -> List[float]:
    """Convenience function for per_iteration scope"""
    return EvaluationScope.per_iteration(data, iteration)


def aggregate(data: List[Union[DataPoint, Dict, float]], **kwargs) -> List[float]:
    """Convenience function for aggregate scope"""
    return EvaluationScope.aggregate(data, **kwargs)


def windowed(data: List[Union[DataPoint, Dict, float]], window_minutes: int = 60, **kwargs) -> List[float]:
    """Convenience function for windowed scope"""
    return EvaluationScope.windowed(data, window_minutes, **kwargs)


def success_rate(results: List[Dict[str, Any]], pass_key: str = 'passed') -> float:
    """Convenience function for cumulative_success_rate"""
    return EvaluationScope.cumulative_success_rate(results, pass_key)


if __name__ == '__main__':
    # Example usage and testing
    from datetime import datetime, timedelta

    print("Evaluation Scope Module - Example Usage")
    print("=" * 70)

    # Create sample data
    now = datetime.now()
    sample_data = [
        DataPoint(value=100, timestamp=now - timedelta(hours=3), iteration=1),
        DataPoint(value=150, timestamp=now - timedelta(hours=2), iteration=2),
        DataPoint(value=120, timestamp=now - timedelta(hours=1), iteration=3),
        DataPoint(value=180, timestamp=now - timedelta(minutes=30), iteration=4),
        DataPoint(value=110, timestamp=now - timedelta(minutes=10), iteration=5),
    ]

    print(f"\nSample Data ({len(sample_data)} points):")
    for dp in sample_data:
        print(f"  {dp}")

    # Test per_iteration
    print("\n" + "-" * 70)
    print("Per Iteration Scope (iteration=3):")
    result = EvaluationScope.per_iteration(sample_data, iteration=3)
    print(f"  Result: {result}")

    # Test aggregate
    print("\n" + "-" * 70)
    print("Aggregate Scope (all data):")
    result = EvaluationScope.aggregate(sample_data)
    print(f"  Result: {result}")

    # Test windowed
    print("\n" + "-" * 70)
    print("Windowed Scope (last 60 minutes):")
    result = EvaluationScope.windowed(sample_data, window_minutes=60)
    print(f"  Result: {result}")

    # Test cumulative success rate
    print("\n" + "-" * 70)
    print("Cumulative Success Rate:")
    test_results = [
        {'passed': True, 'value': 100},
        {'passed': True, 'value': 150},
        {'passed': False, 'value': 50},
        {'passed': True, 'value': 120},
        {'passed': True, 'value': 180},
    ]
    success = EvaluationScope.cumulative_success_rate(test_results)
    print(f"  Success Rate: {success:.2f}%")

    print("\n" + "=" * 70)
    print("\nAvailable Scopes:")
    for scope in EvaluationScope.get_available_scopes():
        info = EvaluationScope.get_scope_info(scope)
        print(f"\n{info['name']}")
        print(f"  Description: {info['description']}")
        print(f"  Use Case: {info['use_case']}")
