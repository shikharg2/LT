#!/usr/bin/env python3
"""
Load Test Utilities Package

Provides comprehensive utilities for test metrics collection, aggregation,
operator evaluation, and scope management.
"""

from .aggregation import Aggregation, aggregate, AggregationError
from .operator import Operator, compare, OperatorError
from .evaluation_scope import (
    EvaluationScope,
    DataPoint,
    per_iteration,
    aggregate as scope_aggregate,
    windowed,
    success_rate,
    EvaluationScopeError
)
from .metrics_collector import MetricsCollector, MetricsCollectorError

__version__ = '1.0.0'

__all__ = [
    # Aggregation
    'Aggregation',
    'aggregate',
    'AggregationError',

    # Operators
    'Operator',
    'compare',
    'OperatorError',

    # Evaluation Scope
    'EvaluationScope',
    'DataPoint',
    'per_iteration',
    'scope_aggregate',
    'windowed',
    'success_rate',
    'EvaluationScopeError',

    # Metrics Collector
    'MetricsCollector',
    'MetricsCollectorError',
]
