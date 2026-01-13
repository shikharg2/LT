#!/usr/bin/env python3
"""
Speed Test Script using iperf3
Performs speed tests on public and private servers based on configuration from main.json
Supports scheduling with start_time field: "immediate", "+Xm" (minutes), or ISO datetime
"""

import json
import csv
import subprocess
import time
import signal
import schedule
import os
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import logging
import sys

# Import aggregation utilities
try:
    from src.utils.aggregation import Aggregation
except ImportError:
    # Fallback for running from different directories
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from src.utils.aggregation import Aggregation


class SpeedTest:
    """Speed test runner using iperf3 with scheduling support"""

    def __init__(self, config_path: str = "./configurations/main.json"):
        """Initialize the speed test runner"""
        self.config_path = config_path
        self.config = self.load_config()
        self.setup_logging()
        self.results = []
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Configuration file '{self.config_path}' not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in configuration file: {e}")
            sys.exit(1)

    def setup_logging(self):
        """Setup logging based on global settings"""
        log_level = self.config.get('global_settings', {}).get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.running = False
        sys.exit(0)

    def get_db_connection(self):
        """Get database connection from environment variables"""
        try:
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'speedtest'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres')
            )
            return conn
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return None

    def write_results_to_db(self, results: List[Dict]):
        """Write test results to PostgreSQL database"""
        if not results:
            self.logger.warning("No results to write to database")
            return

        conn = self.get_db_connection()
        if not conn:
            self.logger.error("Cannot write to database: connection failed")
            return

        try:
            cursor = conn.cursor()

            insert_query = """
                INSERT INTO speed_test.test_results
                (timestamp, scenario_id, iteration, server_type, server, port,
                test_type, status, mbps, bits_per_second, bytes, retransmits,
                jitter_ms, error_message)
                VALUES %s
            """

            values = []
            for result in results:
                values.append((
                    result.get('timestamp'),
                    result.get('scenario_id'),
                    result.get('iteration'),
                    result.get('server_type'),
                    result.get('server'),
                    result.get('port'),
                    result.get('test_type'),
                    result.get('status'),
                    result.get('mbps'),
                    result.get('bits_per_second'),
                    result.get('bytes'),
                    result.get('retransmits'),
                    result.get('jitter_ms'),
                    result.get('error', '')
                ))

            execute_values(cursor, insert_query, values)
            conn.commit()
            self.logger.info(f"Wrote {len(results)} results to database")

        except Exception as e:
            self.logger.error(f"Failed to write results to database: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    def write_evaluations_to_db(self, evaluations: List[Dict]):
        """Write evaluation results to PostgreSQL database"""
        if not evaluations:
            return

        conn = self.get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            insert_query = """
                INSERT INTO speed_test.test_evaluations
                (timestamp, scenario_id, iteration, metric, operator, expected_value,
                actual_value, unit, evaluation_scope, test_index, passed, verdict)
                VALUES %s
            """

            values = []
            for evaluation in evaluations:
                values.append((
                    datetime.now(),
                    evaluation.get('scenario_id', ''),
                    evaluation.get('iteration'),
                    evaluation.get('metric'),
                    evaluation.get('operator'),
                    evaluation.get('expected_value'),
                    evaluation.get('actual_value'),
                    evaluation.get('unit'),
                    evaluation.get('evaluation_scope'),
                    str(evaluation.get('test_index')),
                    evaluation.get('passed'),
                    evaluation.get('verdict')
                ))

            execute_values(cursor, insert_query, values)
            conn.commit()
            self.logger.info(f"Wrote {len(evaluations)} evaluations to database")

        except Exception as e:
            self.logger.error(f"Failed to write evaluations to database: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    def parse_start_time(self, start_time: str) -> Optional[datetime]:
        """
        Parse start_time field from configuration

        Supports:
        - "immediate": Start immediately (returns None)
        - "+Xm": Start in X minutes from now (e.g., "+5m")
        - "+Xh": Start in X hours from now (e.g., "+2h")
        - ISO datetime string: Start at specific time (e.g., "2024-01-15T10:30:00")

        Args:
            start_time: Start time specification from config

        Returns:
            datetime object for scheduled start, or None for immediate
        """
        if not start_time or start_time.lower() == "immediate":
            return None

        # Handle relative time formats (+Xm, +Xh)
        if start_time.startswith('+'):
            time_spec = start_time[1:]  # Remove '+'

            if time_spec.endswith('m'):
                # Minutes
                try:
                    minutes = int(time_spec[:-1])
                    return datetime.now() + timedelta(minutes=minutes)
                except ValueError:
                    self.logger.error(f"Invalid minute format: {start_time}")
                    return None

            elif time_spec.endswith('h'):
                # Hours
                try:
                    hours = int(time_spec[:-1])
                    return datetime.now() + timedelta(hours=hours)
                except ValueError:
                    self.logger.error(f"Invalid hour format: {start_time}")
                    return None
            else:
                self.logger.error(f"Unknown time unit in: {start_time}")
                return None

        # Try to parse as ISO datetime
        try:
            return datetime.fromisoformat(start_time)
        except ValueError:
            self.logger.error(f"Invalid datetime format: {start_time}")
            return None

    def calculate_delay(self, target_time: Optional[datetime]) -> float:
        """
        Calculate delay in seconds until target time

        Args:
            target_time: Target datetime to start, or None for immediate

        Returns:
            Delay in seconds (0 for immediate)
        """
        if target_time is None:
            return 0

        now = datetime.now()
        if target_time <= now:
            self.logger.warning(f"Target time {target_time} is in the past. Starting immediately.")
            return 0

        delay_seconds = (target_time - now).total_seconds()
        return delay_seconds

    def get_speed_test_scenarios(self) -> List[Dict]:
        """Extract speed test scenarios from config"""
        scenarios = []
        for scenario in self.config.get('scenarios', []):
            if scenario.get('protocol') == 'speed_test' and scenario.get('enabled', False):
                scenarios.append(scenario)
        return scenarios

    def run_iperf3_test(self, server: str, port: int, duration: int,
                        reverse: bool = False, bandwidth: str = None) -> Dict:
        """
        Run iperf3 test against a server

        Args:
            server: Server IP or hostname
            port: Server port
            duration: Test duration in seconds
            reverse: If True, run download test (reverse mode), else upload
            bandwidth: Bandwidth limit for test (e.g., "10M")

        Returns:
            Dictionary containing test results
        """
        cmd = ['iperf3', '-c', server, '-p', str(port), '-t', str(duration), '-J']

        if reverse:
            cmd.append('-R')

        if bandwidth:
            cmd.extend(['-b', f'{bandwidth}M'])

        self.logger.info(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                return self.parse_iperf3_results(data, server, port, reverse)
            else:
                self.logger.error(f"iperf3 failed: {result.stderr}")
                return {
                    'server': server,
                    'port': port,
                    'test_type': 'download' if reverse else 'upload',
                    'status': 'failed',
                    'error': result.stderr,
                    'bits_per_second': 0,
                    'mbps': 0
                }
        except subprocess.TimeoutExpired:
            self.logger.error(f"iperf3 test timed out for {server}:{port}")
            return {
                'server': server,
                'port': port,
                'test_type': 'download' if reverse else 'upload',
                'status': 'timeout',
                'bits_per_second': 0,
                'mbps': 0
            }
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse iperf3 output: {e}")
            return {
                'server': server,
                'port': port,
                'test_type': 'download' if reverse else 'upload',
                'status': 'parse_error',
                'bits_per_second': 0,
                'mbps': 0
            }
        except Exception as e:
            self.logger.error(f"Unexpected error during iperf3 test: {e}")
            return {
                'server': server,
                'port': port,
                'test_type': 'download' if reverse else 'upload',
                'status': 'error',
                'error': str(e),
                'bits_per_second': 0,
                'mbps': 0
            }

    def parse_iperf3_results(self, data: Dict, server: str, port: int, reverse: bool) -> Dict:
        """Parse iperf3 JSON output"""
        try:
            end_data = data.get('end', {})
            sum_sent = end_data.get('sum_sent', {})
            sum_received = end_data.get('sum_received', {})

            # For download test (reverse), we care about received data
            # For upload test, we care about sent data
            relevant_data = sum_received if reverse else sum_sent

            bits_per_second = relevant_data.get('bits_per_second', 0)
            mbps = bits_per_second / 1_000_000

            return {
                'server': server,
                'port': port,
                'test_type': 'download' if reverse else 'upload',
                'status': 'success',
                'bits_per_second': bits_per_second,
                'mbps': round(mbps, 2),
                'bytes': relevant_data.get('bytes', 0),
                'retransmits': sum_sent.get('retransmits', 0) if not reverse else 0,
                'jitter_ms': sum_received.get('jitter_ms', 0) if reverse else 0
            }
        except Exception as e:
            self.logger.error(f"Error parsing iperf3 results: {e}")
            return {
                'server': server,
                'port': port,
                'test_type': 'download' if reverse else 'upload',
                'status': 'parse_error',
                'bits_per_second': 0,
                'mbps': 0
            }

    def evaluate_expectation(self, metric_value: float, operator: str,
                           expected_value: float) -> bool:
        """
        Evaluate if a metric meets the expectation

        Args:
            metric_value: Actual measured value
            operator: Comparison operator (gte, lte, eq, neq, gt, lt, between)
            expected_value: Expected value or list for 'between'

        Returns:
            True if expectation is met, False otherwise
        """
        operators_map = {
            'gte': lambda x, y: x >= y,
            'lte': lambda x, y: x <= y,
            'gt': lambda x, y: x > y,
            'lt': lambda x, y: x < y,
            'eq': lambda x, y: x == y,
            'neq': lambda x, y: x != y
        }

        if operator == 'between':
            # expected_value should be a list [min, max]
            if isinstance(expected_value, list) and len(expected_value) == 2:
                return expected_value[0] < metric_value < expected_value[1]
            else:
                self.logger.warning(f"Invalid 'between' value: {expected_value}")
                return False

        if operator in operators_map:
            return operators_map[operator](metric_value, expected_value)

        self.logger.warning(f"Unknown operator: {operator}")
        return False

    def evaluate_results(self, results: List[Dict], expectations: List[Dict],
                        iteration: int) -> List[Dict]:
        """
        Evaluate test results against expectations

        Args:
            results: List of test results
            expectations: List of expectations from config
            iteration: Current iteration number

        Returns:
            List of evaluation results
        """
        evaluations = []

        for expectation in expectations:
            metric = expectation.get('metric')
            operator = expectation.get('operator')
            expected_value = expectation.get('value')
            evaluation_scope = expectation.get('evaluation_scope', 'per_iteration')
            aggregation_method = expectation.get('aggregation', 'avg')
            unit = expectation.get('unit', '')

            # Skip scenario-scoped expectations (handled at scenario end)
            if evaluation_scope == 'scenario':
                continue

            # Convert expected_value to appropriate type
            try:
                if isinstance(expected_value, str):
                    expected_value = float(expected_value)
            except ValueError:
                pass

            # Extract metric values based on metric name
            if metric == 'download_speed':
                metric_values = [r['mbps'] for r in results if r['test_type'] == 'download']
            elif metric == 'upload_speed':
                metric_values = [r['mbps'] for r in results if r['test_type'] == 'upload']
            else:
                self.logger.warning(f"Unknown metric: {metric}")
                continue

            if not metric_values:
                self.logger.warning(f"No data for metric: {metric}")
                continue

            # For per_iteration, evaluate each value separately
            if evaluation_scope == 'per_iteration':
                for idx, value in enumerate(metric_values):
                    passed = self.evaluate_expectation(value, operator, expected_value)
                    evaluations.append({
                        'iteration': iteration,
                        'metric': metric,
                        'operator': operator,
                        'expected_value': expected_value,
                        'actual_value': value,
                        'unit': unit,
                        'evaluation_scope': evaluation_scope,
                        'aggregation': 'none',
                        'test_index': idx,
                        'passed': passed,
                        'verdict': 'PASS' if passed else 'FAIL'
                    })
            elif evaluation_scope == 'overall':
                # For overall, use specified aggregation method
                try:
                    aggregated_value = Aggregation.aggregate(metric_values, aggregation_method)
                except Exception as e:
                    self.logger.warning(f"Aggregation error: {e}, falling back to avg")
                    aggregated_value = sum(metric_values) / len(metric_values)

                passed = self.evaluate_expectation(aggregated_value, operator, expected_value)
                evaluations.append({
                    'iteration': iteration,
                    'metric': metric,
                    'operator': operator,
                    'expected_value': expected_value,
                    'actual_value': round(aggregated_value, 2),
                    'unit': unit,
                    'evaluation_scope': evaluation_scope,
                    'aggregation': aggregation_method,
                    'test_index': 'all',
                    'passed': passed,
                    'verdict': 'PASS' if passed else 'FAIL'
                })

        return evaluations

    def evaluate_scenario(self, all_results: List[Dict], expectations: List[Dict],
                          scenario_id: str) -> List[Dict]:
        """
        Evaluate scenario-level expectations across all iterations

        Args:
            all_results: All test results from the scenario
            expectations: List of expectations from config
            scenario_id: Scenario identifier

        Returns:
            List of scenario-level evaluation results
        """
        evaluations = []

        for expectation in expectations:
            evaluation_scope = expectation.get('evaluation_scope', 'per_iteration')

            # Only process scenario-scoped expectations
            if evaluation_scope != 'scenario':
                continue

            metric = expectation.get('metric')
            operator = expectation.get('operator')
            expected_value = expectation.get('value')
            aggregation_method = expectation.get('aggregation', 'avg')
            unit = expectation.get('unit', '')

            # Convert expected_value to appropriate type
            try:
                if isinstance(expected_value, str):
                    expected_value = float(expected_value)
            except ValueError:
                pass

            # Extract all metric values across all iterations
            if metric == 'download_speed':
                metric_values = [r['mbps'] for r in all_results if r['test_type'] == 'download' and r.get('status') == 'success']
            elif metric == 'upload_speed':
                metric_values = [r['mbps'] for r in all_results if r['test_type'] == 'upload' and r.get('status') == 'success']
            else:
                self.logger.warning(f"Unknown metric for scenario evaluation: {metric}")
                continue

            if not metric_values:
                self.logger.warning(f"No successful data for scenario metric: {metric}")
                evaluations.append({
                    'scenario_id': scenario_id,
                    'iteration': 'all',
                    'metric': metric,
                    'operator': operator,
                    'expected_value': expected_value,
                    'actual_value': 0,
                    'unit': unit,
                    'evaluation_scope': evaluation_scope,
                    'aggregation': aggregation_method,
                    'test_index': 'scenario',
                    'sample_count': 0,
                    'passed': False,
                    'verdict': 'FAIL'
                })
                continue

            # Apply aggregation method
            try:
                aggregated_value = Aggregation.aggregate(metric_values, aggregation_method)
            except Exception as e:
                self.logger.error(f"Aggregation error for scenario: {e}")
                aggregated_value = sum(metric_values) / len(metric_values)

            passed = self.evaluate_expectation(aggregated_value, operator, expected_value)

            evaluations.append({
                'scenario_id': scenario_id,
                'iteration': 'all',
                'metric': metric,
                'operator': operator,
                'expected_value': expected_value,
                'actual_value': round(aggregated_value, 2),
                'unit': unit,
                'evaluation_scope': evaluation_scope,
                'aggregation': aggregation_method,
                'test_index': 'scenario',
                'sample_count': len(metric_values),
                'passed': passed,
                'verdict': 'PASS' if passed else 'FAIL'
            })

            self.logger.info(
                f"Scenario evaluation: {metric} {aggregation_method}={aggregated_value:.2f} "
                f"{operator} {expected_value} -> {'PASS' if passed else 'FAIL'}"
            )

        return evaluations

    def parse_server_spec(self, server_spec: str) -> Tuple[str, int]:
        """
        Parse server specification in format 'ip:port' or 'url:port'

        Args:
            server_spec: Server specification string (e.g., '192.168.1.1:5201', 'iperf.example.com:5201')

        Returns:
            Tuple of (server, port)
        """
        # Remove protocol if present (http://, https://)
        if '://' in server_spec:
            server_spec = server_spec.split('://', 1)[1]

        # Remove trailing slash if present
        server_spec = server_spec.rstrip('/')

        # Parse server and port
        if ':' in server_spec:
            # Use rsplit to handle IPv6 addresses or URLs with multiple colons
            server, port_str = server_spec.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                self.logger.warning(f"Invalid port '{port_str}' in '{server_spec}', using default 5201")
                port = 5201
        else:
            server = server_spec
            port = 5201  # Default iperf3 port

        return server, port

    def run_speed_test_scenario(self, scenario: Dict):
        """Run a complete speed test scenario"""
        scenario_id = scenario.get('id', 'unknown')
        self.logger.info(f"Starting speed test scenario: {scenario_id}")

        schedule = scenario.get('schedule', {})
        mode = schedule.get('mode', 'once')
        recurring_interval = int(schedule.get('recurring_interval', 60))
        recurring_times = int(schedule.get('recurring_times', 1))

        parameters = scenario.get('parameters', {})
        private_servers = parameters.get('private', [])
        public_servers = parameters.get('public', [])
        duration = int(parameters.get('duration', 10))
        uplink_mbps = parameters.get('uplink', '10')
        downlink_mbps = parameters.get('downlink', '100')

        expectations = scenario.get('expectations', [])

        # Determine number of iterations
        iterations = 1 if mode == 'once' else recurring_times

        # Collect all results for scenario-level evaluation
        all_scenario_results = []

        for iteration in range(1, iterations + 1):
            self.logger.info(f"Running iteration {iteration}/{iterations}")
            iteration_results = []
            timestamp = datetime.now().isoformat()

            # Test private servers
            for server_spec in private_servers:
                # Parse server specification (IP:PORT)
                server, port = self.parse_server_spec(server_spec)

                self.logger.info(f"Testing private server: {server}:{port}")

                # Upload test
                upload_result = self.run_iperf3_test(
                    server, port, duration, reverse=False, bandwidth=uplink_mbps
                )
                upload_result['timestamp'] = timestamp
                upload_result['iteration'] = iteration
                upload_result['server_type'] = 'private'
                upload_result['scenario_id'] = scenario_id
                iteration_results.append(upload_result)

                # Download test
                download_result = self.run_iperf3_test(
                    server, port, duration, reverse=True, bandwidth=downlink_mbps
                )
                download_result['timestamp'] = timestamp
                download_result['iteration'] = iteration
                download_result['server_type'] = 'private'
                download_result['scenario_id'] = scenario_id
                iteration_results.append(download_result)

            # Test public servers
            for server_spec in public_servers:
                # Parse server specification (can be URL:PORT or just URL)
                server, port = self.parse_server_spec(server_spec)

                self.logger.info(f"Testing public server: {server}:{port}")

                # Upload test
                upload_result = self.run_iperf3_test(
                    server, port, duration, reverse=False, bandwidth=uplink_mbps
                )
                upload_result['timestamp'] = timestamp
                upload_result['iteration'] = iteration
                upload_result['server_type'] = 'public'
                upload_result['scenario_id'] = scenario_id
                iteration_results.append(upload_result)

                # Download test
                download_result = self.run_iperf3_test(
                    server, port, duration, reverse=True, bandwidth=downlink_mbps
                )
                download_result['timestamp'] = timestamp
                download_result['iteration'] = iteration
                download_result['server_type'] = 'public'
                download_result['scenario_id'] = scenario_id
                iteration_results.append(download_result)

            # Evaluate per-iteration and overall results
            evaluations = self.evaluate_results(iteration_results, expectations, iteration)

            # Add scenario_id to evaluations
            for evaluation in evaluations:
                evaluation['scenario_id'] = scenario_id

            # Store results
            for result in iteration_results:
                self.results.append(result)
                all_scenario_results.append(result)

            # Write to database
            self.write_results_to_db(iteration_results)
            self.write_evaluations_to_db(evaluations)

            # Write evaluations to CSV
            self.write_evaluations(evaluations, scenario_id)

            # Wait before next iteration (except for last iteration)
            if iteration < iterations and mode == 'recurring':
                wait_seconds = recurring_interval * 60
                self.logger.info(f"Waiting {recurring_interval} minutes before next iteration...")
                time.sleep(wait_seconds)

        # After all iterations, evaluate scenario-level expectations
        scenario_evaluations = self.evaluate_scenario(all_scenario_results, expectations, scenario_id)
        if scenario_evaluations:
            self.write_scenario_evaluations(scenario_evaluations, scenario_id)
            self.write_evaluations_to_db(scenario_evaluations)

        # Write aggregation metrics for the entire scenario
        self.write_aggregation_metrics(all_scenario_results, scenario_id)

        self.logger.info(f"Completed speed test scenario: {scenario_id}")

    def write_evaluations(self, evaluations: List[Dict], scenario_id: str):
        """Write evaluation results to CSV file"""
        report_path = Path(self.config.get('global_settings', {}).get('report_path', './results/speed_test/'))
        report_path.mkdir(parents=True, exist_ok=True)

        eval_file = report_path / f'{scenario_id}_evaluations.csv'

        # Check if file exists to determine if we need to write headers
        file_exists = eval_file.exists()

        with open(eval_file, 'a', newline='') as f:
            if evaluations:
                writer = csv.DictWriter(f, fieldnames=evaluations[0].keys())

                if not file_exists:
                    writer.writeheader()

                for evaluation in evaluations:
                    writer.writerow(evaluation)

        self.logger.info(f"Wrote evaluations to {eval_file}")

    def write_scenario_evaluations(self, evaluations: List[Dict], scenario_id: str):
        """Write scenario-level evaluation results to a separate CSV file"""
        if not evaluations:
            return

        report_path = Path(self.config.get('global_settings', {}).get('report_path', './results/speed_test/'))
        report_path.mkdir(parents=True, exist_ok=True)

        eval_file = report_path / f'{scenario_id}_scenario_summary.csv'

        # Always overwrite scenario summary (it's a final summary)
        with open(eval_file, 'w', newline='') as f:
            fieldnames = [
                'scenario_id', 'timestamp', 'metric', 'aggregation', 'actual_value',
                'operator', 'expected_value', 'unit', 'sample_count', 'passed', 'verdict'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()

            timestamp = datetime.now().isoformat()
            for evaluation in evaluations:
                evaluation['timestamp'] = timestamp
                writer.writerow(evaluation)

        self.logger.info(f"Wrote scenario summary to {eval_file}")

    def write_aggregation_metrics(self, all_results: List[Dict], scenario_id: str):
        """Write all aggregation metrics to a separate file"""
        report_path = Path(self.config.get('global_settings', {}).get('report_path', './results/speed_test/'))
        report_path.mkdir(parents=True, exist_ok=True)

        metrics_file = report_path / f'{scenario_id}_aggregation_metrics.csv'

        # Collect metrics for download and upload
        download_values = [r['mbps'] for r in all_results if r['test_type'] == 'download' and r.get('status') == 'success']
        upload_values = [r['mbps'] for r in all_results if r['test_type'] == 'upload' and r.get('status') == 'success']

        rows = []
        timestamp = datetime.now().isoformat()

        # Available aggregation methods
        aggregation_methods = ['avg', 'median', 'p90', 'p95', 'p99', 'min', 'max', 'std_dev', 'count']

        for test_type, values in [('download_speed', download_values), ('upload_speed', upload_values)]:
            if not values:
                continue

            for method in aggregation_methods:
                try:
                    if method == 'count':
                        value = len(values)
                    else:
                        value = Aggregation.aggregate(values, method)
                    rows.append({
                        'scenario_id': scenario_id,
                        'timestamp': timestamp,
                        'metric': test_type,
                        'aggregation': method,
                        'value': round(value, 2) if isinstance(value, float) else value,
                        'unit': 'mbps' if method != 'count' else 'samples'
                    })
                except Exception as e:
                    self.logger.debug(f"Could not compute {method} for {test_type}: {e}")

        if rows:
            with open(metrics_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['scenario_id', 'timestamp', 'metric', 'aggregation', 'value', 'unit'])
                writer.writeheader()
                writer.writerows(rows)

            self.logger.info(f"Wrote aggregation metrics to {metrics_file}")

    def write_results(self):
        """Write all test results to CSV file"""
        if not self.results:
            self.logger.warning("No results to write")
            return

        report_path = Path(self.config.get('global_settings', {}).get('report_path', './results/speed_test/'))
        report_path.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = report_path / f'speed_test_results_{timestamp_str}.csv'

        # Collect all unique field names from all results
        all_fieldnames = set()
        for result in self.results:
            all_fieldnames.update(result.keys())

        # Define preferred field order
        preferred_order = [
            'timestamp', 'scenario_id', 'iteration', 'server_type', 'server', 'port',
            'test_type', 'status', 'mbps', 'bits_per_second', 'bytes',
            'retransmits', 'jitter_ms', 'error'
        ]

        # Sort fieldnames: preferred fields first, then alphabetically
        fieldnames = []
        for field in preferred_order:
            if field in all_fieldnames:
                fieldnames.append(field)
                all_fieldnames.remove(field)
        fieldnames.extend(sorted(all_fieldnames))

        with open(results_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.results)

        self.logger.info(f"Wrote {len(self.results)} results to {results_file}")

    def run_tests_now(self):
        """Execute tests immediately (called by scheduler or direct execution)"""
        self.logger.info("Starting speed test runner")

        scenarios = self.get_speed_test_scenarios()

        if not scenarios:
            self.logger.warning("No enabled speed test scenarios found in configuration")
            return

        for scenario in scenarios:
            self.run_speed_test_scenario(scenario)

        # Write all results
        self.write_results()

        self.logger.info("Speed test runner completed")

    def run_with_schedule(self):
        """
        Run tests with scheduling based on start_time field in configuration

        Reads start_time from each scenario's schedule configuration:
        - "immediate": Starts immediately
        - "+5m": Starts in 5 minutes
        - "+2h": Starts in 2 hours
        - "2024-01-15T10:30:00": Starts at specific datetime
        """
        self.logger.info("=" * 70)
        self.logger.info("Speed Test Runner with Scheduling")
        self.logger.info("=" * 70)

        scenarios = self.get_speed_test_scenarios()

        if not scenarios:
            self.logger.warning("No enabled speed test scenarios found in configuration")
            return

        # Process each scenario's schedule
        for scenario in scenarios:
            scenario_id = scenario.get('id', 'unknown')
            schedule_config = scenario.get('schedule', {})
            start_time = schedule_config.get('start_time', 'immediate')

            # Parse start time
            target_time = self.parse_start_time(start_time)
            delay = self.calculate_delay(target_time)

            if delay == 0:
                self.logger.info(f"Scenario '{scenario_id}': Starting immediately")
            else:
                self.logger.info(
                    f"Scenario '{scenario_id}': Scheduled to start at {target_time} "
                    f"(in {delay:.0f} seconds / {delay/60:.1f} minutes)"
                )

        # Calculate minimum delay (start tests when first scenario is ready)
        min_delay = float('inf')
        for scenario in scenarios:
            schedule_config = scenario.get('schedule', {})
            start_time = schedule_config.get('start_time', 'immediate')
            target_time = self.parse_start_time(start_time)
            delay = self.calculate_delay(target_time)
            min_delay = min(min_delay, delay)

        # Wait for the scheduled time
        if min_delay > 0:
            self.logger.info(f"\nWaiting {min_delay:.0f} seconds until first scheduled test...")
            self.logger.info(f"Press Ctrl+C to cancel\n")
            time.sleep(min_delay)

        # Run tests
        self.running = True
        self.run_tests_now()

    def run(self):
        """
        Main execution method - always respects start_time field from configuration

        Automatically handles scheduling based on start_time field:
        - "immediate": Starts immediately
        - "+5m": Starts in 5 minutes
        - "+2h": Starts in 2 hours
        - ISO datetime: Starts at specific time
        """
        self.run_with_schedule()


def main():
    """
    Main entry point

    The script always respects the start_time field from the configuration.

    Usage:
        # Use default config (./configurations/main.json)
        python new_speed_test.py

        # Use custom config file
        python new_speed_test.py --config path/to/config.json

    Examples:
        # Run with main.json (respects start_time field)
        python new_speed_test.py --config configurations/main.json

        # Run with custom config
        python new_speed_test.py --config configurations/test_scheduler_demo.json
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Speed Test Runner with iperf3 (always respects start_time field)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='./configurations/main.json',
        help='Path to configuration file (default: ./configurations/main.json)'
    )

    args = parser.parse_args()

    tester = SpeedTest(config_path=args.config)
    tester.run()


if __name__ == '__main__':
    main()
