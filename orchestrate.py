#!/usr/bin/env python3
"""
Docker Swarm Orchestration Script for LoadTest Framework

This script:
1. Reads main.json for configuration parameters
2. Initializes Docker Swarm and deploys test-container and db-container
3. Runs the speed test script inside the test-container
4. Copies results from the database to the configured reports directory
"""

import json
import subprocess
import time
import os
import csv
from pathlib import Path
from datetime import datetime

import docker
import psycopg2


def load_config(config_path: str = "./configurations/main.json") -> dict:
    """Load configuration from main.json"""
    with open(config_path, 'r') as f:
        return json.load(f)


def get_local_ip() -> str:
    """Get local IP address for swarm initialization"""
    result = subprocess.run(
        ["hostname", "-I"],
        capture_output=True,
        text=True
    )
    ips = result.stdout.strip().split()
    return ips[0] if ips else "127.0.0.1"


def init_swarm(client: docker.DockerClient) -> bool:
    """Initialize Docker Swarm if not already active"""
    try:
        info = client.info()
        if info.get('Swarm', {}).get('LocalNodeState') == 'active':
            print("Swarm already active")
            return True

        local_ip = get_local_ip()
        print(f"Initializing swarm with advertise address: {local_ip}")
        client.swarm.init(advertise_addr=local_ip)
        print("Swarm initialized successfully")
        return True
    except docker.errors.APIError as e:
        print(f"Error initializing swarm: {e}")
        return False


