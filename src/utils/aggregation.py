#!/usr/bin/env python3
"""
Aggregation Utilities
Provides various statistical aggregation methods for test result analysis
"""

import math
from typing import List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class AggregationError(Exception):
    """Custom exception for aggregation errors"""
    pass


class Aggregation:
    """
    Statistical aggregation methods for analyzing test metrics

    Supported aggregations:
    - avg/mean: Arithmetic mean
    - median/p50: Middle value (50th percentile)
    - p90: 90th percentile
    - p95: 95th percentile
    - p99: 99th percentile
    - min: Minimum value
    - max: Maximum value
    - sum: Total sum
    - count: Count of values
    - std_dev: Standard deviation
    """

    @staticmethod
    def validate_data(data: List[Union[int, float]], allow_empty: bool = False) -> None:
        """
        Validate input data

        Args:
            data: List of numeric values
            allow_empty: Whether to allow empty lists

        Raises:
            AggregationError: If data is invalid
        """
        if not isinstance(data, (list, tuple)):
            raise AggregationError(f"Data must be a list or tuple, got {type(data)}")

        if not allow_empty and len(data) == 0:
            raise AggregationError("Cannot aggregate empty data")

        for i, value in enumerate(data):
            if not isinstance(value, (int, float)):
                raise AggregationError(
                    f"All values must be numeric, got {type(value)} at index {i}"
                )
            if math.isnan(value) or math.isinf(value):
                raise AggregationError(
                    f"Invalid numeric value at index {i}: {value}"
                )

    @staticmethod
    def mean(data: List[Union[int, float]]) -> float:
        """
        Calculate arithmetic mean (average)

        Use Case: Good for throughput; bad for latency (hides spikes)

        Args:
            data: List of numeric values

        Returns:
            Mean value

        Example:
            >>> Aggregation.mean([10, 20, 30, 40, 50])
            30.0
        """
        Aggregation.validate_data(data)
        return sum(data) / len(data)

    @staticmethod
    def avg(data: List[Union[int, float]]) -> float:
        """
        Alias for mean()

        Use Case: Good for throughput; bad for latency (hides spikes)
        """
        return Aggregation.mean(data)

    @staticmethod
    def median(data: List[Union[int, float]]) -> float:
        """
        Calculate median (50th percentile)

        Use Case: Good for "typical" user experience

        Args:
            data: List of numeric values

        Returns:
            Median value

        Example:
            >>> Aggregation.median([10, 20, 30, 40, 50])
            30.0
            >>> Aggregation.median([10, 20, 30, 40])
            25.0
        """
        Aggregation.validate_data(data)
        sorted_data = sorted(data)
        n = len(sorted_data)

        if n % 2 == 0:
            # Even number of elements - average the two middle values
            return (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2
        else:
            # Odd number of elements - return the middle value
            return float(sorted_data[n // 2])

    @staticmethod
    def p50(data: List[Union[int, float]]) -> float:
        """
        Alias for median() - 50th percentile

        Use Case: Good for "typical" user experience
        """
        return Aggregation.median(data)

    @staticmethod
    def percentile(data: List[Union[int, float]], p: float) -> float:
        """
        Calculate arbitrary percentile

        Args:
            data: List of numeric values
            p: Percentile value (0-100)

        Returns:
            Value at the given percentile

        Example:
            >>> Aggregation.percentile([10, 20, 30, 40, 50], 75)
            40.0
        """
        Aggregation.validate_data(data)

        if not 0 <= p <= 100:
            raise AggregationError(f"Percentile must be between 0 and 100, got {p}")

        if len(data) == 1:
            return float(data[0])

        sorted_data = sorted(data)
        n = len(sorted_data)

        # Using linear interpolation method (Type 7 in numpy)
        rank = (p / 100) * (n - 1)
        lower_index = int(math.floor(rank))
        upper_index = int(math.ceil(rank))

        if lower_index == upper_index:
            return float(sorted_data[lower_index])

        # Interpolate between the two nearest values
        weight = rank - lower_index
        return float(
            sorted_data[lower_index] * (1 - weight) +
            sorted_data[upper_index] * weight
        )

    @staticmethod
    def p90(data: List[Union[int, float]]) -> float:
        """
        Calculate 90th percentile

        Use Case: Ignores the worst 10% of outliers

        Args:
            data: List of numeric values

        Returns:
            90th percentile value

        Example:
            >>> Aggregation.p90([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
            91.0
        """
        return Aggregation.percentile(data, 90)

    @staticmethod
    def p95(data: List[Union[int, float]]) -> float:
        """
        Calculate 95th percentile

        Use Case: Standard for SLAs. "95% of users saw this speed."

        Args:
            data: List of numeric values

        Returns:
            95th percentile value

        Example:
            >>> Aggregation.p95([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
            95.5
        """
        return Aggregation.percentile(data, 95)

    @staticmethod
    def p99(data: List[Union[int, float]]) -> float:
        """
        Calculate 99th percentile

        Use Case: Strict performance monitoring

        Args:
            data: List of numeric values

        Returns:
            99th percentile value

        Example:
            >>> Aggregation.p99([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
            9.91
        """
        return Aggregation.percentile(data, 99)

    @staticmethod
    def min(data: List[Union[int, float]]) -> float:
        """
        Calculate minimum value

        Use Case: "What was the fastest we ever loaded?"

        Args:
            data: List of numeric values

        Returns:
            Minimum value

        Example:
            >>> Aggregation.min([10, 5, 20, 15])
            5.0
        """
        Aggregation.validate_data(data)
        return float(min(data))

    @staticmethod
    def max(data: List[Union[int, float]]) -> float:
        """
        Calculate maximum value

        Use Case: "What was the worst lag spike?"

        Args:
            data: List of numeric values

        Returns:
            Maximum value

        Example:
            >>> Aggregation.max([10, 5, 20, 15])
            20.0
        """
        Aggregation.validate_data(data)
        return float(max(data))

    @staticmethod
    def sum(data: List[Union[int, float]]) -> float:
        """
        Calculate sum of all values

        Use Case: Total bytes downloaded, total error count

        Args:
            data: List of numeric values

        Returns:
            Sum of all values

        Example:
            >>> Aggregation.sum([10, 20, 30, 40])
            100.0
        """
        Aggregation.validate_data(data, allow_empty=True)
        return float(sum(data))

    @staticmethod
    def count(data: List[Union[int, float]]) -> int:
        """
        Count number of values

        Use Case: Total number of tests run

        Args:
            data: List of numeric values

        Returns:
            Count of values

        Example:
            >>> Aggregation.count([10, 20, 30, 40])
            4
        """
        Aggregation.validate_data(data, allow_empty=True)
        return len(data)

    @staticmethod
    def std_dev(data: List[Union[int, float]], sample: bool = True) -> float:
        """
        Calculate standard deviation

        Use Case: How unstable/volatile is the network?

        Args:
            data: List of numeric values
            sample: If True, use sample std dev (n-1), else population (n)

        Returns:
            Standard deviation

        Example:
            >>> Aggregation.std_dev([10, 20, 30, 40, 50])
            15.811388300841896
        """
        Aggregation.validate_data(data)

        if len(data) < 2 and sample:
            raise AggregationError(
                "Sample standard deviation requires at least 2 values"
            )

        mean_val = Aggregation.mean(data)
        squared_diffs = [(x - mean_val) ** 2 for x in data]
        variance = sum(squared_diffs) / (len(data) - 1 if sample else len(data))

        return math.sqrt(variance)

    @staticmethod
    def variance(data: List[Union[int, float]], sample: bool = True) -> float:
        """
        Calculate variance

        Use Case: Measure of variability in the data

        Args:
            data: List of numeric values
            sample: If True, use sample variance (n-1), else population (n)

        Returns:
            Variance

        Example:
            >>> Aggregation.variance([10, 20, 30, 40, 50])
            250.0
        """
        std = Aggregation.std_dev(data, sample)
        return std ** 2

    @staticmethod
    def range(data: List[Union[int, float]]) -> float:
        """
        Calculate range (max - min)

        Use Case: Measure of spread in the data

        Args:
            data: List of numeric values

        Returns:
            Range (max - min)

        Example:
            >>> Aggregation.range([10, 20, 30, 40, 50])
            40.0
        """
        Aggregation.validate_data(data)
        return Aggregation.max(data) - Aggregation.min(data)

    @staticmethod
    def aggregate(data: List[Union[int, float]], method: str) -> float:
        """
        Apply aggregation method by name

        Args:
            data: List of numeric values
            method: Aggregation method name

        Returns:
            Aggregated value

        Raises:
            AggregationError: If method is unknown

        Example:
            >>> Aggregation.aggregate([10, 20, 30], "mean")
            20.0
            >>> Aggregation.aggregate([10, 20, 30], "p95")
            29.0
        """
        method = method.lower().strip()

        # Map method names to functions
        method_map = {
            'avg': Aggregation.avg,
            'mean': Aggregation.mean,
            'median': Aggregation.median,
            'p50': Aggregation.p50,
            'p90': Aggregation.p90,
            'p95': Aggregation.p95,
            'p99': Aggregation.p99,
            'min': Aggregation.min,
            'max': Aggregation.max,
            'sum': Aggregation.sum,
            'count': Aggregation.count,
            'std_dev': Aggregation.std_dev,
            'variance': Aggregation.variance,
            'range': Aggregation.range,
        }

        if method not in method_map:
            raise AggregationError(
                f"Unknown aggregation method: '{method}'. "
                f"Available methods: {', '.join(method_map.keys())}"
            )

        try:
            result = method_map[method](data)
            logger.debug(f"Aggregated {len(data)} values using {method}: {result}")
            return result
        except Exception as e:
            logger.error(f"Error applying aggregation {method}: {e}")
            raise

    @staticmethod
    def get_available_methods() -> List[str]:
        """
        Get list of available aggregation methods

        Returns:
            List of method names
        """
        return [
            'avg', 'mean', 'median', 'p50', 'p90', 'p95', 'p99',
            'min', 'max', 'sum', 'count', 'std_dev', 'variance', 'range'
        ]

    @staticmethod
    def get_method_info(method: str) -> dict:
        """
        Get information about an aggregation method

        Args:
            method: Aggregation method name

        Returns:
            Dictionary with method information
        """
        info_map = {
            'avg': {
                'name': 'Average (Mean)',
                'description': 'Arithmetic mean',
                'use_case': 'Good for throughput; bad for latency (hides spikes)',
                'alias': 'mean'
            },
            'mean': {
                'name': 'Mean (Average)',
                'description': 'Arithmetic mean',
                'use_case': 'Good for throughput; bad for latency (hides spikes)',
                'alias': 'avg'
            },
            'median': {
                'name': 'Median (P50)',
                'description': 'The middle value',
                'use_case': 'Good for "typical" user experience',
                'alias': 'p50'
            },
            'p50': {
                'name': 'P50 (Median)',
                'description': '50th Percentile',
                'use_case': 'Good for "typical" user experience',
                'alias': 'median'
            },
            'p90': {
                'name': 'P90',
                'description': '90th Percentile',
                'use_case': 'Ignores the worst 10% of outliers'
            },
            'p95': {
                'name': 'P95',
                'description': '95th Percentile',
                'use_case': 'Standard for SLAs. "95% of users saw this speed."'
            },
            'p99': {
                'name': 'P99',
                'description': '99th Percentile',
                'use_case': 'Strict performance monitoring'
            },
            'min': {
                'name': 'Minimum',
                'description': 'Minimum value',
                'use_case': '"What was the fastest we ever loaded?"'
            },
            'max': {
                'name': 'Maximum',
                'description': 'Maximum value',
                'use_case': '"What was the worst lag spike?"'
            },
            'sum': {
                'name': 'Sum',
                'description': 'Total sum',
                'use_case': 'Total bytes downloaded, total error count'
            },
            'count': {
                'name': 'Count',
                'description': 'Count of events',
                'use_case': 'Total number of tests run'
            },
            'std_dev': {
                'name': 'Standard Deviation',
                'description': 'Standard Deviation',
                'use_case': 'How unstable/volatile is the network?'
            }
        }

        method = method.lower().strip()
        return info_map.get(method, {'name': method, 'description': 'Unknown method'})


# Convenience function for quick access
def aggregate(data: List[Union[int, float]], method: str = 'mean') -> float:
    """
    Convenience function for quick aggregation

    Args:
        data: List of numeric values
        method: Aggregation method (default: 'mean')

    Returns:
        Aggregated value
    """
    return Aggregation.aggregate(data, method)


if __name__ == '__main__':
    # Example usage and testing
    test_data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    print("Aggregation Module - Example Usage")
    print("=" * 70)
    print(f"Test Data: {test_data}\n")

    for method in Aggregation.get_available_methods():
        try:
            result = Aggregation.aggregate(test_data, method)
            info = Aggregation.get_method_info(method)
            print(f"{info['name']:<20} = {result:>10.2f}")
            print(f"  Use Case: {info['use_case']}")
            print()
        except Exception as e:
            print(f"{method:<20} - Error: {e}\n")
