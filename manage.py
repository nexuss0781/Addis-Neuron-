import os
import sys
import subprocess
import time
import signal
import argparse
from typing import Dict, Any

# --- CPEM Configuration ---
# Use absolute paths for maximum robustness in the Colab environment
BASE_DIR = "/content/project-agile-mind"
CPEM_DIR = os.path.join(BASE_DIR, ".cpem")
PID_DIR = os.path.join(CPEM_DIR, "pids")
LOG_DIR = os.path.join(CPEM_DIR, "logs")

# Ensure the PATH includes Cargo's bin directory for all subprocesses
os.environ['PATH'] = "/root/.cargo/bin:" + os.environ.get('PATH', '')

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
    Starts all defined services as background processes using robust,
    non-blocking methods suitable for the Colab environment.
    """
    print("--- [CPEM: UP] Starting all services ---")
    print(f"DEBUG: Ensuring directories exist: {PID_DIR}, {LOG_DIR}")
    os.makedirs(PID_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # --- Step 1: Compile Rust Engine (if necessary) ---
    rust_binary_path = SERVICES["logical_engine"]["command"][0]
    if not os.path.exists(rust_binary_path):
        print(f"DEBUG: Rust binary not found at '{rust_binary_path}'. Initiating compilation (this may take a few minutes)...")
        compile_command = "cargo build --release"
        print(f"DEBUG: Running compile command: '{compile_command}' in '{SERVICES['logical_engine']['cwd']}'")
        
        compile_process = subprocess.Popen(
            compile_command, shell=True, cwd=SERVICES["logical_engine"]["cwd"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=os.environ.copy()
        )
        stdout, stderr = compile_process.communicate()

        if compile_process.returncode != 0:
            print(f"--- [CPEM: FATAL ERROR] ---")
            print(f"Failed to compile Rust engine. Exit code: {compile_process.returncode}")
            if stdout: print(f"--- STDOUT --- \n{stdout}")
            if stderr: print(f"--- STDERR --- \n{stderr}")
            return
        
        print("CPEM: Rust engine compiled successfully.")

    # --- Step 2: Launch All Services ---
    for name, config in SERVICES.items():
        if os.path.exists(config["pid_file"]):
            print(f"DEBUG: PID file '{config['pid_file']}' exists. Checking if process is active...")
            try:
                with open(config["pid_file"], 'r') as f: pid = int(f.read().strip())
                os.kill(pid, 0) # Check if process exists
                print(f"CPEM: Service '{name}' (PID: {pid}) is already running. Skipping.")
                continue
            except (ValueError, ProcessLookupError):
                print(f"CPEM WARNING: Found stale PID file for '{name}'. Removing it.")
                os.remove(config["pid_file"])
            except Exception as e:
                print(f"CPEM WARNING: Error checking PID for '{name}': {e}. Assuming stopped.")
        
        print(f"CPEM: Launching service '{name}'...")
        try:
            log_file_handle = open(config["log_file"], "w")
            
            process = subprocess.Popen(
                config["command"],
                stdout=log_file_handle,
                stderr=log_file_handle,
                cwd=config["cwd"],
                start_new_session=True,
                env=os.environ.copy()
            )
            
            # --- THIS IS THE FIX ---
            # Close our script's reference to the log file handle.
            # The child process still holds a valid reference and can continue writing.
            # This allows the parent script (and the Colab cell) to terminate.
            log_file_handle.close()
            
            with open(config["pid_file"], "w") as f:
                f.write(str(process.pid))

            print(f"CPEM: Service '{name}' started successfully with PID {process.pid}.")
            time.sleep(2)

        except Exception as e:
            print(f"--- [CPEM: FATAL ERROR] ---")
            print(f"Failed to start service '{name}'.")
            print(f"Error Details: {e}")
            print("Attempting to shut down all services...")
            down()
            return
            
    print("\n--- [CPEM: UP] All services launched successfully. ---")

def down():
    print("--- [CPEM: DOWN] Shutting down all services ---")
    for name in reversed(list(SERVICES.keys())):
        config = SERVICES[name]
        pid_file = config["pid_file"]
        if not os.path.exists(pid_file):
            print(f"DEBUG: No PID file for '{name}'. Assuming it is not running.")
            continue
        try:
            pid = None
            with open(pid_file, "r") as f:
                pid_str = f.read().strip()
                if pid_str: pid = int(pid_str)
            
            if pid:
                print(f"CPEM: Stopping service '{name}' (PID: {pid}). Sending SIGTERM...")
                os.kill(pid, signal.SIGTERM)
                time.sleep(2)
                try:
                    os.kill(pid, 0)
                    print(f"CPEM WARNING: Service '{name}' did not terminate gracefully. Sending SIGKILL.")
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    print(f"CPEM: Service '{name}' (PID: {pid}) terminated successfully.")
            else:
                print(f"CPEM WARNING: PID file for '{name}' was empty.")
        except (FileNotFoundError, ProcessLookupError):
            print(f"CPEM: Process for service '{name}' not found. Cleaning up stale PID file.")
        except (ValueError) as e:
            print(f"CPEM WARNING: Corrupted PID file for '{name}'. Error: {e}")
        except Exception as e:
            print(f"--- [CPEM: ERROR] ---")
            print(f"An unexpected error occurred while stopping '{name}'. Details: {e}")
        finally:
            if os.path.exists(pid_file):
                os.remove(pid_file)
                print(f"DEBUG: Cleaned up PID file for '{name}'.")
    print("\n--- [CPEM: DOWN] Shutdown sequence complete. ---")

def status():
    print("--- [CPEM: STATUS] AGI Service Status ---")
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
                print(f"CPEM WARNING: Stale PID file found for '{name}'. Removing it.")
                os.remove(config["pid_file"])
                pid = "N/A"
            except Exception as e:
                current_status = f"Error: {type(e).__name__}"
        print(f"{name:<20} {str(pid):<10} {current_status:<20}")
    print("-" * 52)

def logs(service_name, follow):
    if service_name not in SERVICES:
        print(f"CPEM ERROR: Service '{service_name}' not found.")
        return
    log_file = SERVICES[service_name]["log_file"]
    print(f"DEBUG: Attempting to read log file at: {log_file}")
    if not os.path.exists(log_file):
        print(f"Log file for '{service_name}' not found.")
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
        except KeyboardInterrupt: print("\n--- Stopped tailing logs ---")
    else:
        with open(log_file, "r") as f: print(f.read())

def execute(service_name, command_to_run):
    if service_name not in SERVICES:
        print(f"CPEM ERROR: Service '{service_name}' not found.")
        return
    config = SERVICES[service_name]
    print(f"--- Executing '{' '.join(command_to_run)}' in '{service_name}' context ---")
    proc = subprocess.run(command_to_run, cwd=config["cwd"], capture_output=True, text=True, env=os.environ.copy())
    if proc.stdout: print(f"\n--- STDOUT ---\n{proc.stdout}")
    if proc.stderr: print(f"\n--- STDERR ---\n{proc.stderr}")
    print(f"--- Command finished with exit code {proc.returncode} ---")

def bootstrap():
    print("--- [CPEM: BOOTSTRAP] Performing one-time environment setup ---")
    print("1. Installing system dependencies...")
    subprocess.run("apt-get update -qq && apt-get install -y redis-server build-essential > /dev/null", shell=True, check=True)
    print("2. Installing Python packages...")
    subprocess.run(f"{sys.executable} -m pip install -r python_app/requirements.txt -q", shell=True, check=True)
    print("3. Setting up Rust toolchain (this may take a while)...")
    if not os.path.exists("/root/.cargo/bin/cargo"):
        rustup_init_script = "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
        subprocess.run(rustup_init_script, shell=True, env={**os.environ, "RUSTUP_HOME": "/root/.rustup", "CARGO_HOME": "/root/.cargo"}, check=True)
    print("Rust toolchain is ready.")
    print("--- [CPEM: BOOTSTRAP] Setup complete. ---")

def fetch_memory():
    print("--- [CPEM: GIT] Fetching latest memory ---")
    os.makedirs(os.path.join(BASE_DIR, "nlse_data"), exist_ok=True)
    subprocess.run('git config user.email "colab@agi.com"', shell=True, cwd=BASE_DIR, check=True)
    subprocess.run('git config user.name "Colab AGI"', shell=True, cwd=BASE_DIR, check=True)
    result = subprocess.run('git pull', shell=True, cwd=BASE_DIR, capture_output=True, text=True)
    if result.returncode != 0: print(f"CPEM WARNING: Git pull failed:\n{result.stderr}")
    else: print("CPEM: Memory fetch complete.")

def persist_memory(commit_message):
    print(f"--- [CPEM: GIT] Persisting memory with message: '{commit_message}' ---")
    subprocess.run('git config user.email "colab@agi.com"', shell=True, cwd=BASE_DIR, check=True)
    subprocess.run('git config user.name "Colab AGI"', shell=True, cwd=BASE_DIR, check=True)
    subprocess.run(f'git add {os.path.join(BASE_DIR, "nlse_data")}', shell=True, cwd=BASE_DIR)
    commit_result = subprocess.run(f'git commit -m "{commit_message}"', shell=True, cwd=BASE_DIR, capture_output=True, text=True)
    if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stdout:
        print(f"CPEM WARNING: Git commit failed:\n{commit_result.stderr}")
        return
    pat = os.environ.get("GITHUB_PAT")
    if pat: repo_url = f"https://oauth2:{pat}@github.com/nexuss0781/Addis-Neuron-.git"
    else: repo_url = "https://github.com/nexuss0781/Addis-Neuron-.git"
    push_result = subprocess.run(f'git push {repo_url}', shell=True, cwd=BASE_DIR, capture_output=True, text=True)
    if push_result.returncode != 0:
        print(f"CPEM ERROR: Git push failed:\n{push_result.stderr}\n{push_result.stdout}")
    else: print("CPEM: Memory persistence complete.")

# --- Main CLI Router ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CPEM: AGI Process Manager.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("bootstrap")
    subparsers.add_parser("fetch-memory")
    persist_parser = subparsers.add_parser("persist-memory")
    persist_parser.add_argument("message", type=str)
    subparsers.add_parser("up")
    subparsers.add_parser("down")
    subparsers.add_parser("status")
    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("service_name", choices=SERVICES.keys())
    logs_parser.add_argument("-f", "--follow", action="store_true")
    exec_parser = subparsers.add_parser("exec")
    exec_parser.add_argument("service_name", choices=SERVICES.keys())
    exec_parser.add_argument("run_command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.command == "up": up()
    elif args.command == "down": down()
    elif args.command == "status": status()
    elif args.command == "logs": logs(args.service_name, args.follow)
    elif args.command == "exec":
        if not args.run_command: print("CPEM ERROR: 'exec' requires a command to run.")
        else: execute(args.service_name, args.run_command)
    elif args.command == "bootstrap": bootstrap()
    elif args.command == "fetch-memory": fetch_memory()
    elif args.command == "persist-memory": persist_memory(args.message)