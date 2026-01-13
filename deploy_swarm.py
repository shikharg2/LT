#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import socket

def run_command(cmd, description=""):
    """Run shell command and return output"""
    print(f"\n{description}")
    print(f"Command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False, result.stderr
    print(result.stdout)
    return True, result.stdout

def get_local_ip():
    """Get the local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

def init_swarm():
    """Initialize Docker Swarm if not already initialized"""
    print("\n=== Checking Docker Swarm Status ===")
    result = subprocess.run("docker info --format '{{.Swarm.LocalNodeState}}'",
                          shell=True, capture_output=True, text=True)

    if result.stdout.strip() == 'active':
        print("Docker Swarm already initialized")
        return True

    local_ip = get_local_ip()
    print(f"Detected local IP: {local_ip}")

    success, output = run_command(
        f"docker swarm init --advertise-addr {local_ip}",
        "Initializing Docker Swarm with advertise address"
    )
    return success

def deploy_stack():
    """Deploy Docker stack"""
    print("\n=== Deploying Docker Stack ===")

    success, _ = run_command(
        "docker stack deploy -c docker-compose.yml loadtest",
        "Deploying loadtest stack"
    )
    return success

def check_stack_status():
    """Check status of deployed stack"""
    print("\n=== Checking Stack Status ===")
    run_command("docker stack services loadtest", "Stack services status")
    time.sleep(2)
    run_command("docker stack ps loadtest", "Stack tasks status")

def remove_stack():
    """Remove Docker stack"""
    print("\n=== Removing Docker Stack ===")
    success, _ = run_command(
        "docker stack rm loadtest",
        "Removing loadtest stack"
    )
    if success:
        print("\nWaiting for containers to be removed...")
        time.sleep(5)
    return success

def leave_swarm():
    """Leave Docker Swarm"""
    print("\n=== Leaving Docker Swarm ===")
    success, _ = run_command(
        "docker swarm leave --force",
        "Leaving Docker Swarm"
    )
    return success

def main():
    """Main deployment workflow"""
    print("=" * 70)
    print("Docker Swarm LoadTest Deployment")
    print("=" * 70)

    if len(sys.argv) > 1:
        if sys.argv[1] == "down":
            remove_stack()
            return
        elif sys.argv[1] == "leave":
            remove_stack()
            leave_swarm()
            return

    if not init_swarm():
        print("Failed to initialize Docker Swarm")
        return

    if not deploy_stack():
        print("Failed to deploy stack")
        return

    print("\n=== Waiting for services to start ===")
    time.sleep(10)

    check_stack_status()

    print("\n=== Deployment Complete ===")
    print("\nTo check logs:")
    print("  docker service logs loadtest_test_container")
    print("  docker service logs loadtest_db_container")
    print("\nTo fetch results from database to localhost:")
    print("  python3 fetch_results.py")
    print("  python3 fetch_results.py --scenario speed_test_public_server")
    print("\nTo remove the stack:")
    print("  python3 deploy_swarm.py down")
    print("\nTo remove stack and leave swarm:")
    print("  python3 deploy_swarm.py leave")

if __name__ == "__main__":
    main()
