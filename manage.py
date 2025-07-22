import os
import sys
import subprocess
import time
import signal
from typing import Dict, Any

# --- CPEM Configuration ---
# This dictionary is the heart of our process manager.
# It defines all the services needed to run the AGI.

# Define absolute paths within the Colab environment
BASE_DIR = "/content/project-agile-mind"
PID_DIR = "/content/pids"
LOG_DIR = "/content/logs"

SERVICES: Dict[str, Dict[str, Any]] = {
    "redis": {
        "command": [
            "redis-server",
            "--daemonize", "yes",
            "--port", "6379",
            "--pidfile", f"{PID_DIR}/redis.pid",
            "--logfile", f"{LOG_DIR}/redis.log",
        ],
        "pid_file": f"{PID_DIR}/redis.pid",
        "log_file": f"{LOG_DIR}/redis.log",
        "health_check": ["redis-cli", "-p", "6379", "ping"],
        "cwd": "/", # Working directory for the command
    },
    "logical_engine": {
        "command": [
            f"{BASE_DIR}/rust_engine/target/release/logical_engine"
        ],
        "pid_file": f"{PID_DIR}/logical_engine.pid",
        "log_file": f"{LOG_DIR}/logical_engine.log",
        "health_check": ["curl", "-sf", "http://localhost:8002/health"],
        "cwd": f"{BASE_DIR}/rust_engine",
    },
    "brain_api": {
        "command": [
            "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8001",
        ],
        "pid_file": f"{PID_DIR}/brain_api.pid",
        "log_file": f"{LOG_DIR}/brain_api.log",
        "health_check": ["curl", "-sf", "http://localhost:8001/health"],
        "cwd": f"{BASE_DIR}/python_app",
    },
    # Prometheus and Grafana are omitted for now as they are complex to set up
    # without Docker, but can be added later.
}

# --- Core Functions (to be implemented next) ---
def up():
    """
    Starts all defined services as background processes.
    """
    print("CPEM: Starting all services...")

    # 1. Ensure required directories exist
    os.makedirs(PID_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # 2. Pre-flight check: Compile Rust code if binary doesn't exist
    rust_binary = SERVICES["logical_engine"]["command"][0]
    if not os.path.exists(rust_binary):
        print("CPEM: Rust binary not found. Compiling...")
        compile_proc = subprocess.run(
            "cargo build --release",
            shell=True,
            cwd=SERVICES["logical_engine"]["cwd"],
            capture_output=True, text=True
        )
        if compile_proc.returncode != 0:
            print("CPEM ERROR: Failed to compile Rust engine.")
            print(compile_proc.stderr)
            return
        print("CPEM: Rust engine compiled successfully.")

    # 3. Iterate and launch each service
    for name, config in SERVICES.items():
        pid_file = config["pid_file"]
        
        # Check if the service is already running
        if os.path.exists(pid_file):
            print(f"CPEM: Service '{name}' appears to be already running (PID file exists). Skipping.")
            continue

        print(f"CPEM: Launching service '{name}'...")
        try:
            # Open the log file for writing
            with open(config["log_file"], "w") as log_file:
                # Launch the command as a new process
                process = subprocess.Popen(
                    config["command"],
                    stdout=log_file,
                    stderr=subprocess.STDOUT, # Redirect stderr to stdout
                    cwd=config["cwd"],
                    start_new_session=True # Detach from the current terminal
                )
            
            # Write the new process ID to its pid file
            with open(pid_file, "w") as f:
                f.write(str(process.pid))
            
            print(f"CPEM: Service '{name}' started with PID {process.pid}.")
            time.sleep(1) # Give a moment for the service to initialize

        except Exception as e:
            print(f"CPEM ERROR: Failed to start service '{name}'. Error: {e}")
            # Attempt to clean up if something went wrong
            down()
            return
    
    print("\nCPEM: All services launched.")

def down():
    """
    Stops all defined services by reading their PID files.
    """
    print("CPEM: Shutting down all services...")

    # Iterate in reverse order of startup
    for name in reversed(list(SERVICES.keys())):
        config = SERVICES[name]
        pid_file = config["pid_file"]
        
        if not os.path.exists(pid_file):
            print(f"CPEM: Service '{name}' is not running (no PID file).")
            continue

        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            
            print(f"CPEM: Stopping service '{name}' (PID: {pid})...")
            # Send a graceful termination signal
            os.kill(pid, signal.SIGTERM)

            # Wait a moment to see if it terminates
            time.sleep(1)

            # Check if the process is gone. If not, forcefully kill it.
            # This is a robust way to handle stubborn processes.
            try:
                os.kill(pid, 0) # This doesn't kill, just checks if the PID exists
                print(f"CPEM WARNING: Service '{name}' did not terminate gracefully. Sending SIGKILL.")
                os.kill(pid, signal.SIGKILL)
            except OSError:
                # This is the success case - the process is gone
                pass

            # Clean up the PID file
            os.remove(pid_file)
            print(f"CPEM: Service '{name}' stopped.")

        except FileNotFoundError:
            # This case is handled by the initial check, but is here for safety
            continue
        except ProcessLookupError:
            print(f"CPEM: Process for service '{name}' not found (stale PID file). Cleaning up.")
            os.remove(pid_file)
        except Exception as e:
            print(f"CPEM ERROR: Failed to stop service '{name}'. Error: {e}")

    print("\nCPEM: Shutdown complete.")

def status():
    """
    Checks and reports the status of all defined services.
    """
    print("--- AGI Service Status ---")
    print(f"{'SERVICE':<20} {'PID':<10} {'STATUS':<10}")
    print("-" * 42)

    for name, config in SERVICES.items():
        pid_file = config["pid_file"]
        pid = None
        current_status = "Stopped"

        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    pid_str = f.read().strip()
                    if pid_str:
                        pid = int(pid_str)
                
                # Check if the process actually exists
                # os.kill(pid, 0) will raise a ProcessLookupError if the PID is not running
                # but will do nothing if it is.
                os.kill(pid, 0)
                current_status = "Running"
            
            except (ProcessLookupError, ValueError):
                # The PID file is stale or corrupted.
                current_status = "Stopped (Stale PID)"
                pid = None # Clear PID as it's not valid
            except Exception as e:
                current_status = f"Error: {e}"
                pid = None
        
        pid_display = str(pid) if pid else "N/A"
        print(f"{name:<20} {pid_display:<10} {current_status:<10}")
    
    print("-" * 42)


# --- Main CLI Router (to be implemented later) ---
if __name__ == "__main__":
    print("CPEM: AGI Process & Environment Manager")
    # Argument parsing will be added in Phase B