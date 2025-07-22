import os
import sys
import subprocess
import time
import signal
import argparse
from typing import Dict, Any

# --- CPEM Configuration ---
BASE_DIR = os.getcwd() # Use current working directory
PID_DIR = os.path.join(BASE_DIR, ".cpem", "pids")
LOG_DIR = os.path.join(BASE_DIR, ".cpem", "logs")

SERVICES: Dict[str, Dict[str, Any]] = {
    "redis": {
        "command": [
            "redis-server", "--port", "6379", "--daemonize", "no", # Run in foreground for our manager
        ],
        "pid_file": f"{PID_DIR}/redis.pid",
        "log_file": f"{LOG_DIR}/redis.log",
        "cwd": "/",
    },
    "logical_engine": {
        "command": [f"{BASE_DIR}/rust_engine/target/release/logical_engine"],
        "pid_file": f"{PID_DIR}/logical_engine.pid",
        "log_file": f"{LOG_DIR}/logical_engine.log",
        "cwd": f"{BASE_DIR}/rust_engine",
    },
    "brain_api": {
        "command": ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"],
        "pid_file": f"{PID_DIR}/brain_api.pid",
        "log_file": f"{LOG_DIR}/brain_api.log",
        "cwd": f"{BASE_DIR}/python_app",
    },
}

# --- Core Functions ---

def up():
    print("CPEM: Starting all services...")
    os.makedirs(PID_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    rust_binary = SERVICES["logical_engine"]["command"][0]
    if not os.path.exists(rust_binary):
        print("CPEM: Rust binary not found. Compiling...")
        compile_proc = subprocess.run("cargo build --release", shell=True, cwd=SERVICES["logical_engine"]["cwd"], capture_output=True, text=True)
        if compile_proc.returncode != 0:
            print(f"CPEM ERROR: Failed to compile Rust engine.\n{compile_proc.stderr}")
            return
        print("CPEM: Rust engine compiled successfully.")

    for name, config in SERVICES.items():
        if os.path.exists(config["pid_file"]):
            print(f"CPEM: Service '{name}' appears to be running. Skipping.")
            continue
        print(f"CPEM: Launching service '{name}'...")
        try:
            log_file = open(config["log_file"], "w")
            process = subprocess.Popen(config["command"], stdout=log_file, stderr=subprocess.STDOUT, cwd=config["cwd"], start_new_session=True)
            with open(config["pid_file"], "w") as f:
                f.write(str(process.pid))
            print(f"CPEM: Service '{name}' started with PID {process.pid}.")
        except Exception as e:
            print(f"CPEM ERROR: Failed to start '{name}'. Error: {e}")
            down()
            return
    print("\nCPEM: All services launched.")

def down():
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
            os.kill(pid, signal.SIGTERM)
            time.sleep(1) # Give it a moment to die
            try: # Force kill if it's still alive
                os.kill(pid, 0)
                print(f"CPEM WARNING: Service '{name}' did not terminate gracefully. Sending SIGKILL.")
                os.kill(pid, signal.SIGKILL)
            except OSError: pass # Success
            os.remove(pid_file)
        except (FileNotFoundError, ProcessLookupError):
            if os.path.exists(pid_file): os.remove(pid_file)
        except Exception as e:
            print(f"CPEM ERROR: Failed to stop '{name}'. Error: {e}")
    print("\nCPEM: Shutdown complete.")

def status():
    print("--- AGI Service Status ---")
    print(f"{'SERVICE':<20} {'PID':<10} {'STATUS':<20}")
    print("-" * 52)
    for name, config in SERVICES.items():
        pid, current_status = "N/A", "Stopped"
        if os.path.exists(config["pid_file"]):
            try:
                with open(config["pid_file"], "r") as f:
                    pid_str = f.read().strip()
                    if pid_str:
                        pid = int(pid_str)
                        os.kill(pid, 0)
                        current_status = "Running"
            except (ProcessLookupError, ValueError):
                current_status = "Stopped (Stale PID)"
            except Exception as e:
                current_status = f"Error: {type(e).__name__}"
        print(f"{name:<20} {str(pid):<10} {current_status:<20}")
    print("-" * 52)

def logs(service_name, follow):
    """Tails the logs of a specific service."""
    if service_name not in SERVICES:
        print(f"CPEM ERROR: Service '{service_name}' not found.")
        return
    log_file = SERVICES[service_name]["log_file"]
    if not os.path.exists(log_file):
        print(f"Log file for '{service_name}' not found.")
        return
    
    if follow:
        print(f"--- Tailing logs for '{service_name}' (Ctrl+C to stop) ---")
        try:
            with open(log_file, "r") as f:
                # Go to the end of the file
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    sys.stdout.write(line)
                    sys.stdout.flush()
        except KeyboardInterrupt:
            print("\n--- Stopped tailing logs ---")
    else:
        with open(log_file, "r") as f:
            print(f.read())

def execute(service_name, command_to_run):
    """Executes a command in the context of a service."""
    if service_name not in SERVICES:
        print(f"CPEM ERROR: Service '{service_name}' not found.")
        return
        
    config = SERVICES[service_name]
    print(f"--- Executing '{' '.join(command_to_run)}' in '{service_name}' context ---")
    
    proc = subprocess.run(
        command_to_run,
        cwd=config["cwd"],
        capture_output=True, text=True
    )
    
    if proc.stdout:
        print("\n--- STDOUT ---")
        print(proc.stdout)
    if proc.stderr:
        print("\n--- STDERR ---")
        print(proc.stderr)
    
    print(f"--- Command finished with exit code {proc.returncode} ---")

# --- Main CLI Router ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CPEM: AGI Process & Environment Manager for Colab.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    up_parser = subparsers.add_parser("up", help="Start all AGI services.")
    down_parser = subparsers.add_parser("down", help="Stop all AGI services.")
    status_parser = subparsers.add_parser("status", help="Check the status of all services.")
    
    logs_parser = subparsers.add_parser("logs", help="View logs for a specific service.")
    logs_parser.add_argument("service_name", choices=SERVICES.keys(), help="The service to view logs for.")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output.")

    exec_parser = subparsers.add_parser("exec", help="Execute a command in a service's context.")
    exec_parser.add_argument("service_name", choices=SERVICES.keys(), help="The service context to run in.")
    exec_parser.add_argument("run_command", nargs=argparse.REMAINDER, help="The command to execute.")

    args = parser.parse_args()

    if args.command == "up":
        up()
    elif args.command == "down":
        down()
    elif args.command == "status":
        status()
    elif args.command == "logs":
        logs(args.service_name, args.follow)
    elif args.command == "exec":
        if not args.run_command:
            print("CPEM ERROR: 'exec' requires a command to run.")
        else:
            execute(args.service_name, args.run_command)