def wait_for_service(client: docker.DockerClient, service_name: str, timeout: int = 120) -> bool:
    """Wait for a service to be running"""
    print(f"Waiting for service {service_name} to be ready...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            services = client.services.list(filters={'name': service_name})
            if services:
                service = services[0]
                tasks = service.tasks()
                for task in tasks:
                    if task.get('Status', {}).get('State') == 'running':
                        print(f"Service {service_name} is running")
                        return True
        except Exception as e:
            print(f"Error checking service: {e}")

        time.sleep(2)

    print(f"Timeout waiting for service {service_name}")
    return False


def wait_for_database(host: str, port: int, timeout: int = 60) -> bool:
    """Wait for PostgreSQL database to be ready"""
    print("Waiting for database to be ready...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database='speedtest',
                user='postgres',
                password='postgres',
                connect_timeout=5
            )
            conn.close()
            print("Database is ready")
            return True
        except psycopg2.OperationalError:
            time.sleep(2)

    print("Timeout waiting for database")
    return False


def deploy_stack(client: docker.DockerClient, config: dict) -> bool:
    """Deploy the Docker Swarm stack with test and db containers"""

    # Create overlay network
    network_name = "loadtest_network"
    try:
        networks = client.networks.list(names=[network_name])
        if not networks:
            print(f"Creating overlay network: {network_name}")
            client.networks.create(
                network_name,
                driver="overlay",
                attachable=True
            )
        else:
            print(f"Network {network_name} already exists")
    except Exception as e:
        print(f"Error creating network: {e}")
        return False

    # Deploy db-container service
    db_service_name = "loadtest_db"
    try:
        existing = client.services.list(filters={'name': db_service_name})
        if existing:
            print(f"Removing existing service: {db_service_name}")
            existing[0].remove()
            time.sleep(5)

        print(f"Creating service: {db_service_name}")
        client.services.create(
            image="db-container",
            name=db_service_name,
            env=[
                "POSTGRES_DB=speedtest",
                "POSTGRES_USER=postgres",
                "POSTGRES_PASSWORD=postgres"
            ],
            networks=[network_name],
            endpoint_spec=docker.types.EndpointSpec(
                ports={5432: (5432, 'tcp')}
            ),
            mode=docker.types.ServiceMode('replicated', replicas=1)
        )
    except Exception as e:
        print(f"Error creating db service: {e}")
        return False

    # Wait for database service and connection
    if not wait_for_service(client, db_service_name):
        return False

    if not wait_for_database('localhost', 5432):
        return False

    return True


def run_speed_test(client: docker.DockerClient, config: dict) -> bool:
    """Run the speed test inside test-container with volume mounts"""

    network_name = "loadtest_network"
    project_root = Path(__file__).parent.resolve()

    command = [
        "python3",
        "/app/src/test_protocols/iperf/new_speed_test.py",
        "--config", "/app/configurations/main.json"
    ]

    print(f"Running test container...")
    print(f"Project root: {project_root}")
    print(f"Command: {' '.join(command)}")

    try:
        container = client.containers.run(
            image="test-container",
            command=command,
            environment={
                "DB_HOST": "loadtest_db",
                "DB_PORT": "5432",
                "DB_NAME": "speedtest",
                "DB_USER": "postgres",
                "DB_PASSWORD": "postgres"
            },
            volumes={
                str(project_root / "src"): {"bind": "/app/src", "mode": "ro"},
                str(project_root / "configurations"): {"bind": "/app/configurations", "mode": "ro"},
                str(project_root / "results"): {"bind": "/app/results", "mode": "rw"}
            },
            network=network_name,
            remove=True,
            detach=False,
            stdout=True,
            stderr=True
        )

        # container.run with detach=False returns bytes output
        if isinstance(container, bytes):
            output = container.decode('utf-8')
            print("Test output:")
            print(output)

        print("Test completed successfully")
        return True

    except docker.errors.ContainerError as e:
        print(f"Test container failed with exit code {e.exit_status}")
        if e.stderr:
            print(f"Error: {e.stderr.decode('utf-8')}")
        return False
    except Exception as e:
        print(f"Error running test: {e}")
        return False


def export_results(config: dict) -> bool:
    """Export results from database to the configured reports directory"""

    report_path = config.get('global_settings', {}).get('report_path', './results/speed_test/')
    report_dir = Path(report_path)
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"Exporting results to: {report_dir}")

    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='speedtest',
            user='postgres',
            password='postgres'
        )
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Export test results
        cursor.execute("SELECT * FROM speed_test.test_results ORDER BY timestamp")
        results = cursor.fetchall()

        if results:
            columns = [desc[0] for desc in cursor.description]
            results_file = report_dir / f"test_results_{timestamp}.csv"

            with open(results_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(results)

            print(f"Exported {len(results)} test results to {results_file}")
        else:
            print("No test results found in database")

        # Export evaluations
        cursor.execute("SELECT * FROM speed_test.test_evaluations ORDER BY timestamp")
        evaluations = cursor.fetchall()

        if evaluations:
            columns = [desc[0] for desc in cursor.description]
            eval_file = report_dir / f"evaluations_{timestamp}.csv"

            with open(eval_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(evaluations)

            print(f"Exported {len(evaluations)} evaluations to {eval_file}")
        else:
            print("No evaluations found in database")

        # Export summary views
        cursor.execute("SELECT * FROM speed_test.latest_test_summary")
        summary = cursor.fetchall()

        if summary:
            columns = [desc[0] for desc in cursor.description]
            summary_file = report_dir / f"summary_{timestamp}.csv"

            with open(summary_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(summary)

            print(f"Exported summary to {summary_file}")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"Error exporting results: {e}")
        return False


def cleanup(client: docker.DockerClient):
    """Clean up services after completion"""
    print("Cleaning up services...")

    # Only db runs as a service now, test runs as a container
    try:
        services = client.services.list(filters={'name': 'loadtest_db'})
        for service in services:
            print("Removing service: loadtest_db")
            service.remove()
    except Exception as e:
        print(f"Error removing loadtest_db: {e}")

    time.sleep(3)
    print("Cleanup complete")


def main():
    """Main orchestration entry point"""
    print("=" * 60)
    print("LoadTest Docker Swarm Orchestration")
    print("=" * 60)

    # Load configuration
    print("\n[1/5] Loading configuration...")
    config = load_config()
    report_path = config.get('global_settings', {}).get('report_path', './results/speed_test/')
    print(f"Report path: {report_path}")

    # Ensure results directory exists
    Path(report_path).mkdir(parents=True, exist_ok=True)
    Path("./results").mkdir(parents=True, exist_ok=True)

    # Get enabled scenarios
    scenarios = [s for s in config.get('scenarios', [])
                 if s.get('enabled', False) and s.get('protocol') == 'speed_test']
    print(f"Enabled speed test scenarios: {len(scenarios)}")
    for s in scenarios:
        print(f"  - {s.get('id')}: {s.get('description', 'No description')}")

    # Initialize Docker client
    print("\n[2/5] Initializing Docker...")
    client = docker.from_env()

    # Initialize swarm
    if not init_swarm(client):
        print("Failed to initialize swarm")
        return 1

    # Deploy stack
    print("\n[3/5] Deploying services...")
    if not deploy_stack(client, config):
        print("Failed to deploy stack")
        cleanup(client)
        return 1

    # Run speed test
    print("\n[4/5] Running speed test...")
    test_success = run_speed_test(client, config)

    # Export results
    print("\n[5/5] Exporting results...")
    export_success = export_results(config)

    # Cleanup
    print("\nCleaning up...")
    cleanup(client)

    # Summary
    print("\n" + "=" * 60)
    print("Orchestration Complete")
    print("=" * 60)
    print(f"Test execution: {'SUCCESS' if test_success else 'FAILED'}")
    print(f"Results export: {'SUCCESS' if export_success else 'FAILED'}")
    print(f"Reports saved to: {report_path}")

    return 0 if (test_success and export_success) else 1


if __name__ == '__main__':
    exit(main())
