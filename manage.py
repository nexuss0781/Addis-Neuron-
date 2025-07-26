import os
import sys
import subprocess
import time
import signal
import argparse
from typing import Dict, Any

# --- CPEM Configuration ---
# Use the script's location to define the base directory for robustness
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CPEM_DIR = os.path.join(BASE_DIR, ".cpem")
PID_DIR = os.path.join(CPEM_DIR, "pids")
LOG_DIR = os.path.join(CPEM_DIR, "logs")
# Ensure the PATH includes Cargo's bin directory for all subprocesses
os.environ['PATH'] = "/root/.cargo/bin:" + os.environ.get('PATH', '')

SERVICES: Dict[str, Dict[str, Any]] = {
    "redis": {"command": ["redis-server", "--port", "6379", "--daemonize", "no"], "cwd": "/"},
    "logical_engine": {"command": [os.path.join(BASE_DIR, "rust_engine", "target", "release", "logical_engine")], "cwd": BASE_DIR},
    "brain_api": {"command": [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"], "cwd": os.path.join(BASE_DIR, "python_app")},
}
# Automatically add pid and log file paths to each service
for name in SERVICES:
    SERVICES[name]["pid_file"] = os.path.join(PID_DIR, f"{name}.pid")
    SERVICES[name]["log_file"] = os.path.join(LOG_DIR, f"{name}.log")


def bootstrap():
    """Prepares the environment by creating necessary data files and directories."""
    print("CPEM: Bootstrapping environment...")
    
    # Create the data directory the Rust engine needs to start.
    data_dir = os.path.join(BASE_DIR, "nlse_data")
    print(f"CPEM: Ensuring data directory exists at '{data_dir}'...")
    os.makedirs(data_dir, exist_ok=True)
    
    # Create the empty placeholder files the StorageManager loads.
    atoms_path = os.path.join(data_dir, "atoms.json")
    graph_path = os.path.join(data_dir, "graph.bin")

    if not os.path.exists(atoms_path):
        with open(atoms_path, "w") as f:
            f.write("[]")
        print("CPEM: Created empty 'atoms.json'.")
        
    if not os.path.exists(graph_path):
        with open(graph_path, "w") as f:
            pass # Just create the empty file
        print("CPEM: Created empty 'graph.bin'.")

    print("CPEM: Bootstrap complete.")


def up():
    """Starts all services as background processes and creates log files."""
    print("CPEM: Starting all services...")
    os.makedirs(PID_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    for name, config in SERVICES.items():
        if os.path.exists(config["pid_file"]):
            try:
                with open(config["pid_file"], 'r') as f: pid = int(f.read().strip())
                os.kill(pid, 0) # Check if process exists
                print(f"CPEM: Service '{name}' (PID: {pid}) appears to be running. Skipping.")
                continue
            except (IOError, ValueError, ProcessLookupError):
                print(f"CPEM: Found stale PID file for '{name}'. Removing.")
                os.remove(config["pid_file"])

        print(f"CPEM: Launching '{name}'... Log: {config['log_file']}")
        try:
            log_file = open(config["log_file"], "w")
            # `start_new_session=True` is critical for detaching from the script's lifecycle
            process = subprocess.Popen(config["command"], stdout=log_file, stderr=log_file, cwd=config["cwd"], start_new_session=True)
            with open(config["pid_file"], "w") as f:
                f.write(str(process.pid))
            print(f"CPEM: Service '{name}' started with PID {process.pid}.")
        except Exception as e:
            print(f"CPEM ERROR: Failed to start '{name}'. Error: {e}")
            down() # Attempt a cleanup on failure
            return
    print("\nCPEM: All services launched.")

def down():
    """Stops all running services by targeting their process groups."""
    print("CPEM: Shutting down all services...")
    for name in reversed(list(SERVICES.keys())):
        config = SERVICES[name]
        pid_file = config["pid_file"]
        if not os.path.exists(pid_file):
            continue
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            print(f"CPEM: Stopping service '{name}' (PID: {pid})...")
            # Kill the entire process group to ensure cleanup of child processes
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            time.sleep(1)
            os.remove(pid_file) # Clean up PID file after sending signal
        except (FileNotFoundError, ProcessLookupError, ValueError):
            # The process is already gone, just clean up the file
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception as e:
            print(f"CPEM ERROR: Failed to stop '{name}'. Error: {e}")
    print("\nCPEM: Shutdown complete.")

def status():
    """Checks and reports the status of each service."""
    print(f"{'SERVICE':<20} {'PID':<10} {'STATUS':<20}\n" + "-" * 52)
    for name, config in SERVICES.items():
        pid, current_status = "N/A", "Stopped"
        if os.path.exists(config["pid_file"]):
            try:
                with open(config["pid_file"], "r") as f:
                    pid_str = f.read().strip()
                    if pid_str:
                        pid = int(pid_str)
                        os.kill(pid, 0) # Check if process exists without sending a signal
                        current_status = "Running"
            except (ProcessLookupError, ValueError, IOError):
                current_status = "Stopped (Stale PID)"
            except Exception as e:
                current_status = f"Error: {type(e).__name__}"
        print(f"{name:<20} {str(pid):<10} {current_status:<20}")
    print("-" * 52)

def logs(service_name: str):
    """Prints the logs for a specific service."""
    log_file = SERVICES[service_name]["log_file"]
    print(f"--- [LOGS] {service_name.upper()} ---")
    print("=" * 40)
    if not os.path.exists(log_file):
        print(f"Log file not found at {log_file}.")
        return
    with open(log_file, "r") as f:
        content = f.read()
        if not content.strip():
            print("(Log file is empty)")
        else:
            print(content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CPEM: Colab Process Environment Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("bootstrap", help="Prepare the environment (create data files).")
    subparsers.add_parser("up", help="Start all services.")
    subparsers.add_parser("down", help="Stop all services.")
    subparsers.add_parser("status", help="Check the status of all services.")
    
    logs_parser = subparsers.add_parser("logs", help="Display logs for a service.")
    logs_parser.add_argument("service_name", choices=SERVICES.keys(), help="The service to display logs for.")
    
    args = parser.parse_args()
    
    # Simple dispatcher to call the correct function
    if args.command == "bootstrap":
        bootstrap()
    elif args.command == "up":
        up()
    elif args.command == "down":
        down()
    elif args.command == "status":
        status()
    elif args.command == "logs":
        logs(args.service_name)