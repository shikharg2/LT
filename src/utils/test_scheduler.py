#!/usr/bin/env python3
"""
Test Scheduler using Python schedule library
Provides flexible scheduling with human-readable time specifications
"""

import json
import logging
import sys
import time
import signal
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import importlib.util
import schedule


class SchedulerError(Exception):
    """Custom exception for scheduler errors"""
    pass


class TestScheduler:
    """
    Flexible test scheduler using Python schedule library

    Supports multiple scheduling patterns:
    - Every N seconds/minutes/hours/days/weeks
    - At specific times (e.g., "10:30", "09:00")
    - On specific days (Monday, Tuesday, etc.)
    - One-time immediate execution
    - Recurring with limits

    Schedule configuration examples:
        "schedule": {
            "mode": "every",
            "interval": 10,
            "unit": "minutes"
        }

        "schedule": {
            "mode": "daily",
            "time": "09:30"
        }

        "schedule": {
            "mode": "weekly",
            "day": "monday",
            "time": "10:00"
        }

        "schedule": {
            "mode": "hourly",
            "minute": 30
        }
    """

    def __init__(self, config_path: str = "./configurations/main.json"):
        """
        Initialize the test scheduler

        Args:
            config_path: Path to the main configuration file
        """
        self.config_path = config_path
        self.config = self.load_config()
        self.setup_logging()
        self.jobs: List[Dict] = []
        self.running = False
        self.threads: List[threading.Thread] = []
        self.run_counts: Dict[str, int] = {}

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

        # Create logs directory
        log_dir = Path('./logs')
        log_dir.mkdir(parents=True, exist_ok=True)

        # Configure logging with both file and console handlers
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'test_scheduler.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)

    def parse_schedule_config(self) -> List[Dict]:
        """
        Parse schedule configurations from main.json

        Supports multiple schedule modes:
        - once: Run immediately once
        - recurring: Run N times with interval
        - every: Run every N units (seconds/minutes/hours/days)
        - daily: Run daily at specific time
        - weekly: Run weekly on specific day at specific time
        - hourly: Run hourly at specific minute
        - custom: Advanced scheduling with schedule library syntax

        Returns:
            List of job configurations
        """
        jobs = []

        for scenario in self.config.get('scenarios', []):
            if not scenario.get('enabled', False):
                continue

            schedule_config = scenario.get('schedule', {})
            mode = schedule_config.get('mode', 'once')

            # Skip cron mode (handled by cron_scheduler)
            if mode == 'cron':
                continue

            job = {
                'scenario': scenario,
                'schedule_config': schedule_config,
                'mode': mode,
                'next_run': None,
                'last_run': None,
                'run_count': 0,
                'max_runs': None,
                'schedule_job': None
            }

            jobs.append(job)
            self.logger.info(
                f"Registered job for scenario '{scenario.get('id')}' with mode: {mode}"
            )

        return jobs

    def create_schedule(self, job: Dict) -> bool:
        """
        Create a schedule for a job based on its configuration

        Args:
            job: Job configuration dictionary

        Returns:
            True if schedule created successfully, False otherwise
        """
        scenario_id = job['scenario'].get('id')
        schedule_config = job['schedule_config']
        mode = job['mode']

        try:
            if mode == 'once':
                # Run immediately once
                job['max_runs'] = 1
                # Schedule to run as soon as possible
                job['schedule_job'] = schedule.every(1).seconds.do(
                    self.run_test_wrapper, job
                )
                self.logger.info(f"Scheduled '{scenario_id}' to run once immediately")

            elif mode == 'recurring':
                # Run N times with interval
                interval = int(schedule_config.get('recurring_interval', 60))
                times = int(schedule_config.get('recurring_times', 1))
                job['max_runs'] = times

                job['schedule_job'] = schedule.every(interval).minutes.do(
                    self.run_test_wrapper, job
                )
                self.logger.info(
                    f"Scheduled '{scenario_id}' to run {times} times every {interval} minutes"
                )

            elif mode == 'every':
                # Run every N units
                interval = int(schedule_config.get('interval', 1))
                unit = schedule_config.get('unit', 'minutes').lower()
                max_runs = schedule_config.get('max_runs')

                if max_runs:
                    job['max_runs'] = int(max_runs)

                # Map unit to schedule function
                if unit in ['second', 'seconds']:
                    job['schedule_job'] = schedule.every(interval).seconds.do(
                        self.run_test_wrapper, job
                    )
                elif unit in ['minute', 'minutes']:
                    job['schedule_job'] = schedule.every(interval).minutes.do(
                        self.run_test_wrapper, job
                    )
                elif unit in ['hour', 'hours']:
                    job['schedule_job'] = schedule.every(interval).hours.do(
                        self.run_test_wrapper, job
                    )
                elif unit in ['day', 'days']:
                    job['schedule_job'] = schedule.every(interval).days.do(
                        self.run_test_wrapper, job
                    )
                elif unit in ['week', 'weeks']:
                    job['schedule_job'] = schedule.every(interval).weeks.do(
                        self.run_test_wrapper, job
                    )
                else:
                    self.logger.error(f"Unknown unit: {unit}")
                    return False

                self.logger.info(
                    f"Scheduled '{scenario_id}' to run every {interval} {unit}"
                )

            elif mode == 'daily':
                # Run daily at specific time
                time_str = schedule_config.get('time', '09:00')
                max_runs = schedule_config.get('max_runs')

                if max_runs:
                    job['max_runs'] = int(max_runs)

                job['schedule_job'] = schedule.every().day.at(time_str).do(
                    self.run_test_wrapper, job
                )
                self.logger.info(
                    f"Scheduled '{scenario_id}' to run daily at {time_str}"
                )

            elif mode == 'weekly':
                # Run weekly on specific day at specific time
                day = schedule_config.get('day', 'monday').lower()
                time_str = schedule_config.get('time', '09:00')
                max_runs = schedule_config.get('max_runs')

                if max_runs:
                    job['max_runs'] = int(max_runs)

                # Map day names to schedule functions
                day_map = {
                    'monday': schedule.every().monday,
                    'tuesday': schedule.every().tuesday,
                    'wednesday': schedule.every().wednesday,
                    'thursday': schedule.every().thursday,
                    'friday': schedule.every().friday,
                    'saturday': schedule.every().saturday,
                    'sunday': schedule.every().sunday
                }

                if day not in day_map:
                    self.logger.error(f"Unknown day: {day}")
                    return False

                job['schedule_job'] = day_map[day].at(time_str).do(
                    self.run_test_wrapper, job
                )
                self.logger.info(
                    f"Scheduled '{scenario_id}' to run every {day} at {time_str}"
                )

            elif mode == 'hourly':
                # Run hourly at specific minute
                minute = schedule_config.get('minute', 0)
                max_runs = schedule_config.get('max_runs')

                if max_runs:
                    job['max_runs'] = int(max_runs)

                minute_str = f":{minute:02d}"
                job['schedule_job'] = schedule.every().hour.at(minute_str).do(
                    self.run_test_wrapper, job
                )
                self.logger.info(
                    f"Scheduled '{scenario_id}' to run hourly at minute {minute}"
                )

            elif mode == 'custom':
                # Custom schedule using schedule library syntax
                # Example: {"mode": "custom", "schedule": "every().day.at('10:30').do(job)"}
                self.logger.warning(
                    f"Custom mode not yet implemented for '{scenario_id}'"
                )
                return False

            else:
                self.logger.error(f"Unknown schedule mode: {mode}")
                return False

            return True

        except Exception as e:
            self.logger.error(
                f"Error creating schedule for '{scenario_id}': {e}",
                exc_info=True
            )
            return False

    def run_test_wrapper(self, job: Dict):
        """
        Wrapper function to run a test and track execution

        Args:
            job: Job configuration dictionary
        """
        scenario = job['scenario']
        scenario_id = scenario.get('id')

        # Update run tracking
        job['run_count'] += 1
        job['last_run'] = datetime.now()

        self.logger.info(
            f"Executing test for scenario: {scenario_id} "
            f"(run {job['run_count']}/{job['max_runs'] or 'unlimited'})"
        )

        try:
            # Execute the test
            success = self.run_test(scenario)

            if success:
                self.logger.info(
                    f"Test completed successfully for scenario: {scenario_id}"
                )
            else:
                self.logger.error(f"Test failed for scenario: {scenario_id}")

        except Exception as e:
            self.logger.error(
                f"Error executing test for scenario {scenario_id}: {e}",
                exc_info=True
            )

        # Check if we've reached max runs
        if job['max_runs'] and job['run_count'] >= job['max_runs']:
            self.logger.info(
                f"Reached max runs ({job['max_runs']}) for scenario: {scenario_id}"
            )
            # Cancel the scheduled job
            if job['schedule_job']:
                schedule.cancel_job(job['schedule_job'])
                self.logger.info(f"Cancelled schedule for scenario: {scenario_id}")

    def run_test(self, scenario: Dict) -> bool:
        """
        Execute a test scenario

        Args:
            scenario: Scenario configuration

        Returns:
            True if test executed successfully, False otherwise
        """
        scenario_id = scenario.get('id', 'unknown')
        protocol = scenario.get('protocol', 'unknown')

        self.logger.info(
            f"Starting test execution for scenario: {scenario_id} (protocol: {protocol})"
        )

        try:
            # Determine which test protocol to run
            if protocol == 'speed_test':
                return self.run_speed_test(scenario)
            elif protocol == 'voip_test':
                return self.run_voip_test(scenario)
            else:
                self.logger.error(f"Unknown protocol: {protocol}")
                return False

        except Exception as e:
            self.logger.error(
                f"Error executing test for scenario {scenario_id}: {e}",
                exc_info=True
            )
            return False

    def run_speed_test(self, scenario: Dict) -> bool:
        """
        Run speed test using the speed_test module

        Args:
            scenario: Scenario configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            # Import the speed test module
            spec = importlib.util.spec_from_file_location(
                "speed_test",
                "./src/test_protocols/iperf/speed_test.py"
            )
            speed_test_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(speed_test_module)

            # Create a temporary config with only this scenario
            # Override schedule to run once
            scenario_copy = scenario.copy()
            scenario_copy['schedule'] = {
                'mode': 'once',
                'duration': scenario.get('schedule', {}).get('duration', 10)
            }

            temp_config = {
                'global_settings': self.config.get('global_settings', {}),
                'scenarios': [scenario_copy]
            }

            # Create temporary config file
            temp_config_path = Path('./configurations/temp_scheduler_config.json')
            temp_config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(temp_config_path, 'w') as f:
                json.dump(temp_config, f, indent=2)

            # Run the test
            tester = speed_test_module.SpeedTest(str(temp_config_path))
            tester.run()

            # Clean up temporary config
            if temp_config_path.exists():
                temp_config_path.unlink()

            self.logger.info(
                f"Speed test completed successfully for scenario: {scenario.get('id')}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error running speed test: {e}", exc_info=True)
            return False

    def run_voip_test(self, scenario: Dict) -> bool:
        """
        Run VoIP test

        Args:
            scenario: Scenario configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            scenario_id = scenario.get('id')
            self.logger.info(f"VoIP test execution for scenario: {scenario_id}")

            # Placeholder for VoIP test execution
            self.logger.warning("VoIP test execution not yet fully implemented")

            return True

        except Exception as e:
            self.logger.error(f"Error running VoIP test: {e}", exc_info=True)
            return False

    def start(self):
        """Start the test scheduler"""
        self.logger.info("Starting Test Scheduler...")
        self.logger.info(f"Configuration: {self.config_path}")

        # Parse schedule configurations
        self.jobs = self.parse_schedule_config()

        if not self.jobs:
            self.logger.warning("No schedulable jobs found in configuration")
            return

        # Create schedules for all jobs
        scheduled_count = 0
        for job in self.jobs:
            if self.create_schedule(job):
                scheduled_count += 1

        if scheduled_count == 0:
            self.logger.error("Failed to create any schedules")
            return

        self.logger.info(
            f"Test Scheduler started with {scheduled_count}/{len(self.jobs)} jobs scheduled"
        )

        self.running = True

        # Print initial status
        self.print_status()

        # Main scheduling loop
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)

                # Check if all jobs are completed
                if all(
                    job['max_runs'] and job['run_count'] >= job['max_runs']
                    for job in self.jobs
                ):
                    self.logger.info("All scheduled jobs completed")
                    break

        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            self.stop()

    def stop(self):
        """Stop the test scheduler gracefully"""
        self.logger.info("Stopping Test Scheduler...")
        self.running = False

        # Clear all scheduled jobs
        schedule.clear()

        self.logger.info("Test Scheduler stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current scheduler status

        Returns:
            Dictionary with scheduler status information
        """
        job_status = []

        for job in self.jobs:
            scenario_id = job['scenario'].get('id')

            # Get next run time from schedule
            next_run = None
            if job['schedule_job'] and hasattr(job['schedule_job'], 'next_run'):
                next_run = job['schedule_job'].next_run

            job_status.append({
                'scenario_id': scenario_id,
                'mode': job['mode'],
                'run_count': job['run_count'],
                'max_runs': job['max_runs'],
                'last_run': job['last_run'].isoformat() if job['last_run'] else None,
                'next_run': next_run.isoformat() if next_run else None,
                'status': 'completed' if (job['max_runs'] and job['run_count'] >= job['max_runs']) else 'active'
            })

        return {
            'running': self.running,
            'total_jobs': len(self.jobs),
            'active_jobs': sum(1 for j in job_status if j['status'] == 'active'),
            'completed_jobs': sum(1 for j in job_status if j['status'] == 'completed'),
            'jobs': job_status
        }

    def print_status(self):
        """Print current scheduler status to console"""
        status = self.get_status()

        print("\n" + "=" * 80)
        print("TEST SCHEDULER STATUS")
        print("=" * 80)
        print(f"Status: {'RUNNING' if status['running'] else 'STOPPED'}")
        print(f"Total Jobs: {status['total_jobs']}")
        print(f"Active Jobs: {status['active_jobs']}")
        print(f"Completed Jobs: {status['completed_jobs']}")
        print("\n" + "-" * 80)
        print(f"{'Scenario ID':<35} {'Mode':<12} {'Runs':<15} {'Status':<10}")
        print("-" * 80)

        for job in status['jobs']:
            runs = f"{job['run_count']}/{job['max_runs'] or '∞'}"
            print(
                f"{job['scenario_id']:<35} {job['mode']:<12} {runs:<15} {job['status']:<10}"
            )

        print("=" * 80 + "\n")


def main():
    """Main entry point for the test scheduler"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Test Scheduler using Python schedule library'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='./configurations/main.json',
        help='Path to configuration file (default: ./configurations/main.json)'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show scheduler status and exit'
    )

    args = parser.parse_args()

    scheduler = TestScheduler(config_path=args.config)

    if args.status:
        scheduler.print_status()
    else:
        print("\nStarting Test Scheduler...")
        print("Press Ctrl+C to stop\n")
        scheduler.start()


if __name__ == '__main__':
    main()
