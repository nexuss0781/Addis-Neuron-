# manage.py

import os
import sys
import subprocess
import time
import signal
import argparse
from typing import Dict, Any

# Ensure Cargo's bin directory is in PATH for subprocesses
os.environ['PATH'] += ":" + os.path.join(os.path.expanduser("~"), ".cargo", "bin")

# --- CPEM Configuration ---
BASE_DIR = "/content/project-agile-mind"
CPEM_DIR = os.path.join(BASE_DIR, ".cpem")
PID_DIR = os.path.join(CPEM_DIR, "pids")
LOG_DIR = os.path.join(CPEM_DIR, "logs")

SERVICES: Dict[str, Dict[str, Any]] = {
    "redis": {
        "command": ["redis-server", "--port", "6379", "--daemonize", "no"],
        "pid_file": os.path.join(PID_DIR, "redis.pid"),
        "log_file": os.path.join(LOG_DIR, "redis.log"),
        "cwd": "/",
    },
    "logical_engine": {
        "command": [os.path.join(BASE_DIR, "rust_engine", "target", "release", "logical_engine")],
        "pid_file": os.path.join(PID_DIR, "logical_engine.pid"),
        "log_file": os.path.join(LOG_DIR, "logical_engine.log"),
        "cwd": os.path.join(BASE_DIR, "rust_engine"),
    },
    "brain_api": {
        "command": [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"],
        "pid_file": os.path.join(PID_DIR, "brain_api.pid"),
        "log_file": os.path.join(LOG_DIR, "brain_api.log"),
        "cwd": os.path.join(BASE_DIR, "python_app"),
    },
}


# --- Core Functions ---

def up():
    """
    Starts all defined services as background processes using a robust
    double-fork or detached Popen call suitable for Colab.
    """
    print("CPEM: Starting all services...")
    os.makedirs(PID_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    rust_binary_path = SERVICES["logical_engine"]["command"][0]
    if not os.path.exists(rust_binary_path):
        print("CPEM: Rust binary not found. Compiling...")
        compile_proc = subprocess.run(
            "cargo build --release", shell=True, cwd=SERVICES["logical_engine"]["cwd"],
            capture_output=True, text=True
        )
        if compile_proc.returncode != 0:
            print(f"CPEM ERROR: Failed to compile Rust engine.\n{compile_proc.stderr}")
            return
        print("CPEM: Rust engine compiled successfully.")

    for name, config in SERVICES.items():
        if os.path.exists(config["pid_file"]):
            print(f"CPEM: Service '{name}' appears to be already running. Skipping.")
            continue

        print(f"CPEM: Launching service '{name}'...")
        try:
            # --- CORRECTED PROCESS LAUNCH ---
            # We open the log file handle here...
            log_file_handle = open(config["log_file"], "w")
            
            # ...and pass it to Popen. The `start_new_session=True` is the key
            # to detaching it from the current script's process group.
            process = subprocess.Popen(
                config["command"],
                stdout=log_file_handle,
                stderr=log_file_handle, # Redirect both to the same handle
                cwd=config["cwd"],
                start_new_session=True 
            )
            
            # After launching, we can close our script's reference to the handle.
            # The child process still holds a valid reference to the open file.
            log_file_handle.close()
            
            with open(config["pid_file"], "w") as f:
                f.write(str(process.pid))

            print(f"CPEM: Service '{name}' started with PID {process.pid}.")
            time.sleep(1)

        except Exception as e:
            print(f"CPEM ERROR: Failed to start service '{name}'. Error: {e}")
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
            time.sleep(1)
            try:
                os.kill(pid, 0)
                print(f"CPEM WARNING: Service '{name}' did not terminate gracefully. Sending SIGKILL.")
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            os.remove(pid_file)
            print(f"CPEM: Service '{name}' stopped.")
        except (FileNotFoundError, ProcessLookupError):
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception as e:
            print(f"CPEM ERROR: Failed to stop service '{name}'. Error: {e}")
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
    if service_name not in SERVICES:
        print(f"CPEM ERROR: Service '{service_name}' not found.")
        return
    log_file = SERVICES[service_name]["log_file"]
    if not os.path.exists(log_file):
        print(f"Log file for '{service_name}' not found at {log_file}.")
        return

    if follow:
        print(f"--- Tailing logs for '{service_name}' (Ctrl+C to stop) ---")
        try:
            with open(log_file, "r") as f:
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
        print(f"\n--- STDOUT ---\n{proc.stdout}")
    if proc.stderr:
        print(f"\n--- STDERR ---\n{proc.stderr}")
    print(f"--- Command finished with exit code {proc.returncode} ---")


def bootstrap():
    print("CPEM: Running bootstrap setup...")
    print("1. Installing system dependencies...")
    subprocess.run("apt-get update -qq && apt-get install -y redis-server build-essential > /dev/null", shell=True, check=True)
    print("2. Installing Python packages...")
    subprocess.run(f"{sys.executable} -m pip install -r python_app/requirements.txt -q", shell=True, check=True)
    print("3. Setting up Rust toolchain (this may take a while)...")
    rustup_init_script = "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
    subprocess.run(rustup_init_script, shell=True, env={**os.environ, "RUSTUP_HOME": "/root/.rustup", "CARGO_HOME": "/root/.cargo"}, check=True)
    print("Rust toolchain is ready.")
    print("CPEM: Bootstrap complete.")


def fetch_memory():
    print("CPEM: Fetching latest memory from Git...")
    nlse_data_path = os.path.join(BASE_DIR, "nlse_data")
    os.makedirs(nlse_data_path, exist_ok=True)

    subprocess.run('git config user.email "colab_user@example.com"', shell=True, cwd=BASE_DIR, check=True)
    subprocess.run('git config user.name "Colab AGI User"', shell=True, cwd=BASE_DIR, check=True)

    result = subprocess.run('git pull --rebase', shell=True, cwd=BASE_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        if "not a git repository" in result.stderr.lower() or "no such file or directory" in result.stderr.lower():
            print("CPEM INFO: Not a git repository or no existing clone. Skipping pull.")
        else:
            print(f"CPEM WARNING: Git pull failed:\n{result.stderr}")
    else:
        print("CPEM: Memory fetch complete. Repository updated.")


def persist_memory(commit_message):
    print("CPEM: Persisting memory to Git...")
    subprocess.run('git config user.email "colab_user@example.com"', shell=True, cwd=BASE_DIR, check=True)
    subprocess.run('git config user.name "Colab AGI User"', shell=True, cwd=BASE_DIR, check=True)

    add_result = subprocess.run(f'git add {os.path.join(BASE_DIR, "nlse_data")}', shell=True, cwd=BASE_DIR, capture_output=True, text=True, check=False)
    if add_result.returncode != 0:
        print(f"CPEM WARNING: Git add failed:\n{add_result.stderr}")

    commit_result = subprocess.run(f'git commit -m "{commit_message}"', shell=True, cwd=BASE_DIR, capture_output=True, text=True, check=False)
    if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stdout:
        print(f"CPEM WARNING: Git commit failed:\n{commit_result.stderr}")
        return

    push_cmd = 'git push'
    push_result = subprocess.run(push_cmd, shell=True, cwd=BASE_DIR, capture_output=True, text=True)
    if push_result.returncode != 0:
        print(f"CPEM ERROR: Git push failed:\n{push_result.stderr}\n{push_result.stdout}")
        print("CPEM HINT: For private repos, ensure you are authenticated (e.g., using a PAT with the clone URL).")
        return
    print("CPEM: Memory persistence complete. Changes pushed to GitHub.")


# --- Main CLI Router ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CPEM: AGI Process & Environment Manager for Colab.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    bootstrap_parser = subparsers.add_parser("bootstrap", help="Perform one-time environment setup (apt, pip, rustup).")
    fetch_memory_parser = subparsers.add_parser("fetch-memory", help="Pull latest memory files from Git.")
    persist_memory_parser = subparsers.add_parser("persist-memory", help="Commit and push memory files to Git.")
    persist_memory_parser.add_argument("message", type=str, help="Commit message for memory persistence.")

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

    os.environ["REPO_URL"] = os.environ.get("REPO_URL", "https://github.com/nexuss0781/Addis-Neuron-.git")

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
    elif args.command == "bootstrap":
        bootstrap()
    elif args.command == "fetch-memory":
        fetch_memory()
    elif args.command == "persist-memory":
        persist_memory(args.message)