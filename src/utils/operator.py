#!/usr/bin/env python3
"""
Operator Utilities
Provides comparison operators for evaluating test expectations
"""

from typing import Union, List, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class OperatorError(Exception):
    """Custom exception for operator errors"""
    pass


class Operator:
    """
    Comparison operators for evaluating test expectations

    Supported operators:
    - eq (==): Equal to
    - neq (!=): Not equal to
    - lt (<): Less than
    - lte (<=): Less than or equal to
    - gt (>): Greater than
    - gte (>=): Greater than or equal to
    - between: Inside a range (x < value < y)
    """

    @staticmethod
    def validate_numeric(value: Any, name: str = "value") -> None:
        """
        Validate that a value is numeric

        Args:
            value: Value to validate
            name: Name of the value (for error messages)

        Raises:
            OperatorError: If value is not numeric
        """
        if not isinstance(value, (int, float)):
            raise OperatorError(
                f"{name} must be numeric, got {type(value).__name__}"
            )

    @staticmethod
    def eq(actual: Union[int, float], expected: Union[int, float], tolerance: float = 0.0) -> bool:
        """
        Equal to (==)

        Use Case: HTTP Code eq 200

        Args:
            actual: Actual measured value
            expected: Expected value
            tolerance: Tolerance for floating-point comparison (default: 0.0)

        Returns:
            True if actual equals expected (within tolerance)

        Example:
            >>> Operator.eq(200, 200)
            True
            >>> Operator.eq(200.5, 200.0, tolerance=1.0)
            True
            >>> Operator.eq(200, 404)
            False
        """
        Operator.validate_numeric(actual, "actual")
        Operator.validate_numeric(expected, "expected")

        if tolerance == 0.0:
            return actual == expected
        else:
            return abs(actual - expected) <= tolerance

    @staticmethod
    def neq(actual: Union[int, float], expected: Union[int, float], tolerance: float = 0.0) -> bool:
        """
        Not equal to (!=)

        Use Case: Error Count neq 0

        Args:
            actual: Actual measured value
            expected: Expected value
            tolerance: Tolerance for floating-point comparison (default: 0.0)

        Returns:
            True if actual does not equal expected

        Example:
            >>> Operator.neq(404, 200)
            True
            >>> Operator.neq(0, 0)
            False
            >>> Operator.neq(5.5, 5.0, tolerance=1.0)
            False
        """
        return not Operator.eq(actual, expected, tolerance)

    @staticmethod
    def lt(actual: Union[int, float], expected: Union[int, float]) -> bool:
        """
        Less than (<)

        Use Case: Jitter lt 30ms

        Args:
            actual: Actual measured value
            expected: Expected value

        Returns:
            True if actual is less than expected

        Example:
            >>> Operator.lt(25, 30)
            True
            >>> Operator.lt(30, 30)
            False
            >>> Operator.lt(35, 30)
            False
        """
        Operator.validate_numeric(actual, "actual")
        Operator.validate_numeric(expected, "expected")
        return actual < expected

    @staticmethod
    def lte(actual: Union[int, float], expected: Union[int, float]) -> bool:
        """
        Less than or equal to (<=)

        Use Case: Page Load lte 5000ms

        Args:
            actual: Actual measured value
            expected: Expected value

        Returns:
            True if actual is less than or equal to expected

        Example:
            >>> Operator.lte(4500, 5000)
            True
            >>> Operator.lte(5000, 5000)
            True
            >>> Operator.lte(5500, 5000)
            False
        """
        Operator.validate_numeric(actual, "actual")
        Operator.validate_numeric(expected, "expected")
        return actual <= expected

    @staticmethod
    def gt(actual: Union[int, float], expected: Union[int, float]) -> bool:
        """
        Greater than (>)

        Use Case: Throughput gt 100Mbps

        Args:
            actual: Actual measured value
            expected: Expected value

        Returns:
            True if actual is greater than expected

        Example:
            >>> Operator.gt(150, 100)
            True
            >>> Operator.gt(100, 100)
            False
            >>> Operator.gt(50, 100)
            False
        """
        Operator.validate_numeric(actual, "actual")
        Operator.validate_numeric(expected, "expected")
        return actual > expected

    @staticmethod
    def gte(actual: Union[int, float], expected: Union[int, float]) -> bool:
        """
        Greater than or equal to (>=)

        Use Case: Success Rate gte 95%

        Args:
            actual: Actual measured value
            expected: Expected value

        Returns:
            True if actual is greater than or equal to expected

        Example:
            >>> Operator.gte(97, 95)
            True
            >>> Operator.gte(95, 95)
            True
            >>> Operator.gte(93, 95)
            False
        """
        Operator.validate_numeric(actual, "actual")
        Operator.validate_numeric(expected, "expected")
        return actual >= expected

    @staticmethod
    def between(
        actual: Union[int, float],
        expected: Union[List, Tuple],
        inclusive: str = 'neither'
    ) -> bool:
        """
        Between range (x < value < y)

        Use Case: Bitrate between [2000, 5000]

        Args:
            actual: Actual measured value
            expected: Range as [min, max] or (min, max)
            inclusive: 'neither' (default), 'both', 'left', 'right'

        Returns:
            True if actual is within the range

        Example:
            >>> Operator.between(3000, [2000, 5000])
            True
            >>> Operator.between(2000, [2000, 5000], inclusive='both')
            True
            >>> Operator.between(2000, [2000, 5000], inclusive='neither')
            False
            >>> Operator.between(6000, [2000, 5000])
            False
        """
        Operator.validate_numeric(actual, "actual")

        if not isinstance(expected, (list, tuple)) or len(expected) != 2:
            raise OperatorError(
                f"'between' expected value must be a list/tuple of 2 values, "
                f"got {type(expected).__name__} with {len(expected) if isinstance(expected, (list, tuple)) else 0} values"
            )

        min_val, max_val = expected
        Operator.validate_numeric(min_val, "min_val")
        Operator.validate_numeric(max_val, "max_val")

        if min_val > max_val:
            raise OperatorError(
                f"Invalid range: min ({min_val}) is greater than max ({max_val})"
            )

        inclusive = inclusive.lower()

        if inclusive == 'both':
            return min_val <= actual <= max_val
        elif inclusive == 'left':
            return min_val <= actual < max_val
        elif inclusive == 'right':
            return min_val < actual <= max_val
        elif inclusive == 'neither':
            return min_val < actual < max_val
        else:
            raise OperatorError(
                f"Invalid inclusive parameter: '{inclusive}'. "
                f"Must be 'neither', 'both', 'left', or 'right'"
            )

    @staticmethod
    def evaluate(
        actual: Union[int, float],
        operator: str,
        expected: Union[int, float, List, Tuple],
        **kwargs
    ) -> bool:
        """
        Evaluate a comparison using operator name

        Args:
            actual: Actual measured value
            operator: Operator name (eq, neq, lt, lte, gt, gte, between)
            expected: Expected value or range
            **kwargs: Additional arguments (tolerance, inclusive)

        Returns:
            True if comparison passes, False otherwise

        Raises:
            OperatorError: If operator is unknown

        Example:
            >>> Operator.evaluate(100, 'gte', 95)
            True
            >>> Operator.evaluate(3000, 'between', [2000, 5000])
            True
            >>> Operator.evaluate(200, 'eq', 200)
            True
        """
        operator = operator.lower().strip()

        # Map operator names to functions
        operator_map = {
            'eq': lambda a, e, **kw: Operator.eq(a, e, tolerance=kw.get('tolerance', 0.0)),
            'neq': lambda a, e, **kw: Operator.neq(a, e, tolerance=kw.get('tolerance', 0.0)),
            'lt': lambda a, e, **kw: Operator.lt(a, e),
            'lte': lambda a, e, **kw: Operator.lte(a, e),
            'gt': lambda a, e, **kw: Operator.gt(a, e),
            'gte': lambda a, e, **kw: Operator.gte(a, e),
            'between': lambda a, e, **kw: Operator.between(a, e, inclusive=kw.get('inclusive', 'neither')),
        }

        # Support alternative names
        alias_map = {
            '==': 'eq',
            '!=': 'neq',
            '<': 'lt',
            '<=': 'lte',
            '>': 'gt',
            '>=': 'gte',
            'equals': 'eq',
            'not_equals': 'neq',
            'less_than': 'lt',
            'less_than_or_equal': 'lte',
            'greater_than': 'gt',
            'greater_than_or_equal': 'gte',
            'in_range': 'between',
        }

        # Resolve alias
        operator = alias_map.get(operator, operator)

        if operator not in operator_map:
            raise OperatorError(
                f"Unknown operator: '{operator}'. "
                f"Available operators: {', '.join(operator_map.keys())}"
            )

        try:
            result = operator_map[operator](actual, expected, **kwargs)
            logger.debug(
                f"Evaluated: {actual} {operator} {expected} = {result}"
            )
            return result
        except OperatorError:
            raise
        except Exception as e:
            logger.error(f"Error evaluating operator {operator}: {e}")
            raise OperatorError(f"Error evaluating operator {operator}: {e}")

    @staticmethod
    def get_available_operators() -> List[str]:
        """
        Get list of available operators

        Returns:
            List of operator names
        """
        return ['eq', 'neq', 'lt', 'lte', 'gt', 'gte', 'between']

    @staticmethod
    def get_operator_info(operator: str) -> dict:
        """
        Get information about an operator

        Args:
            operator: Operator name

        Returns:
            Dictionary with operator information
        """
        info_map = {
            'eq': {
                'name': 'Equal To',
                'symbol': '==',
                'description': 'Equal to',
                'use_case': 'HTTP Code eq 200',
                'example': 'actual == expected'
            },
            'neq': {
                'name': 'Not Equal To',
                'symbol': '!=',
                'description': 'Not equal to',
                'use_case': 'Error Count neq 0',
                'example': 'actual != expected'
            },
            'lt': {
                'name': 'Less Than',
                'symbol': '<',
                'description': 'Less than',
                'use_case': 'Jitter lt 30ms',
                'example': 'actual < expected'
            },
            'lte': {
                'name': 'Less Than or Equal',
                'symbol': '<=',
                'description': 'Less than or equal to',
                'use_case': 'Page Load lte 5000ms',
                'example': 'actual <= expected'
            },
            'gt': {
                'name': 'Greater Than',
                'symbol': '>',
                'description': 'Greater than',
                'use_case': 'Throughput gt 100Mbps',
                'example': 'actual > expected'
            },
            'gte': {
                'name': 'Greater Than or Equal',
                'symbol': '>=',
                'description': 'Greater than or equal to',
                'use_case': 'Success Rate gte 95%',
                'example': 'actual >= expected'
            },
            'between': {
                'name': 'Between',
                'symbol': 'x < y < z',
                'description': 'Inside a range',
                'use_case': 'Bitrate between [2000, 5000]',
                'example': 'min < actual < max'
            }
        }

        operator = operator.lower().strip()
        return info_map.get(operator, {
            'name': operator,
            'description': 'Unknown operator'
        })

    @staticmethod
    def get_symbol(operator: str) -> str:
        """
        Get mathematical symbol for an operator

        Args:
            operator: Operator name

        Returns:
            Mathematical symbol
        """
        symbol_map = {
            'eq': '==',
            'neq': '!=',
            'lt': '<',
            'lte': '<=',
            'gt': '>',
            'gte': '>=',
            'between': 'x < y < z'
        }
        return symbol_map.get(operator.lower(), operator)


# Convenience function for quick evaluation
def compare(actual: Union[int, float], operator: str, expected: Union[int, float, List, Tuple], **kwargs) -> bool:
    """
    Convenience function for quick comparison

    Args:
        actual: Actual value
        operator: Operator name
        expected: Expected value
        **kwargs: Additional arguments

    Returns:
        Comparison result
    """
    return Operator.evaluate(actual, operator, expected, **kwargs)


if __name__ == '__main__':
    # Example usage and testing
    print("Operator Module - Example Usage")
    print("=" * 70)

    test_cases = [
        (100, 'gte', 95, {}, "Success Rate >= 95%"),
        (200, 'eq', 200, {}, "HTTP Code == 200"),
        (5, 'neq', 0, {}, "Error Count != 0"),
        (25, 'lt', 30, {}, "Jitter < 30ms"),
        (4500, 'lte', 5000, {}, "Page Load <= 5000ms"),
        (150, 'gt', 100, {}, "Throughput > 100Mbps"),
        (3000, 'between', [2000, 5000], {}, "Bitrate between [2000, 5000]"),
        (2000, 'between', [2000, 5000], {'inclusive': 'both'}, "Bitrate between [2000, 5000] (inclusive)"),
    ]

    for actual, op, expected, kwargs, description in test_cases:
        result = Operator.evaluate(actual, op, expected, **kwargs)
        symbol = Operator.get_symbol(op)
        print(f"\n{description}")
        print(f"  {actual} {symbol} {expected} = {result}")
        print(f"  Result: {'PASS' if result else 'FAIL'}")

    print("\n" + "=" * 70)
    print("\nAvailable Operators:")
    for op in Operator.get_available_operators():
        info = Operator.get_operator_info(op)
        print(f"\n{info['name']} ({info['symbol']})")
        print(f"  Use Case: {info['use_case']}")
