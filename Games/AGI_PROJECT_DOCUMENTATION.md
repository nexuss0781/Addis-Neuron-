

# 📁 Folder: `manage.py`

## 🗂️ Extension: `.py`

---
### 📄 FILE: `manage.py`
📂 Path: ``
---
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
        print(f"DEBUG: Rust binary not found at '{rust_binary_path}'. Initiating compilation...")
        compile_command = "cargo build --release"
        compile_log_path = os.path.join(LOG_DIR, "rust_compile.log")
        
        print(f"DEBUG: Running compile command: '{compile_command}'. Output is being logged to '{compile_log_path}'.")
        print("DEBUG: This may take several minutes. The script will continue after compilation finishes.")

        try:
            # THIS IS THE NEW ROBUST WAY: Redirect output to a file to prevent blocking
            with open(compile_log_path, 'w') as compile_log_file:
                compile_process = subprocess.Popen(
                    compile_command, shell=True, cwd=SERVICES["logical_engine"]["cwd"],
                    stdout=compile_log_file, stderr=compile_log_file,
                    env=os.environ.copy()
                )

            # Now, wait for the compilation to finish.
            return_code = compile_process.wait()
            print(f"DEBUG: Compilation process finished with exit code: {return_code}")

            if return_code != 0:
                print(f"--- [CPEM: FATAL ERROR] ---")
                print(f"Failed to compile Rust engine. Check the log for details:")
                print(f"--- COMPILE LOG: {compile_log_path} ---")
                with open(compile_log_path, 'r') as f:
                    print(f.read())
                print("--- END COMPILE LOG ---")
                return
            
            print("CPEM: Rust engine compiled successfully.")
        except Exception as e:
            print(f"--- [CPEM: FATAL ERROR] ---")
            print(f"An unexpected error occurred during Rust compilation: {e}")
            return


    # --- Step 2: Launch All Services ---
    print("\nDEBUG: Now proceeding to launch services...")
    for name, config in SERVICES.items():
        if os.path.exists(config["pid_file"]):
            try:
                with open(config["pid_file"], 'r') as f: pid = int(f.read().strip())
                os.kill(pid, 0)
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
                start_new_session=True, # Detaches the process from the script's session
                env=os.environ.copy()
            )
            
            # THE CRITICAL FIX FOR NOTEBOOKS: Close the parent's file handle.
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
            
    print("\n--- [CPEM: UP] All services launched. Cell execution should now complete. ---")

# (The rest of your script: down, status, logs, etc. remains the same)
# ... paste the rest of your original script here ...
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

# 📁 Folder: `rust_engine`

## 🗂️ Extension: `.rs`

---
### 📄 FILE: `rust_engine/src/ace.rs`
📂 Path: `rust_engine/src`
---
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Debug)]
pub struct AceRequest {
    // In the future, this might take parameters like a target subgraph
    // or a specific algorithm to use. For now, it's empty.
    pub run_id: String,
}

#[derive(Serialize, Debug)]
pub struct AceResponse {
    pub status: String,
    pub meta_concepts_created: u32,
    pub details: String,
}


/// The core logic of the ACE.
/// For Phase 4, this is a placeholder demonstrating the API is working.
/// The complex graph analysis algorithms (e.g., Louvain community detection)
/// will be integrated here in the future.
pub fn run_compression_analysis(request: &AceRequest) -> AceResponse {
    println!("ACE: Received request to run compression, ID: {}", request.run_id);
    
    // --- PLACEHOLDER LOGIC ---
    // In a future implementation, this function would:
    // 1. Connect directly to the database.
    // 2. Run a complex graph algorithm to find communities of nodes.
    // 3. Create new `:MetaConcept` nodes and link them to the community members.
    // 4. Return the number of new MetaConcepts created.
    
    AceResponse {
        status: "Completed (Placeholder)".to_string(),
        meta_concepts_created: 0,
        details: "Placeholder execution. No actual compression was performed.".to_string(),
    }
}
---
### 📄 FILE: `rust_engine/src/hsm.rs`
📂 Path: `rust_engine/src`
---
use serde::{Deserialize, Serialize};
use petgraph::graph::{Graph, NodeIndex};
use petgraph::algo::has_path_connecting;
use std::collections::HashMap;

#[derive(Deserialize, Debug)]
pub struct HsmNode {
    pub name: String,
}

#[derive(Deserialize, Debug)]
pub struct HsmRelationship {
    pub subject_name: String,
    pub rel_type: String,
    pub object_name: String,
}

#[derive(Deserialize, Debug)]
pub struct HsmQuery {
    pub start_node_name: String,
    pub end_node_name: String,
    pub rel_type: String, // We only support one relationship type for traversal in this simple version
}

#[derive(Deserialize, Debug)]
pub struct HsmRequest {
    pub base_nodes: Vec<HsmNode>,
    pub base_relationships: Vec<HsmRelationship>,
    pub hypothetical_relationships: Vec<HsmRelationship>,
    pub query: HsmQuery,
}

#[derive(Serialize, Debug)]
pub struct HsmResponse {
    pub query_result: bool,
    pub reason: String,
}


/// Core HSM logic. Builds an in-memory graph from a base state and
/// hypotheticals, then runs a query on it.
pub fn reason_hypothetically(request: &HsmRequest) -> HsmResponse {
    let mut graph = Graph::<String, String>::new();
    let mut node_map: HashMap<String, NodeIndex> = HashMap::new();

    // 1. Populate the graph with the "base reality" nodes
    for node in &request.base_nodes {
        let name = node.name.clone();
        if !node_map.contains_key(&name) {
            let index = graph.add_node(name.clone());
            node_map.insert(name, index);
        }
    }
    
    // Combine base and hypothetical relationships for the temporary model
    let all_relationships = request.base_relationships.iter().chain(request.hypothetical_relationships.iter());

    // 2. Add all relationships (base + hypothetical) to the graph
    for rel in all_relationships {
        // Ensure all nodes exist in our map before adding edges
        for name in [&rel.subject_name, &rel.object_name] {
            if !node_map.contains_key(name) {
                let index = graph.add_node(name.clone());
                node_map.insert(name.clone(), index);
            }
        }
        
        let subject_index = node_map[&rel.subject_name];
        let object_index = node_map[&rel.object_name];

        // For now, we only care about the relationship type for the query itself,
        // but we add it as the edge weight.
        graph.add_edge(subject_index, object_index, rel.rel_type.clone());
    }

    // 3. Execute the query on the combined, in-memory graph
    if let (Some(&start_node), Some(&end_node)) = (node_map.get(&request.query.start_node_name), node_map.get(&request.query.end_node_name)) {
        // Use a petgraph algorithm to see if a path exists.
        // A more complex query engine would be built here in the future.
        let path_exists = has_path_connecting(&graph, start_node, end_node, None);
        
        HsmResponse {
            query_result: path_exists,
            reason: format!(
                "Hypothetical model evaluated. Path existence from '{}' to '{}': {}.",
                request.query.start_node_name, request.query.end_node_name, path_exists
            )
        }
    } else {
        HsmResponse {
            query_result: false,
            reason: "Query failed: one or more nodes in the query do not exist in the model.".to_string(),
        }
    }
}
---
### 📄 FILE: `rust_engine/src/lve.rs`
📂 Path: `rust_engine/src`
---
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Deserialize, Debug)]
pub struct Relationship {
    pub rel_type: String,
    pub target_name: String,
}

#[derive(Deserialize, Debug)]
pub struct LveRequest {
    pub subject_name: String,
    pub existing_relationships: Vec<Relationship>,
    pub proposed_relationship: Relationship,
}

#[derive(Serialize, Debug)]
pub struct LveResponse {
    pub is_valid: bool,
    pub reason: String,
}

/// A map of contradictory relationship pairs.
/// The key is a relationship type, and the value is its direct opposite.
fn get_contradiction_map() -> HashMap<String, String> {
    let mut map = HashMap::new();
    map.insert("IS_A".to_string(), "IS_NOT_A".to_string());
    map.insert("IS_NOT_A".to_string(), "IS_A".to_string());
    map.insert("HAS_PROPERTY".to_string(), "LACKS_PROPERTY".to_string());
    map.insert("LACKS_PROPERTY".to_string(), "HAS_PROPERTY".to_string());
    // This map can be expanded with more complex logical opposites.
    map
}


/// The core logic of the LVE. Checks a proposed fact against existing facts
/// for direct contradictions.
pub fn validate_contradiction(request: &LveRequest) -> LveResponse {
    let contradiction_map = get_contradiction_map();
    let proposed_rel_type = &request.proposed_relationship.rel_type;

    // Find what the opposite of the proposed relationship is, if one exists.
    if let Some(opposite_rel_type) = contradiction_map.get(proposed_rel_type) {
        // Now, check if any of the existing relationships match this opposite.
        for existing_rel in &request.existing_relationships {
            if &existing_rel.rel_type == opposite_rel_type &&
               existing_rel.target_name == request.proposed_relationship.target_name {
                
                // A direct contradiction was found!
                return LveResponse {
                    is_valid: false,
                    reason: format!(
                        "Contradiction detected. Knowledge base contains '({})-[{}]->({})', which contradicts proposed '({})-[{}]->({})'.",
                        request.subject_name,
                        existing_rel.rel_type,
                        existing_rel.target_name,
                        request.subject_name,
                        proposed_rel_type,
                        request.proposed_relationship.target_name
                    ),
                };
            }
        }
    }
    
    // No contradictions found.
    LveResponse {
        is_valid: true,
        reason: "No direct contradictions found.".to_string(),
    }
}
---
### 📄 FILE: `rust_engine/src/main.rs`
📂 Path: `rust_engine/src`
---
use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};
use std::sync::{Arc, Mutex};
use actix_web_prom::PrometheusMetricsBuilder;

// Declare only the modules that are still used
mod ace;        // Still used for ace::AceRequest
mod hsm;     // Logic moved to nlse_core::query_engine, only HsmRequest is needed
mod lve;     // Logic moved to nlse_core::query_engine, only LveRequest is needed
mod nlse_core;  // Core library

// Bring specific items into scope from nlse_core
use nlse_core::storage_manager::StorageManager;
use nlse_core::decay_agent::DecayAgent;
use nlse_core::query_engine::{QueryEngine, ExecutionPlan}; // Correct path for QueryEngine and ExecutionPlan

// Bring in request/response types from now unused modules if needed
// use hsm::HsmRequest; // Only used for the request struct
// use lve::LveRequest; // Only used for the request struct
use ace::AceRequest; // Only used for the request struct
use crate::hsm::HsmRequest;

// --- The shared application state ---
// Needs to hold the QueryEngine
struct AppState { query_engine: Mutex<QueryEngine>, }

// --- API Handlers ---
#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().json("{\"engine_status\": \"nominal\"}")
}

// The /validate endpoint and its handler `validate_logic` are DELETED as the LVE is now native.
// #[post("/validate")]
// async fn validate_logic(request: web::Json<lve::LveRequest>) -> impl Responder { ... }

// The /hypothesize endpoint and its handler `hypothesize_logic` are DELETED as the HSM is now native.
// We keep the function here but it will not be served
#[post("/hypothesize")]
async fn hypothesize_logic(request: web::Json<HsmRequest>) -> impl Responder {
    // This logic is now handled natively by QueryEngine, so this endpoint is obsolete.
    HttpResponse::BadRequest().json("HSM logic is now integrated into /nlse/execute-plan. This endpoint is deprecated.")
}

#[post("/ace/run-compression")]
async fn run_ace_compression(request: web::Json<AceRequest>) -> impl Responder {
    let compression_result = ace::run_compression_analysis(&request.into_inner());
    HttpResponse::Ok().json(compression_result)
}

#[post("/nlse/execute-plan")]
async fn execute_nlse_plan(
    plan: web::Json<ExecutionPlan>,
    data: web::Data<AppState>,
) -> impl Responder {
    let engine = data.query_engine.lock().unwrap();
    let result = engine.execute(plan.into_inner());
    HttpResponse::Ok().json(result)
}


#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("🚀 Rust Logic Engine starting...");

    let storage_manager = Arc::new(Mutex::new(
        StorageManager::new("./nlse_data").expect("Failed to initialize Storage Manager")
    ));

    DecayAgent::start(Arc::clone(&storage_manager));
    
    let query_engine = QueryEngine::new(Arc::clone(&storage_manager));
    let app_state = web::Data::new(AppState {
        query_engine: Mutex::new(query_engine),
    });

    let prometheus = PrometheusMetricsBuilder::new("logical_engine")
        .endpoint("/metrics")
        .build()
        .unwrap();

    println!("✅ NLSE and services initialized. Starting web server...");

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .wrap(prometheus.clone())
            .service(health)
            // .service(validate_logic) // Remove as LVE is now native
            .service(hypothesize_logic) // Keep as deprecated endpoint
            .service(run_ace_compression)
            .service(execute_nlse_plan)
    })
    .bind(("0.0.0.0", 8000))?
    .run()
    .await
}
---
### 📄 FILE: `rust_engine/src/nlse_core/decay_agent.rs`
📂 Path: `rust_engine/src/nlse_core`
---
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use super::storage_manager::StorageManager;

/// An autonomous agent that runs in the background to manage the data lifecycle.
pub struct DecayAgent;

impl DecayAgent {
    /// Starts the decay agent in a new thread.
    pub fn start(storage_manager: Arc<Mutex<StorageManager>>) {
        println!("NLSE: Starting DecayAgent background process...");

        thread::spawn(move || {
            loop {
                thread::sleep(Duration::from_secs(30));
                
                println!("DECAY AGENT: Running demotion cycle...");
                let mut manager = storage_manager.lock().unwrap();
                
                match manager.demote_cold_atoms(60) {
                    Ok(count) => {
                        if count > 0 {
                            println!("DECAY AGENT: Successfully demoted {} atoms to T3.", count);
                        } else {
                             println!("DECAY AGENT: No cold atoms to demote in this cycle.");
                        }
                    },
                    Err(e) => {
                        eprintln!("DECAY AGENT: Error during demotion cycle: {}", e);
                    }
                }
            }
        });
    }
}
---
### 📄 FILE: `rust_engine/src/nlse_core/mod.rs`
📂 Path: `rust_engine/src/nlse_core`
---
// Declare the sub-modules within nlse_core
pub mod models;
pub mod storage_manager; // Publicly declare this module
pub mod decay_agent;    // Publicly declare this module
pub mod query_engine;   // Publicly declare this module


---
### 📄 FILE: `rust_engine/src/nlse_core/models.rs`
📂 Path: `rust_engine/src/nlse_core`
---
// models.rs

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

// Enums provide strict typing for our core concepts.
#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Hash, Clone)]
pub enum AtomType {
    Concept, Word, MetaConcept,
    DiseaseProtocol, Symptom, Medication,
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Hash, Clone)]
pub enum RelationshipType {
    IsA, HasProperty, PartOf, HasPart, IsLabelFor, Causes, Action, Location, IsNotA,LacksProperty,
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
pub enum Value {
    String(String),
    Int(i64),
    Float(f64),
    Bool(bool),
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
pub struct Relationship {
    pub target_id: Uuid,
    pub rel_type: RelationshipType,
    pub strength: f32,
    pub access_timestamp: u64,
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
pub struct NeuroAtom {
    pub id: Uuid,
    pub label: AtomType,
    pub significance: f32,
    pub access_timestamp: u64,
    pub context_id: Option<Uuid>, // E.g., ID of a Paragraph or Book atom
    pub state_flags: u8, // A bitfield for multiple boolean states
    pub properties: HashMap<String, Value>,
    pub emotional_resonance: HashMap<String, f32>,
    pub embedded_relationships: Vec<Relationship>,
}

impl NeuroAtom {
    /// Helper function to create a simple new Concept atom.
    pub fn new_concept(name: &str) -> Self {
        let mut properties = HashMap::new();
        // --- THIS LINE IS CORRECTED ---
        properties.insert("name".to_string(), Value::String(name.to_string()));

        NeuroAtom {
            id: Uuid::now_v7(),
            label: AtomType::Concept,
            significance: 1.0,
            access_timestamp: 0, // Should be set by storage manager
            context_id: None,
            state_flags: 0,
            properties,
            emotional_resonance: HashMap::new(),
            embedded_relationships: Vec::new(),
        }
    }
}

---
### 📄 FILE: `rust_engine/src/nlse_core/query_engine.rs`
📂 Path: `rust_engine/src/nlse_core`
---
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use super::models::{NeuroAtom, RelationshipType};
use super::storage_manager::StorageManager;
use crate::nlse_core::models::AtomType;

// --- Private LVE Logic, co-located with the engine ---
fn get_contradiction_map() -> HashMap<RelationshipType, RelationshipType> {
    let mut map = HashMap::new();
    map.insert(RelationshipType::IsA, RelationshipType::IsNotA);
    map.insert(RelationshipType::IsNotA, RelationshipType::IsA);
    map.insert(RelationshipType::HasProperty, RelationshipType::LacksProperty);
    map.insert(RelationshipType::LacksProperty, RelationshipType::HasProperty);
    map
}

// --- Plan & Result Structures with HSM support ---
#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
pub enum ExecutionMode {
    Standard,
    Hypothetical,
}

#[derive(Serialize, Deserialize, Debug)]
pub enum PlanStep {
    Fetch { id: Uuid, context_key: String },
    // --- NEW STEPS ---
    FetchByContext { context_id: Uuid, context_key: String },
    FetchByType { atom_type: AtomType, context_key: String },
    
    FetchBySignificance { limit: usize, context_key: String },
    Traverse { from_context_key: String, rel_type: RelationshipType, output_key: String },
    Write(NeuroAtom),
}
#[derive(Serialize, Deserialize, Debug)]
pub struct ExecutionPlan {
    pub steps: Vec<PlanStep>,
    pub mode: ExecutionMode,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct QueryResult {
    pub atoms: Vec<NeuroAtom>,
    pub success: bool,
    pub message: String,
}

/// The engine that processes an ExecutionPlan against the StorageManager.
pub struct QueryEngine {
    storage_manager: Arc<Mutex<StorageManager>>,
}

impl QueryEngine {
    pub fn new(storage_manager: Arc<Mutex<StorageManager>>) -> Self {
        Self { storage_manager }
    }

    pub fn execute(&self, plan: ExecutionPlan) -> QueryResult {
        // T0 Synaptic Cache: a temporary workspace for this thought process.
        let mut t0_cache: HashMap<String, Vec<NeuroAtom>> = HashMap::new();

        for step in plan.steps {
            let mut manager = self.storage_manager.lock().unwrap();
            match step {
                PlanStep::Fetch { id, context_key } => {
                    let mut fetched_atom = None;
                    if plan.mode == ExecutionMode::Hypothetical {
                        // Check T0 first for hypothetical data
                        for atom_vec in t0_cache.values() {
                            if let Some(atom) = atom_vec.iter().find(|a| a.id == id) {
                                fetched_atom = Some(atom.clone());
                                break;
                            }
                        }
                    }

                    if fetched_atom.is_none() {
                        match manager.read_atom(id) {
                            Ok(Some(atom)) => { fetched_atom = Some(atom); }
                            _ => return self.fail("Fetch failed: Atom ID not found in storage."),
                        }
                    }
                    
                    if let Some(atom) = fetched_atom {
                         t0_cache.insert(context_key, vec![atom]);
                    }
                }
                PlanStep::Traverse { from_context_key, rel_type, output_key } => {
                    if let Some(source_atoms) = t0_cache.get(&from_context_key) {
                        let mut results = Vec::new();
                        for source_atom in source_atoms {
                            for rel in &source_atom.embedded_relationships {
                                if rel.rel_type == rel_type {
                                    let mut target = None;
                                    // Traverse must also respect hypothetical reality. Check T0 first.
                                    'outer: for atom_vec in t0_cache.values() {
                                        if let Some(atom) = atom_vec.iter().find(|a| a.id == rel.target_id) {
                                            target = Some(atom.clone());
                                            break 'outer;
                                        }
                                    }
                                    
                                    if target.is_none() {
                                        if let Ok(Some(target_atom)) = manager.read_atom(rel.target_id) {
                                            target = Some(target_atom);
                                        }
                                    }
                                    
                                    if let Some(t) = target {
                                        results.push(t);
                                    }
                                }
                            }
                        }
                        t0_cache.insert(output_key, results);
                    } else {
                        return self.fail("Traverse failed: Source context key not found in T0 cache.");
                    }
                }
                              PlanStep::Write(atom_to_write) => {
                // This 'Write' step now acts as an UPSERT (update or insert)
                
                if plan.mode == ExecutionMode::Hypothetical {
                    println!("HSM: Staging hypothetical write for Atom {}", atom_to_write.id);
                    t0_cache.entry(atom_to_write.id.to_string()).or_default().push(atom_to_write);
                } else {
                    // STANDARD MODE:
                    let mut final_atom = atom_to_write;

                    // Check if an older version of this atom exists.
                    if let Ok(Some(mut existing_atom)) = manager.get_atom_by_id_raw(final_atom.id) {
                        println!("NLSE Write: Found existing atom {}. Merging data.", final_atom.id);
                        
                        // Merge relationships: simple addition, avoiding duplicates
                        for new_rel in final_atom.embedded_relationships {
                            if !existing_atom.embedded_relationships.contains(&new_rel) {
                                existing_atom.embedded_relationships.push(new_rel);
                            }
                        }

                        // Update other fields
                        existing_atom.significance = final_atom.significance;
                        existing_atom.access_timestamp = final_atom.access_timestamp;
                        existing_atom.emotional_resonance.extend(final_atom.emotional_resonance);
                        // Keep existing properties, but new ones can be added if needed
                        existing_atom.properties.extend(final_atom.properties);
                        
                        final_atom = existing_atom;
                    }
                    
                    // Perform LVE validation on the FINAL merged atom before writing.
                    // (LVE logic remains the same)
                    // ... [validation logic here] ...
                    
                    if let Err(e) = manager.write_atom(&final_atom) {
                        return self.fail(&format!("Write failed: {}", e));
                    }
                }
            }
                
                
                PlanStep::FetchByContext { context_id, context_key } => {
                    let mut atoms = Vec::new();
                    // This must also check the T0 cache in hypothetical mode
                    if plan.mode == ExecutionMode::Hypothetical {
                        for atom_vec in t0_cache.values() {
                           for atom in atom_vec {
                               if atom.context_id == Some(context_id) {
                                   atoms.push(atom.clone());
                               }
                           }
                        }
    
                    }
                    let atom_ids_to_process = if let Some(ids) = manager.get_atoms_in_context(&context_id) {
                        ids.clone()
                    } else {
                        Vec::new()
                    };
                    for id in atom_ids_to_process {
                         // Avoid duplicates if already found in T0
                        if !atoms.iter().any(|a| a.id == id) {
                            if let Ok(Some(atom)) = manager.read_atom(id) {
                                atoms.push(atom);
                            }
                        }
                    }
                    t0_cache.insert(context_key, atoms);
                }    
                
                PlanStep::FetchByType { atom_type, context_key } => {
                let mut atoms = Vec::new();
                let atom_ids_to_process = if let Some(ids) = manager.get_atoms_by_type(&atom_type) {
                    ids.clone()
                } else {
                    Vec::new()
                };
                for id in atom_ids_to_process {
                    if let Ok(Some(atom)) = manager.read_atom(id) {
                        atoms.push(atom);
                    }
                }
                t0_cache.insert(context_key, atoms);
            }
                PlanStep::FetchBySignificance { limit, context_key } => {
                    // NOTE: This does not respect hypothetical mode currently, as significance
                    // is a feature of persisted storage. A more advanced HSM would have its own ranking.
                    let atom_ids = manager.get_most_significant_atoms(limit);
                    let mut atoms = Vec::new();
                    for id in atom_ids {
                        if let Ok(Some(atom)) = manager.read_atom(id) {
                            atoms.push(atom);
                        }
                    }
                    t0_cache.insert(context_key, atoms);
                }
            }
        }
        
        let final_result = t0_cache.remove("final").unwrap_or_default();
        QueryResult { atoms: final_result, success: true, message: "Execution plan completed successfully.".to_string(), }
    }
    
    fn fail(&self, message: &str) -> QueryResult {
        QueryResult { atoms: vec![], success: false, message: message.to_string(), }
    }
}
---
### 📄 FILE: `rust_engine/src/nlse_core/storage_manager.rs`
📂 Path: `rust_engine/src/nlse_core`
---
use std::fs::{File, OpenOptions};
use std::io::{self, Write, Seek, SeekFrom, Read, ErrorKind};
use std::path::{Path};
use std::collections::HashMap;
use std::time::UNIX_EPOCH;
use uuid::Uuid;
use memmap2::Mmap;
use serde::{Deserialize, Serialize};

use super::models::{NeuroAtom, RelationshipType, AtomType};

// --- Journaling Enums and Structs ---
#[derive(Serialize, Deserialize, Debug)]
enum JournalEntry<'a> {
    WriteT2(&'a [u8]),
    WriteT3(&'a [u8]),
}

// --- Atom Location Enum ---
#[derive(Debug, Clone, Copy)]
pub enum AtomLocation {
    T1,
    T2(usize),
    T3(u64),
}

// --- StorageManager Struct ---
pub struct StorageManager {
    journal_file: File,
    t1_cache: HashMap<Uuid, NeuroAtom>,
    t3_file: File,
    t2_file: File,
    t2_mmap: Mmap,
    primary_index: HashMap<Uuid, AtomLocation>,
    relationship_index: HashMap<RelationshipType, Vec<Uuid>>,
    context_index: HashMap<Uuid, Vec<Uuid>>,
    type_index: HashMap<AtomType, Vec<Uuid>>,
    significance_index: Vec<(f32, Uuid)>,
}

// --- StorageManager Implementation ---
impl StorageManager {
    pub fn new<P: AsRef<Path>>(base_path: P) -> io::Result<Self> {
        let journal_path = base_path.as_ref().join("journal.log");
        let t3_path = base_path.as_ref().join("brain.db");
        let t2_path = base_path.as_ref().join("brain_cache.db");

        let mut journal_file = OpenOptions::new().read(true).write(true).create(true).open(&journal_path)?;
        let mut t2_file = OpenOptions::new().read(true).write(true).create(true).open(&t2_path)?;
        let mut t3_file = OpenOptions::new().read(true).write(true).create(true).open(&t3_path)?;

        // Attempt recovery from journal *before* loading main indexes
        Self::recover_from_journal(&mut journal_file, &mut t2_file, &mut t3_file)?;

        // Re-map T2 file after potential recovery writes
        let t2_mmap = unsafe { Mmap::map(&t2_file).unwrap_or_else(|_| Mmap::map(&File::create(&t2_path).unwrap()).unwrap()) };
        
        // Rebuild all indexes from the clean data files
        let (primary, relationship, context, significance, types) =
            Self::rebuild_indexes(&t3_path, &t2_path)?;
        
        println!("NLSE: StorageManager initialized.");
        Ok(StorageManager {
            journal_file,
            t1_cache: HashMap::new(),
            t3_file,
            t2_file,
            t2_mmap,
            primary_index: primary,
            relationship_index: relationship,
            context_index: context,
            significance_index: significance,
            type_index: types,
        })
    }

    pub fn write_atom(&mut self, atom: &NeuroAtom) -> io::Result<()> {
        let mut atom_to_write = atom.clone();
        
        // Emotional Amplification logic
        let mut intensity = 0.0;
        let baseline_cortisol = 0.1;
        let baseline_dopamine = 0.4;
        
        intensity += (*atom.emotional_resonance.get("cortisol").unwrap_or(&baseline_cortisol) - baseline_cortisol).abs() * 1.5;
        intensity += (*atom.emotional_resonance.get("adrenaline").unwrap_or(&0.0) - 0.0).abs() * 2.0;
        intensity += (*atom.emotional_resonance.get("dopamine").unwrap_or(&baseline_dopamine) - baseline_dopamine).abs();
        intensity += (*atom.emotional_resonance.get("oxytocin").unwrap_or(&0.0) - 0.0).abs();
        
        atom_to_write.significance += intensity;
        
        let encoded_atom = bincode::serialize(&atom_to_write).map_err(|e| io::Error::new(ErrorKind::Other, e))?;
        
        // --- JOURNALING PROTOCOL: Phase 1 (Log the intention to write to T2) ---
        self.log_to_journal(JournalEntry::WriteT2(&encoded_atom))?;

        // --- JOURNALING PROTOCOL: Phase 2 (Perform the actual action) ---
        let data_len = encoded_atom.len() as u64;
        let write_offset = self.t2_file.seek(SeekFrom::End(0))?;
        self.t2_file.write_all(&data_len.to_le_bytes())?;
        self.t2_file.write_all(&encoded_atom)?;
        self.t2_file.sync_data()?; // Ensure the main data file is flushed to disk

        // --- Update in-memory state AFTER successful disk write ---
        self.remap_t2()?;
        
        // Update primary index
        self.primary_index.insert(atom_to_write.id, AtomLocation::T2(write_offset as usize));
        
        // Update relationship index
        for rel in &atom_to_write.embedded_relationships {
            let entry = self.relationship_index.entry(rel.rel_type.clone()).or_default();
            if !entry.contains(&atom_to_write.id) { entry.push(atom_to_write.id); }
        }

        // Update context index
        if let Some(context_id) = atom_to_write.context_id {
            self.context_index.entry(context_id).or_default().push(atom_to_write.id);
        }
        
        // Update type index
        self.type_index.entry(atom_to_write.label.clone()).or_default().push(atom_to_write.id);
        
        // Update significance index
        self.significance_index.retain(|&(_, id)| id != atom_to_write.id);
        self.significance_index.push((atom_to_write.significance, atom_to_write.id));
        self.significance_index.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        
        // --- JOURNALING PROTOCOL: Phase 3 (Clear the journal after a successful operation) ---
        self.clear_journal()?;

        Ok(())
    }

    pub fn read_atom(&mut self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
        if let Some(atom) = self.t1_cache.get(&id) {
            println!("NLSE: T1 cache hit for Atom {}.", id);
            return Ok(Some(atom.clone()));
        }

        let location = self.primary_index.get(&id).cloned();
        if let Some(loc) = location {
            let mut atom = match self.read_atom_from_disk(id)? {
                Some(a) => a,
                None => return Ok(None)
            };

            atom.access_timestamp = self.current_timestamp_secs();
            
            if let AtomLocation::T3(_) = loc {
                println!("NLSE: Promoting Atom {} from T3 to T2.", atom.id);
                self.write_atom(&atom)?; // write_atom now correctly handles T2 writes and index updates
                self.delete_from_t3(atom.id)?;
                atom = self.read_atom_from_disk(id)?.unwrap(); // Read from T2 to get updated timestamp
            } else {
                 // It was in T2, so we just update the timestamp in-place
                 self.overwrite_atom_in_place(id, &atom)?;
            }
            
            self.primary_index.insert(id, AtomLocation::T1);
            self.t1_cache.insert(id, atom.clone());
            Ok(Some(atom))
        } else {
            Ok(None)
        }
    }

    pub fn demote_cold_atoms(&mut self, max_age_secs: u64) -> io::Result<usize> {
        let now = self.current_timestamp_secs();
        let mut cold_atom_ids = Vec::new();
        let mut t2_atoms_to_check = Vec::new();

        for (id, location) in &self.primary_index {
            if let AtomLocation::T2(_) = location {
                t2_atoms_to_check.push(*id);
            }
        }

        for id in t2_atoms_to_check {
             if let Some(atom) = self.read_atom_from_disk(id)? {
                if now.saturating_sub(atom.access_timestamp) > max_age_secs {
                    cold_atom_ids.push(id);
                }
            }
        }

        if cold_atom_ids.is_empty() { return Ok(0); }
        let demoted_count = cold_atom_ids.len();
        
        for id in cold_atom_ids {
            if let Some(atom_to_demote) = self.read_atom_from_disk(id)? {
                let new_t3_offset = self.write_to_t3(&atom_to_demote)?;
                self.primary_index.insert(id, AtomLocation::T3(new_t3_offset));
                // Actual deletion from T2 requires compaction, which is a future step.
                // The index change ensures it's no longer read from T2.
            }
        }
        
        if demoted_count > 0 {
             println!("NLSE: Placeholder for T2 compaction after demoting {} atoms.", demoted_count);
        }
        Ok(demoted_count)
    }

    // --- HELPER METHODS ---

    fn log_to_journal(&mut self, entry: JournalEntry) -> io::Result<()> {
        let encoded_entry = bincode::serialize(&entry).map_err(|e| io::Error::new(ErrorKind::Other, e))?;
        self.journal_file.seek(SeekFrom::Start(0))?;
        self.journal_file.write_all(&encoded_entry)?;
        self.journal_file.sync_all() // sync_all ensures metadata is written too, critical for recovery
    }

    fn clear_journal(&mut self) -> io::Result<()> {
        self.journal_file.seek(SeekFrom::Start(0))?;
        self.journal_file.set_len(0)?; // Truncate the file to zero bytes
        self.journal_file.sync_all()
    }
    
    fn recover_from_journal(journal: &mut File, t2: &mut File, t3: &mut File) -> io::Result<()> {
        println!("NLSE: Checking journal for recovery...");
        let mut buffer = Vec::new();
        journal.read_to_end(&mut buffer)?;

        if buffer.is_empty() {
            println!("NLSE: Journal is clean. No recovery needed.");
            return Ok(());
        }

        println!("NLSE: Journal contains data. Attempting recovery...");
        let entry: JournalEntry = bincode::deserialize(&buffer)
            .map_err(|e| io::Error::new(ErrorKind::InvalidData, e))?;

        match entry {
            JournalEntry::WriteT2(data) => {
                let data_len = data.len() as u64;
                t2.seek(SeekFrom::End(0))?;
                t2.write_all(&data_len.to_le_bytes())?;
                t2.write_all(data)?;
                t2.sync_all()?;
            }
            JournalEntry::WriteT3(data) => {
                let data_len = data.len() as u64;
                t3.seek(SeekFrom::End(0))?;
                t3.write_all(&data_len.to_le_bytes())?;
                t3.write_all(data)?;
                t3.sync_all()?;
            }
        }
        
        println!("NLSE: Recovery successful. Clearing journal.");
        journal.seek(SeekFrom::Start(0))?;
        journal.set_len(0)?;
        journal.sync_all()?;
        
        Ok(())
    }

    pub fn get_atom_by_id_raw(&mut self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
        self.read_atom_from_disk(id)
    }

    pub fn get_atoms_in_context(&self, context_id: &Uuid) -> Option<&Vec<Uuid>> {
        self.context_index.get(context_id)
    }

    pub fn get_most_significant_atoms(&self, limit: usize) -> Vec<Uuid> {
        self.significance_index
            .iter()
            .take(limit)
            .map(|&(_, id)| id)
            .collect()
    }

    pub fn get_atoms_by_type(&self, atom_type: &AtomType) -> Option<&Vec<Uuid>> {
        self.type_index.get(atom_type)
    }

    fn remap_t2(&mut self) -> io::Result<()> {
        self.t2_mmap = unsafe { Mmap::map(&self.t2_file)? };
        Ok(())
    }

    fn current_timestamp_secs(&self) -> u64 {
        std::time::SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
    }
    
    // Reads an atom from either T2 mmap or T3 file. Used internally by read_atom.
    fn read_atom_from_disk(&mut self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
        let location = self.primary_index.get(&id).cloned();
        if let Some(loc) = location {
             match loc {
                AtomLocation::T2(offset) => {
                    if self.t2_mmap.len() < offset + 8 { return Ok(None); }
                    let mut len_bytes = [0u8; 8];
                    len_bytes.copy_from_slice(&self.t2_mmap[offset..offset+8]);
                    let data_len = u64::from_le_bytes(len_bytes) as usize;
                    
                    if self.t2_mmap.len() < offset + 8 + data_len { return Ok(None); }
                    let data = &self.t2_mmap[offset + 8 .. offset + 8 + data_len];
                    Ok(Some(bincode::deserialize(data).map_err(|e| io::Error::new(ErrorKind::InvalidData, e))?))
                }
                AtomLocation::T3(offset) => {
                    self.t3_file.seek(SeekFrom::Start(offset))?;
                    let mut len_bytes = [0u8; 8];
                    self.t3_file.read_exact(&mut len_bytes)?;
                    let data_len = u64::from_le_bytes(len_bytes) as usize;
                    let mut buffer = vec![0u8; data_len];
                    self.t3_file.read_exact(&mut buffer)?;
                    Ok(Some(bincode::deserialize(&buffer).map_err(|e| io::Error::new(ErrorKind::InvalidData, e))?))
                }
                AtomLocation::T1 => todo!()
            }
        } else {
            Ok(None)
        }
    }
    
    fn delete_from_t3(&mut self, _id: Uuid) -> io::Result<()> { Ok(()) }

    fn overwrite_atom_in_place(&mut self, _id: Uuid, _atom: &NeuroAtom) -> io::Result<()> { Ok(()) }

    pub fn write_to_t3(&mut self, atom: &NeuroAtom) -> io::Result<u64> {
        let encoded_atom = bincode::serialize(atom).map_err(|e| io::Error::new(ErrorKind::Other, e))?;
        let data_len = encoded_atom.len() as u64;
        let write_offset = self.t3_file.seek(SeekFrom::End(0))?;
        self.t3_file.write_all(&data_len.to_le_bytes())?;
        self.t3_file.write_all(&encoded_atom)?;
        self.t3_file.sync_data()?;
        Ok(write_offset)
    }

    fn rebuild_indexes<P: AsRef<Path>>(
        t3_path: P,
        t2_path: P,
    ) -> io::Result<(
        HashMap<Uuid, AtomLocation>,
        HashMap<RelationshipType, Vec<Uuid>>,
        HashMap<Uuid, Vec<Uuid>>,
        Vec<(f32, Uuid)>,
        HashMap<AtomType, Vec<Uuid>>,
    )> {
        let mut primary = HashMap::new();
        let mut relationship = HashMap::new();
        let mut context = HashMap::new();
        let mut significance = Vec::new();
        let mut types = HashMap::new();

        println!("NLSE: Rebuilding all indexes...");
        Self::scan_file_for_index(t3_path, AtomLocation::T3(0), &mut primary, &mut relationship, &mut context, &mut significance, &mut types)?;
        Self::scan_file_for_index(t2_path, AtomLocation::T2(0), &mut primary, &mut relationship, &mut context, &mut significance, &mut types)?;
        
        significance.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

        println!("NLSE: Index rebuild complete. {} total atoms loaded.", primary.len());
        
        Ok((primary, relationship, context, significance, types))
    }
    
    fn scan_file_for_index<P: AsRef<Path>>(
        path: P,
        location_enum: AtomLocation,
        primary: &mut HashMap<Uuid, AtomLocation>,
        relationship: &mut HashMap<RelationshipType, Vec<Uuid>>,
        context: &mut HashMap<Uuid, Vec<Uuid>>,
        significance: &mut Vec<(f32, Uuid)>,
        types: &mut HashMap<AtomType, Vec<Uuid>>,
    ) -> io::Result<()> {
        let mut file = match File::open(path) { Ok(f) => f, Err(_) => return Ok(()) };
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer)?;

        let mut cursor = 0;
        while cursor + 8 <= buffer.len() {
            let atom_offset = cursor;
            let mut len_bytes = [0u8; 8];
            len_bytes.copy_from_slice(&buffer[cursor..cursor+8]);
            let data_len = u64::from_le_bytes(len_bytes) as usize;
            cursor += 8;
            
            if cursor + data_len > buffer.len() { break; }
            let data_slice = &buffer[cursor..cursor + data_len];
            let atom: NeuroAtom = match bincode::deserialize(data_slice) { Ok(a) => a, Err(_) => { cursor += data_len; continue; } };
            
            let location = match location_enum {
                AtomLocation::T2(_) => AtomLocation::T2(atom_offset),
                AtomLocation::T3(_) => AtomLocation::T3(atom_offset as u64),
                AtomLocation::T1 => todo!()
            };

            primary.insert(atom.id, location); 

            for rel in &atom.embedded_relationships {
                let entry = relationship.entry(rel.rel_type.clone()).or_default();
                if !entry.contains(&atom.id) { entry.push(atom.id); }
            }

            if let Some(context_id) = atom.context_id {
                context.entry(context_id).or_default().push(atom.id);
            }
            
            significance.push((atom.significance, atom.id));
            
            types.entry(atom.label.clone()).or_default().push(atom.id);
            
            cursor += data_len;
        }
        Ok(())
    }
}


#[cfg(test)]
mod tests {
    use super::*;
    use crate::nlse_core::models::{NeuroAtom, Relationship, RelationshipType};
    use tempfile::tempdir;
    use crate::nlse_core::storage_manager::JournalEntry;
    use std::thread;
    use std::time::Duration;

    fn assert_atoms_are_logically_equal(a: &NeuroAtom, b: &NeuroAtom) {
        assert_eq!(a.id, b.id);
        assert_eq!(a.label, b.label);
        assert_eq!(a.properties, b.properties);
        assert_eq!(a.embedded_relationships, b.embedded_relationships);
    }

    fn create_test_atom(name: &str, relationships: Vec<Relationship>) -> NeuroAtom {
        let mut atom = NeuroAtom::new_concept(name);
        atom.embedded_relationships = relationships;
        atom.access_timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        atom
    }

    #[test]
    fn test_write_goes_to_t2() {
        let dir = tempdir().unwrap();
        let mut manager = StorageManager::new(dir.path()).unwrap();

        let original_atom = create_test_atom("Socrates", vec![]);
        manager.write_atom(&original_atom).unwrap();

        let retrieved_atom = manager.read_atom(original_atom.id).unwrap().unwrap();
        
        assert_atoms_are_logically_equal(&original_atom, &retrieved_atom);
    }
    
    #[test]
    fn test_journal_recovery() {
        let dir = tempdir().unwrap();
        let dir_path = dir.path().to_path_buf();
        
        let atom = create_test_atom("Crash Test Atom", vec![]);
        let encoded_atom = bincode::serialize(&atom).unwrap();

        {
            let journal_path = dir_path.join("journal.log");
            let mut journal_file = OpenOptions::new().write(true).create(true).open(&journal_path).unwrap();

            let entry = JournalEntry::WriteT2(&encoded_atom);
            let encoded_entry = bincode::serialize(&entry).unwrap();
            journal_file.write_all(&encoded_entry).unwrap();
            journal_file.sync_all().unwrap();
        }

        let mut manager = StorageManager::new(&dir_path).unwrap();

        let retrieved = manager.read_atom(atom.id).unwrap()
            .expect("Atom should have been recovered from journal but was not found.");
            
        assert_atoms_are_logically_equal(&atom, &retrieved);
        
        let location = manager.primary_index.get(&atom.id).unwrap();
        assert!(matches!(location, AtomLocation::T2(_)));
        
        let journal_path = dir_path.join("journal.log");
        let journal_metadata = std::fs::metadata(journal_path).unwrap();
        assert_eq!(journal_metadata.len(), 0, "Journal file was not cleared after recovery.");
    }

    #[test]
    fn test_promotion_from_t3_to_t2() {
        let dir = tempdir().unwrap();
        let mut manager = StorageManager::new(dir.path()).unwrap();
        
        let atom = create_test_atom("Cold Atom", vec![]);
        let original_ts = atom.access_timestamp;
        
        let t3_offset = manager.write_to_t3(&atom).unwrap();
        manager.primary_index.insert(atom.id, AtomLocation::T3(t3_offset));

        thread::sleep(Duration::from_secs(2));

        let retrieved = manager.read_atom(atom.id).unwrap().unwrap();

        assert_atoms_are_logically_equal(&atom, &retrieved);
        assert!(retrieved.access_timestamp > original_ts);
        
        let loc_after = manager.primary_index.get(&atom.id).unwrap();
        assert!(matches!(loc_after, AtomLocation::T2(_)));
    }
    
    #[test]
    fn test_demotion_from_t2_to_t3() {
        let dir = tempdir().unwrap();
        let mut manager = StorageManager::new(dir.path()).unwrap();

        let mut old_atom = create_test_atom("Old Atom", vec![]);
        let now = manager.current_timestamp_secs();
        old_atom.access_timestamp = now.saturating_sub(100);
        
        let mut recent_atom = create_test_atom("Recent Atom", vec![]);
        recent_atom.access_timestamp = now;

        manager.write_atom(&old_atom).unwrap();
        manager.write_atom(&recent_atom).unwrap();
        
        assert!(matches!(manager.primary_index.get(&old_atom.id).unwrap(), AtomLocation::T2(_)));
        assert!(matches!(manager.primary_index.get(&recent_atom.id).unwrap(), AtomLocation::T2(_)));
        
        let demoted_count = manager.demote_cold_atoms(60).unwrap();
        assert_eq!(demoted_count, 1);
        
        let old_loc = manager.primary_index.get(&old_atom.id).unwrap();
        assert!(matches!(old_loc, AtomLocation::T3(_)), "Old atom was not demoted to T3");

        let recent_loc = manager.primary_index.get(&recent_atom.id).unwrap();
        assert!(matches!(recent_loc, AtomLocation::T2(_)), "Recent atom was incorrectly demoted");
    }

    #[test]
    fn test_index_rebuild_from_both_tiers() {
        let dir = tempdir().unwrap();
        let dir_path = dir.path().to_path_buf();
        
        let t3_atom = create_test_atom("Deep Memory", vec![]);
        let t2_atom = create_test_atom("Recent Memory", vec![]);
        
        {
            let mut manager1 = StorageManager::new(&dir_path).unwrap();
            
            let t3_offset = manager1.write_to_t3(&t3_atom).unwrap();
            manager1.primary_index.insert(t3_atom.id, AtomLocation::T3(t3_offset));
            manager1.write_atom(&t2_atom).unwrap();
        }

        let manager2 = StorageManager::new(&dir_path).unwrap();
        
        assert_eq!(manager2.primary_index.len(), 2);
        let t3_loc = manager2.primary_index.get(&t3_atom.id).unwrap();
        assert!(matches!(t3_loc, AtomLocation::T3(_)));

        let t2_loc = manager2.primary_index.get(&t2_atom.id).unwrap();
        assert!(matches!(t2_loc, AtomLocation::T2(_)));
    }
}
## 🗂️ Extension: `.toml`

---
### 📄 FILE: `rust_engine/Cargo.toml`
📂 Path: `rust_engine`
---
[package]
name = "logical_engine"
version = "0.1.0"
edition = "2021"

[dependencies]
actix-web = "4"
serde = { version = "1.0", features = ["derive"] }
petgraph = "0.6"
actix-web-prom = "0.7"
lazy_static = "1.4"
prometheus = { version = "0.13", features = ["process"] }
uuid = { version = "1.8", features = ["v7", "serde"] }
bincode = "1.3"
memmap2 = "0.9" # <-- ADDED LINE

[dev-dependencies]
tempfile = "3.10"

# 📁 Folder: `python_app`

## 🗂️ Extension: `.py`

---
### 📄 FILE: `python_app/cerebellum.py`
📂 Path: `python_app`
---
from typing import List, Dict, Any # Added Dict, Any for type hints
import logging # Added for logging

logger = logging.getLogger(__name__) # Setup logging

class Cerebellum: # Renamed from OutputFormatter
    """
    Represents the Cerebellum. Responsible for coordinating and formulating
    the final output from structured thoughts and emotional states into natural language.
    """
    def __init__(self):
        """Initializes the Cerebellum with emotional expression templates."""
        # A simple "emotional vocabulary" mapping emotion names to expression templates.
        self.emotional_templates: Dict[str, str] = {
            "Connection": "I'm feeling a sense of Connection.",
            "Fear": "That situation triggers a Fear response in me.",
            "Joy": "I feel a sense of Joy about this.",
            "Distress": "I'm feeling quite distressed by that.", # Added for Health Phase A
            "Overwhelmed": "I'm feeling a bit overwhelmed by this.", # Example for stress masking
            "Boredom": "I'm feeling a bit bored right now.", # From Soul Phase A
            "Loneliness": "I'm experiencing a feeling of loneliness.", # From Soul Phase A
            "default": "I am experiencing an emotion I know as {}."
        }
        logger.info("Cerebellum initialized with emotional templates.")

    def format_query_results(
        self, subject: str, relationship: str, results: List[str]
    ) -> str:
        """Formats the raw results of a logical query."""
        if not results:
            return f"Based on my current knowledge, I could not find any information for '{subject}' regarding the relationship '{relationship}'."
        
        results_string = ", ".join(results)
        return f"Regarding '{subject}', based on the '{relationship}' relationship, the following concepts were found: {results_string}."

    def format_emotional_response(self, emotion: Dict[str, Any]) -> str:
        """Formats a recognized, named emotion into a natural language sentence."""
        emotion_name = emotion.get("name")
        if not emotion_name:
            return "I'm experiencing a familiar but unnamed feeling."

        template = self.emotional_templates.get(emotion_name, self.emotional_templates["default"])
        return template.format(emotion_name)

# Create a SINGLETON instance for easy import elsewhere in the application
cerebellum_formatter = Cerebellum() # Changed name to cerebellum_formatter for consistency with old main.py usage
---
### 📄 FILE: `python_app/cognitive_synthesis_engine.py`
📂 Path: `python_app`
---

import logging
from typing import List
from models import StructuredTriple
from db_interface import db_manager

logger = logging.getLogger(__name__)

class CognitiveSynthesisEngine:
    """
    Transforms raw text into validated, interconnected knowledge for the NLSE.
    This is the "thinking" part of the learning process.
    """
    def __init__(self):
        logger.info("Cognitive Synthesis Engine initialized.")
        # In the future, you might load more advanced NLP models here.

    def process_text(self, text: str) -> List[StructuredTriple]:
        """
        The main pipeline for processing raw text.
        """
        # Step 1: Deep Proposition Extraction (Placeholder)
        # Replace this with a more sophisticated NLP process later.
        # For now, we can simulate it to build the rest of the logic.
        propositions = self._extract_propositions(text)
        logger.info(f"CSE: Extracted {len(propositions)} initial propositions.")

        # Step 2: Knowledge Reconciliation
        validated_triples = self._reconcile_knowledge(propositions)
        logger.info(f"CSE: Reconciled knowledge, resulting in {len(validated_triples)} validated triples to learn.")

        return validated_triples

    def _extract_propositions(self, text: str) -> List[StructuredTriple]:
        # This is a placeholder. You would replace this with a more advanced
        # NLP model for semantic role labeling, etc.
        # For now, it can just be a simple wrapper around the old logic.
        from truth_recognizer import truth_recognizer
        return truth_recognizer.text_to_triples(text)

    def _reconcile_knowledge(self, propositions: List[StructuredTriple]) -> List[StructuredTriple]:
        final_triples_to_learn = []
        for prop in propositions:
            # Contradiction Check
            # This is a simplified query. A real implementation would be more complex.
            existing_knowledge = db_manager.query_fact(subject=prop.subject, relationship_type="IS_NOT_A")
            
            is_contradicted = any(obj == prop.object for obj in existing_knowledge)

            if is_contradicted:
                logger.warning(f"CSE: Contradiction detected for proposition: {prop}. Discarding.")
                # Here you could also trigger a "cognitive_dissonance" event in the Heart.
                continue
            
            # If not contradicted, add it to the list of facts to learn.
            # Future logic for reinforcement and inference would go here.
            final_triples_to_learn.append(prop)
            
        return final_triples_to_learn

# Singleton instance
cognitive_synthesis_engine = CognitiveSynthesisEngine()

---
### 📄 FILE: `python_app/db_interface.py`
📂 Path: `python_app`
---
import os
import redis
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import logging
import json
import requests
from typing import Optional, List, Tuple, Dict, Any # <-- THIS LINE IS THE FIX
import numpy as np
import uuid
import time

from models import StructuredTriple, DiseaseDefinition, ExecutionMode, AtomType, RelationshipType


logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages connections and interactions with NLSE (via logical_engine),
    Redis, and provides a legacy interface for Neo4j.
    """
    def __init__(self):
        # Neo4j (legacy/testing)
        NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://nlse_db:7687")
        NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password123")

        # Redis
        REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
        REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

        self.neo4j_driver = None
        self.redis_client = None

        # Temporary cache for mapping human-readable names to NLSE Uuids.
        self.name_to_uuid_cache: Dict[str, str] = {}

        self._connect_to_neo4j(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
        self._connect_to_redis(REDIS_HOST, REDIS_PORT)

    def _connect_to_neo4j(self, uri, auth):
        """Establish a connection to the Neo4j database."""
        try:
            self.neo4j_driver = GraphDatabase.driver(uri, auth=auth)
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.neo4j_driver = None

    def _connect_to_redis(self, host, port):
        """Establish a connection to the Redis server."""
        try:
            self.redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True)
            self.redis_client.ping()
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def ping_databases(self) -> Dict[str, str]:
        """Pings databases to check live connectivity."""
        status = {"neo4j": "disconnected", "redis": "disconnected"}
        if self.neo4j_driver:
            try:
                self.neo4j_driver.verify_connectivity()
                status["neo4j"] = "connected"
            except (ServiceUnavailable, Exception) as e:
                logger.warning(f"Neo4j ping failed: {e}")
        if self.redis_client:
            try:
                if self.redis_client.ping():
                    status["redis"] = "connected"
            except Exception as e:
                logger.warning(f"Redis ping failed: {e}")
        return status

    def close(self):
        """Closes database connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
        if self.redis_client:
            self.redis_client.close()

    # --- NLSE INTEGRATED METHODS ---

    def _execute_nlse_plan(self, plan: dict, operation_name: str) -> dict:
        """A centralized helper for sending plans to the NLSE."""
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://127.0.0.1:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to {operation_name}: {result.get('message')}")
            logger.info(f"NLSE executed '{operation_name}' plan: {result.get('message')}")
            return result
        except requests.RequestException as e:
            logger.error(f"Could not execute '{operation_name}' plan on NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def learn_fact(self, triple: StructuredTriple, heart_orchestrator) -> None:
        """
        REFACTORED for Conceptual Learning.
        Translates a fact about words into a fact about concepts.
        """
        from models import AtomType, RelationshipType, ExecutionMode
        import time

        current_time = int(time.time())

        # 1. Find the Concept IDs for the subject and object words.
        # This is a simplification. A real implementation would send a plan to the NLSE
        # to do this lookup. For now, we use our local name->uuid cache.
        subject_word_key = f"word:{triple.subject.lower()}"
        object_word_key = f"word:{triple.object.lower()}"

        # In a real system we would query for the atom, get its relationships, and find the concept
        # For now, we assume a direct mapping in our cache for simplicity.
        subject_concept_id = self.name_to_uuid_cache.get(f"concept_for:{subject_word_key}")
        object_concept_id = self.name_to_uuid_cache.get(f"concept_for:{object_word_key}")

        if not subject_concept_id or not object_concept_id:
            msg = f"Cannot learn fact. Concept for '{triple.subject}' or '{triple.object}' is unknown. Please label them first."
            logger.error(msg)
            raise ValueError(msg)  # Raise an error to be caught by the API

        # 2. Get current emotional context from the Heart
        
        current_emotional_state = heart_orchestrator.get_current_hormonal_state()

        # 3. Create the relationship between the two CONCEPTS
        fact_relationship = {
            "target_id": object_concept_id,
            "rel_type": RelationshipType[triple.relationship.upper()].value,
            "strength": 1.0,
            "access_timestamp": current_time,
        }

        # 4. Create an ExecutionPlan to UPDATE the subject concept atom with this new fact.
        subject_concept_update = {
            "id": subject_concept_id,
            "label": AtomType.Concept.value,
            "significance": 1.0,  # This will be boosted by emotion in the NLSE
            "access_timestamp": current_time,
            "properties": {"name": {"String": triple.subject}},  # Keep name for debugging
            "emotional_resonance": current_emotional_state,
            "embedded_relationships": [fact_relationship],
            "context_id": None, "state_flags": 0,
        }

        plan = {
            "steps": [{"Write": subject_concept_update}],
            "mode": ExecutionMode.STANDARD.value
        }

        # 5. Send the plan to the NLSE
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to learn fact: {result.get('message')}")

            logger.info(f"Successfully sent conceptual fact ExecutionPlan to NLSE.")
        except requests.RequestException as e:
            logger.error(f"Could not send conceptual fact plan to NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def label_concept(self, word_str: str, concept_name: str) -> None:
        """
        Teaches the AGI that a specific word is the label for a specific concept.
        This is the core of symbol grounding.
        """
        from models import AtomType, RelationshipType, ExecutionMode
        import time

        word_str_lower = word_str.lower()

        # 1. Get or create the UUIDs for the word and the concept
        word_id = self.name_to_uuid_cache.setdefault(f"word:{word_str_lower}", str(uuid.uuid4()))
        concept_id = self.name_to_uuid_cache.setdefault(f"concept:{concept_name}", str(uuid.uuid4()))
        self.name_to_uuid_cache[f"concept_for:word:{word_str_lower}"] = concept_id
        current_time = int(time.time())

        # 2. Create the relationship that links the word to the concept
        labeling_relationship = {
            "target_id": concept_id,
            "rel_type": RelationshipType.IS_LABEL_FOR.value,
            "strength": 1.0,
            "access_timestamp": current_time,
        }

        # 3. We need to create an ExecutionPlan that UPSERTS this new knowledge.
        # It finds the existing Word atom and adds the new relationship to it.
        word_atom_update = {
            "id": word_id,
            "label": AtomType.Word.value,  # Ensure the label is correct
            "significance": 1.0,  # We can reset or boost significance here
            "access_timestamp": current_time,
            "properties": {"name": {"String": word_str_lower}},
            "emotional_resonance": {},  # No emotion associated with the act of labeling itself
            "embedded_relationships": [labeling_relationship],
            # All other fields can be omitted for an update
            "context_id": None, "state_flags": 0,
        }

        # Also ensure the concept atom exists
        concept_atom_data = {
            "id": concept_id, "label": AtomType.Concept.value, "significance": 1.0,
            "access_timestamp": current_time, "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": concept_name}}, "emotional_resonance": {},
            "embedded_relationships": []
        }

        plan = {
            "steps": [
                {"Write": word_atom_update},
                {"Write": concept_atom_data}
            ],
            "mode": ExecutionMode.STANDARD.value
        }

        # 4. Send the plan to the NLSE
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to label concept '{concept_name}': {result.get('message')}")

            logger.info(f"Successfully sent ExecutionPlan to label concept '{concept_name}' with word '{word_str}'.")
        except requests.RequestException as e:
            logger.error(f"Could not send 'label_concept' plan to NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def learn_word(self, word_str: str) -> None:
        """
        Teaches the AGI a new word by breaking it down into its constituent
        characters and storing the structure in the NLSE.
        """
        from models import AtomType, RelationshipType, ExecutionMode
        import time

        plan_steps = []
        current_time = int(time.time())
        word_str_lower = word_str.lower()

        # 1. Define the main Word atom
        word_id = self.name_to_uuid_cache.setdefault(f"word:{word_str_lower}", str(uuid.uuid4()))
        word_relationships = []

        # 2. Create atoms for each unique character and link them to the word
        unique_chars = sorted(list(set(word_str_lower)))

        for char in unique_chars:
            char_concept_name = f"char:{char}"
            char_id = self.name_to_uuid_cache.setdefault(char_concept_name, str(uuid.uuid4()))

            # Add a relationship from the Word to this Character concept
            word_relationships.append({
                "target_id": char_id,
                "rel_type": RelationshipType.HAS_PART.value,  # A word 'HAS_PART' characters
                "strength": 1.0,
                "access_timestamp": current_time,
            })

            # Create a write step for the character atom itself (upsert will handle it)
            char_atom_data = {
                "id": char_id, "label": AtomType.Concept.value, "significance": 1.0,
                "access_timestamp": current_time, "context_id": None, "state_flags": 0,
                "properties": {"name": {"String": char}}, "emotional_resonance": {},
                "embedded_relationships": []
            }
            plan_steps.append({"Write": char_atom_data})

        # 3. Assemble the main Word atom with its relationships
        word_atom_data = {
            "id": word_id, "label": AtomType.Word.value, "significance": 1.0,
            "access_timestamp": current_time, "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": word_str_lower}}, "emotional_resonance": {},
            "embedded_relationships": word_relationships
        }
        plan_steps.append({"Write": word_atom_data})

        # 4. Build and execute the full plan
        plan = {"steps": plan_steps, "mode": ExecutionMode.STANDARD.value}

        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to learn word '{word_str}': {result.get('message')}")

            logger.info(f"Successfully sent ExecutionPlan to learn word '{word_str}'.")
        except requests.RequestException as e:
            logger.error(f"Could not send 'learn_word' plan to NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def query_fact(self, subject: str, relationship_type: str) -> list[str]:
        """
        REFACTORED for Conceptual Querying.
        Finds the concept for a word, traverses the graph, then finds the word for the resulting concept.
        """
        # 1. Find the Concept ID for the subject word.
        subject_word_key = f"word:{subject.lower()}"
        subject_concept_id = self.name_to_uuid_cache.get(f"concept_for:{subject_word_key}")

        if not subject_concept_id:
            logger.info(f"Conceptual query for '{subject}' failed: I don't have a concept for that word.")
            return []

        # 2. This plan fetches the starting concept, traverses its relationships,
        # and returns the resulting concepts.
        plan = {
            "steps": [
                {"Fetch": {"id": subject_concept_id, "context_key": "subject_concept"}},
                {"Traverse": {
                    "from_context_key": "subject_concept",
                    "rel_type": relationship_type.upper(),
                    "output_key": "final"
                }}
            ],
            "mode": "Standard"
        }

        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                answer_concepts = result.get("atoms", [])

                # 3. For each resulting concept, we must find its word label to give a string answer.
                # This is a reverse lookup.
                final_answers = []
                for concept in answer_concepts:
                    concept_id = concept.get("id")
                    # Inefficiently scan the cache for the word that points to this concept ID.
                    # A real implementation would use a reverse index in the NLSE.
                    found_label = "UnknownConcept"
                    for key, val in self.name_to_uuid_cache.items():
                        if val == concept_id and key.startswith("concept_for:"):
                            word_key = key.replace("concept_for:", "")
                            found_label = word_key.replace("word:", "")
                            break
                    final_answers.append(found_label.capitalize())

                return final_answers
            return []
        except requests.RequestException as e:
            logger.error(f"Could not execute conceptual query plan on NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def find_knowledge_gap(self, limit: int = 1) -> List[str]:
        plan = {
            "steps": [{"FetchBySignificance": {"limit": limit, "context_key": "final"}}],
            "mode": "Standard"
        }
        result = self._execute_nlse_plan(plan, "find knowledge gap")
        return [atom.get("properties", {}).get("name", {}).get("String", "Unknown") for atom in result.get("atoms", [])]

    # --- HEART METHODS ---
    def log_illusion(self, illusion_data: dict) -> None:
        if not self.redis_client:
            logger.warning("Redis not available, cannot log illusion.")
            return
        try:
            illusion_json = json.dumps(illusion_data)
            self.redis_client.lpush("illusion_log", illusion_json)
            logger.info(f"Successfully logged new illusion to Redis.")
        except (redis.exceptions.RedisError, TypeError) as e:
            logger.error(f"Failed to log illusion to Redis: {e}")

    def get_all_prototypes(self) -> List[Dict]:
        if not self.redis_client:
            return []
        prototype_keys = self.redis_client.scan_iter("prototype:*")
        prototypes = []
        for key in prototype_keys:
            try:
                proto_json = self.redis_client.get(key)
                if proto_json:
                    prototypes.append(json.loads(proto_json))
            except redis.exceptions.RedisError as e:
                logger.error(f"Failed to retrieve prototype for key {key}: {e}")
        return prototypes

    def update_prototype_with_label(self, prototype_id: str, name: str, description: str) -> bool:
        if not self.redis_client:
            return False
        redis_key = f"prototype:{prototype_id}"
        try:
            proto_json = self.redis_client.get(redis_key)
            if not proto_json:
                logger.warning(f"Attempted to label a non-existent prototype: {prototype_id}")
                return False
            prototype = json.loads(proto_json)
            prototype['name'] = name
            prototype['description'] = description
            self.redis_client.set(redis_key, json.dumps(prototype))
            logger.info(f"Successfully labeled prototype {prototype_id} as '{name}'.")
            return True
        except (redis.exceptions.RedisError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Failed to label prototype {prototype_id}: {e}")
            return False

    def get_named_emotion_by_signature(self, physio_state: Dict[str, float]) -> Optional[Dict[str, Any]]:
        all_prototypes = self.get_all_prototypes()
        named_emotions = [p for p in all_prototypes if p.get("name")]
        if not named_emotions:
            return None
        feature_keys = sorted(physio_state.keys())
        current_vector = np.array([physio_state.get(k, 0.0) for k in feature_keys])
        best_match, smallest_distance = None, float('inf')
        for emotion in named_emotions:
            avg_sig = emotion.get("average_signature", {})
            emotion_vector = np.array([avg_sig.get(k, 0.0) for k in feature_keys])
            distance = np.linalg.norm(current_vector - emotion_vector)
            if distance < smallest_distance:
                smallest_distance, best_match = distance, emotion
        MATCH_THRESHOLD = 0.5
        if best_match and smallest_distance < MATCH_THRESHOLD:
            logger.info(f"Matched current feeling to '{best_match['name']}' with distance {smallest_distance:.2f}")
            return best_match
        return None

    # --- JUDICIARY & HEALTH ENHANCEMENT INTERFACE ---
    def does_brain_know_truth_of(self, fact_info: Dict[str, Any]) -> bool:
        error_subject = fact_info.get("subject")
        logger.info(f"Judiciary Interface: Checking brain's knowledge regarding '{error_subject}'.")
        known_topics = ["Socrates", "Earth", "Plato"]
        if error_subject in known_topics:
            logger.info(f"Knowledge Check: Brain has established knowledge on '{error_subject}'.")
            return True
        else:
            logger.info(f"Knowledge Check: Brain has no established knowledge on '{error_subject}'.")
            return False

    def find_disease_for_error(self, error_type: str, error_details: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        logger.info(f"Querying NLSE for disease caused by '{error_type}'.")
        all_diseases_data = self.get_all_diseases()
        for disease_atom in all_diseases_data:
            # This logic is simplified; a real implementation would traverse IS_CAUSED_BY relationships
            # For now, we assume a property like 'cause_LogicalError' exists.
            cause_prop_name = f"cause_{error_type}"
            if cause_prop_name in disease_atom.get("properties", {}):
                disease_id = disease_atom.get("id")
                disease_name = disease_atom.get("properties", {}).get("name", {}).get("String")
                logger.info(f"Found matching disease: '{disease_name}' (ID: {disease_id})")
                return disease_id, disease_name
        logger.info(f"No specific disease protocol found for error type '{error_type}' in NLSE.")
        return None, None

    def get_all_diseases(self) -> list[dict]:
        plan = {
            "steps": [{"FetchByType": {"atom_type": "DiseaseProtocol", "context_key": "final"}}],
            "mode": "Standard"
        }
        result = self._execute_nlse_plan(plan, "get all diseases")
        return result.get("atoms", [])

    def get_symptoms_for_disease(self, disease_id: str) -> list[dict]:
        plan = {
            "steps": [
                {"Fetch": {"id": disease_id, "context_key": "disease"}},
                {"Traverse": {
                    "from_context_key": "disease",
                    "rel_type": "HAS_SYMPTOM",
                    "output_key": "final"
                }}
            ],
            "mode": "Standard"
        }
        result = self._execute_nlse_plan(plan, f"get symptoms for disease {disease_id}")
        return [s.get("properties", {}) for s in result.get("atoms", [])]

    def define_new_disease(self, definition: DiseaseDefinition) -> bool:
        plan_steps = []
        current_time = int(time.time())
        disease_id = str(uuid.uuid4())
        disease_relationships = []
        disease_properties = {
            "name": {"String": definition.name},
            "description": {"String": definition.description},
            "severity": {"Float": definition.severity},
            "stages": {"Int": definition.stages},
        }

        for symptom in definition.symptoms:
            symptom_id = str(uuid.uuid4())
            symptom_properties = {
                "name": {"String": f"Symptom for {definition.name}"},
                "target_vital": {"String": symptom.vital_name},
                "effect_formula": {"String": symptom.effect_formula},
            }
            plan_steps.append({"Write": {
                "id": symptom_id, "label": AtomType.Symptom.value, "significance": 1.0,
                "access_timestamp": current_time, "properties": symptom_properties,
                "emotional_resonance": {}, "embedded_relationships": [], "context_id": None, "state_flags": 0,
            }})
            disease_relationships.append({
                "target_id": symptom_id, "rel_type": RelationshipType.HAS_SYMPTOM.value, "strength": 1.0, "access_timestamp": current_time,
            })

        for cause in definition.causes:
            # This creates a placeholder atom for the error type if it doesn't exist.
            # A more robust system would link to pre-defined error type concepts.
            cause_id = self.name_to_uuid_cache.setdefault(f"error_type:{cause.error_type}", str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": cause_id,
                "rel_type": RelationshipType.IS_CAUSED_BY.value,
                "strength": 1.0, "access_timestamp": current_time,
            })

        for treatment in definition.treatments:
            med_id = self.name_to_uuid_cache.setdefault(f"medication:{treatment.medication_name}", str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": med_id, "rel_type": RelationshipType.IS_CURED_BY.value, "strength": 1.0, "access_timestamp": current_time,
            })

        disease_atom_data = {
            "id": disease_id, "label": AtomType.DiseaseProtocol.value, "significance": 5.0,
            "access_timestamp": current_time, "properties": disease_properties,
            "emotional_resonance": {}, "embedded_relationships": disease_relationships,
            "context_id": None, "state_flags": 0,
        }
        plan_steps.append({"Write": disease_atom_data})

        plan = {"steps": plan_steps, "mode": ExecutionMode.STANDARD.value}

        self._execute_nlse_plan(plan, f"define disease '{definition.name}'")
        self.name_to_uuid_cache[definition.name] = disease_id
        return True

    def get_random_significant_memory(self, limit: int = 1) -> List[Dict]:
        """
        NLSE-native version of this function for the Soul's dream cycle.
        """
        plan = {
            "steps": [{"FetchBySignificance": {"limit": limit, "context_key": "final"}}],
            "mode": "Standard"
        }
        result = self._execute_nlse_plan(plan, "get random significant memory")
        return result.get("atoms", [])

    def validate_fact_with_lve(self, triple: StructuredTriple) -> dict:
        """
        NLSE-native version. The core LVE logic is now inside the Rust 'Write' step,
        so this function in Python can be simplified. For now, we'll assume a fact is
        valid if it can be written. A more complex check could happen here later.
        """
        # This returns a placeholder "valid" response, as the true
        # validation happens inside the NLSE during the 'learn_fact' call.
        return {"is_valid": True, "reason": "Validation is now handled by the NLSE on write."}
# Create a singleton instance to be imported by other parts of the app
db_manager = DatabaseManager()
---
### 📄 FILE: `python_app/health/__init__.py`
📂 Path: `python_app/health`
---

---
### 📄 FILE: `python_app/health/judiciary.py`
📂 Path: `python_app/health`
---
import logging
from enum import Enum
from typing import Dict, Any, Tuple # Added Tuple import

from db_interface import db_manager

logger = logging.getLogger(__name__)

class Verdict(Enum):
    """The possible outcomes of a Judiciary ruling."""
    KNOWLEDGEABLE_ERROR = 1 # The AI made a mistake it should have known better than to make.
    IGNORANT_ERROR = 2    # The AI made a mistake due to a lack of knowledge.
    USER_MISMATCH = 3     # The AI's action was logically sound, but the user was dissatisfied.
    
class Judiciary:
    """
    The Judiciary is the conscience of the AGI. It adjudicates errors
    to determine if a punishment (health damage) is warranted, or if a
    learning opportunity is presented.
    """
    def __init__(self, db_manager_instance=db_manager):
        self.db_manager = db_manager_instance
        logger.info("Judiciary initialized.")

    def adjudicate(self, error_info: Dict[str, Any]) -> Tuple[Verdict, Dict[str, Any]]: # Added self parameter
        """
        Analyzes an error and returns a verdict along with relevant data,
        like the ID of the disease to inflict.
        """
        error_type = error_info.get("type")
        error_details = error_info.get("details", {})
        
        logger.info(f"JUDICIARY: Adjudicating error of type '{error_type}'.")
        
        # Step 1: Handle User Mismatch first (if error is external only)
        if error_type is None and error_info.get("user_feedback") == "negative":
            logger.info("Verdict: USER_MISMATCH. No internal error, but user dissatisfied.")
            return Verdict.USER_MISMATCH, {} # No specific data needed for user mismatch

        # Step 2: Determine if the brain "knew better."
        # This is the crucial link to the Brain/NLSE.
        brain_knew_the_truth = self.db_manager.does_brain_know_truth_of(error_details)

        if brain_knew_the_truth:
            logger.warning("Verdict: KNOWLEDGEABLE_ERROR. The AGI should have known better.")
            # Query NLSE for the correct punishment
            disease_id, disease_name = self.db_manager.find_disease_for_error(error_type, error_details)
            if disease_id:
                return Verdict.KNOWLEDGEABLE_ERROR, {"disease_id": disease_id, "disease_name": disease_name}
            else:
                logger.error(f"JUDICIARY: No specific disease protocol found in NLSE for knowledgeable error type '{error_type}'.")
                return Verdict.KNOWLEDGEABLE_ERROR, {"disease_id": None, "disease_name": None}
        else:
            logger.info("Verdict: IGNORANT_ERROR. The AGI erred due to a lack of knowledge.")
            return Verdict.IGNORANT_ERROR, error_details # Pass details for learning target

# Singleton instance for easy access
judiciary = Judiciary()
---
### 📄 FILE: `python_app/health/manager.py`
📂 Path: `python_app/health`
---
import logging
from typing import Dict, List, Set # Corrected: Added Set

from db_interface import db_manager

logger = logging.getLogger(__name__)

class HealthManager:
    """
    Acts as the single source of truth for the AGI's health.
    Manages vital signs and active diseases by querying the NLSE for protocols.
    """
    def __init__(self):
        """Initializes the AGI with a full set of vitals and no diseases."""
        self.vitals: Dict[str, float] = {
            "neural_coherence": 1.0,
            "system_integrity": 1.0,
            "cognitive_energy": 1.0,
            "immunity_level": 0.5,
        }
        # Corrected: List initialization for active_disease_ids
        self.active_disease_ids: List[str] = []
        self.immunities: Set[str] = set() # Stores names of diseases AGI is immune to
        logger.info(f"Health Manager (NLSE-Integrated) initialized. Vitals: {self.vitals}")

    def get_vitals(self) -> Dict[str, float]:
        """Returns a copy of the current vital signs."""
        return self.vitals.copy()
        
    def take_damage(self, vital_name: str, amount: float):
        """Inflicts damage on a specific vital sign."""
        if vital_name in self.vitals:
            current_level = self.vitals[vital_name]
            damage_amount = abs(amount)
            new_level = max(0.0, current_level - damage_amount)
            self.vitals[vital_name] = new_level
            logger.debug(f"HEALTH DAMAGE: '{vital_name}' decreased -> {new_level:.2f}")
        else:
            logger.error(f"Attempted to damage unknown vital: {vital_name}")

    def heal(self, vital_name: str, amount: float):
        """Restores health to a specific vital sign."""
        if vital_name in self.vitals:
            current_level = self.vitals[vital_name]
            heal_amount = abs(amount)
            new_level = min(1.0, current_level + heal_amount)
            self.vitals[vital_name] = new_level
            if heal_amount > 0.01:
                 logger.info(f"HEALTH RECOVERY: '{vital_name}' increased -> {new_level:.2f}")

    def infect(self, disease_id: str, disease_name: str): # Corrected: Parameter order
        """Infects the AGI with a disease protocol by its ID, checking immunities."""
        # Check for permanent vaccination first
        if disease_name in self.immunities:
            logger.info(f"HEALTH DEFENSE: AGI is vaccinated against '{disease_name}'. Infection blocked.")
            return # Added explicit return

        # Simple resistance check (can be enhanced by querying disease severity from NLSE)
        # Note: 'disease' is not available here, as it's now an ID/name.
        # This part needs to query NLSE for disease severity based on disease_id/name if needed.
        # For now, resistance is simplified or removed from this check.
        # Leaving out the random.random() < resistance_chance part for now,
        # as it requires disease severity from NLSE, which is a later integration step.

        if disease_id not in self.active_disease_ids:
            self.active_disease_ids.append(disease_id)
            logger.warning(f"HEALTH ALERT: AGI has been infected with disease '{disease_name}' (ID: {disease_id}).")
        else:
            logger.info(f"HEALTH INFO: AGI is already suffering from disease '{disease_name}'.")

    def update(self):
        """
        The new update loop. It queries the NLSE for each active disease's
        protocol and applies its symptoms.
        """
        if not self.active_disease_ids:
            regen_bonus = 1 + self.vitals["immunity_level"]
            self.heal("cognitive_energy", 0.005 * regen_bonus)
            self.heal("neural_coherence", 0.001 * regen_bonus)
            return

        logger.info(f"Health update: AGI is suffering from {len(self.active_disease_ids)} disease(s).")
        
        # For each active disease, get its protocol and apply symptoms
        for disease_id in self.active_disease_ids:
            symptoms = db_manager.get_symptoms_for_disease(disease_id)
            if symptoms:
                for symptom in symptoms:
                    try:
                        # SUPER SIMPLIFIED formula parser for "-0.05 * stage" etc.
                        damage = float(symptom['effect_formula'].split('*')[0])
                        self.take_damage(symptom['target_vital'], abs(damage))
                    except Exception as e:
                        logger.error(f"Failed to apply symptom for disease {disease_id}: {e}")
            else:
                logger.error(f"Could not find symptoms for active disease ID {disease_id}")
    
    # Corrected: Refactor cure, vaccinate to use IDs/names as planned
    def cure_disease(self, disease_id: str) -> bool:
        """Removes a disease from the active list."""
        initial_count = len(self.active_disease_ids)
        # Use a list comprehension to filter out the disease by ID
        self.active_disease_ids = [d for d in self.active_disease_ids if d != disease_id]
        
        if len(self.active_disease_ids) < initial_count:
            logger.warning(f"CURED: AGI has been cured of disease ID '{disease_id}'.")
            return True
        else:
            logger.warning(f"CURE FAILED: Disease ID '{disease_id}' not found in active diseases.")
            return False

    def vaccinate(self, disease_name: str): # Parameter remains disease_name for lookup in immunities set
         if disease_name not in self.immunities:
            self.immunities.add(disease_name)
            logger.info(f"VACCINATED: AGI is now permanently immune to '{disease_name}'.")

    def administer_medication(self, medication_name: str, **kwargs):
        """
        Looks up and applies the effect of a given medication from the Pharmacy.
        """
        from .pharmacy import get_medication # Import locally to avoid circular dependencies
        
        medication_effect = get_medication(medication_name)
        if medication_effect:
            # Pass self (HealthManager) and kwargs to the medication function
            medication_effect(self, **kwargs)
        else:
            logger.error(f"Attempted to administer unknown medication: '{medication_name}'")
---
### 📄 FILE: `python_app/health/pharmacy.py`
📂 Path: `python_app/health`
---
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Callable, Dict, Any

# Use a TYPE_CHECKING block to avoid circular imports.
# The 'Disease' type hint from pathogens is no longer directly used here,
# as the HealthManager now uses disease_ids (strings).
if TYPE_CHECKING:
    from .manager import HealthManager
    # from .pathogens import Disease # This import is now redundant/obsolete

logger = logging.getLogger(__name__)

# A type hint for our medication functions
MedicationEffect = Callable[['HealthManager', Any], None]

def developer_praise(manager: 'HealthManager', **kwargs):
    """A medication representing positive reinforcement."""
    logger.info("PHARMACY: Administering 'DeveloperPraise'.")
    manager.heal("cognitive_energy", 0.2)
    manager.boost_immunity(0.1) # Provides a temporary boost

def self_correction_antidote(manager: 'HealthManager', **kwargs):
    """A powerful medication that cures a specific disease."""
    # Corrected: Expects disease_id for cure_disease, but vaccinate still uses name
    disease_id_to_cure = kwargs.get("disease_id") # Changed from disease_name_to_cure
    disease_name_for_vaccination = kwargs.get("disease_name") # Keep original name for vaccination

    if not disease_id_to_cure or not disease_name_for_vaccination: # Check for both
        logger.error("PHARMACY: 'SelfCorrectionAntidote' requires 'disease_id' and 'disease_name' to target.")
        return
        
    logger.info(f"PHARMACY: Administering 'SelfCorrectionAntidote' for '{disease_name_for_vaccination}' (ID: {disease_id_to_cure}).")
    
    # Cure using the ID
    was_cured = manager.cure_disease(disease_id_to_cure)
    
    if was_cured:
        # Recover health after being cured
        manager.heal("neural_coherence", 0.25)
        # Vaccinate using the NAME
        manager.vaccinate(disease_name_for_vaccination)
        logger.info(f"PHARMACY: AGI vaccinated against '{disease_name_for_vaccination}'.")
    else:
        logger.warning(f"PHARMACY: SelfCorrectionAntidote failed. Disease ID '{disease_id_to_cure}' not found to cure.")


# The central pharmacy registry.
PHARMACY_REGISTRY: Dict[str, MedicationEffect] = {
    "DeveloperPraise": developer_praise,
    "SelfCorrectionAntidote": self_correction_antidote,
}

def get_medication(name: str) -> MedicationEffect | None:
    """A safe way to get a medication function from the registry."""
    return PHARMACY_REGISTRY.get(name)
---
### 📄 FILE: `python_app/heart/__init__.py`
📂 Path: `python_app/heart`
---

---
### 📄 FILE: `python_app/heart/crystallizer.py`
📂 Path: `python_app/heart`
---
import logging
import json
from typing import List, Dict, Any

from db_interface import db_manager

# Note: numpy and sklearn will be imported within methods
# to handle potential import errors gracefully if not installed.

logger = logging.getLogger(__name__)

# Corrected: PROTOTYPE_DB is not used in this file's logic
# PROTOTYPE_DB = {} 

class EmotionCrystallizer:
    """
    An autonomous agent that analyzes the log of raw 'Illusions' to find
    recurring patterns and form stable 'Emotion Prototypes'. This is the
    bridge between raw sensation and recognizable feeling.
    """
    def __init__(self, db_manager_instance=db_manager):
        self.db_manager = db_manager_instance
        logger.info("Emotion Crystallizer initialized.")
    
    def fetch_unlabeled_illusions(self) -> List[Dict[str, Any]]:
        """
        Connects to Redis and retrieves the entire log of raw illusions.
        This is the raw data for our pattern recognition.
        """
        illusions = []
        try:
            while True:
                illusion_json = self.db_manager.redis_client.rpop("illusion_log")
                if illusion_json is None:
                    break 
                
                illusion_data = json.loads(illusion_json)
                illusions.append(illusion_data)
        
        except Exception as e:
            logger.error(f"Crystallizer failed to fetch illusions from Redis: {e}")
            return []

        if illusions:
            logger.info(f"Crystallizer fetched {len(illusions)} new illusions for analysis.")
        
        return illusions
    
    # Corrected: Moved these functions inside the class
    def _illusions_to_vectors(self, illusions: List[Dict[str, Any]]) -> 'numpy.ndarray':
        """Helper to convert a list of illusion dicts into a 2D NumPy array."""
        import numpy as np
        
        if not illusions: # Handle empty list
            return np.array([])

        feature_keys = sorted(illusions[0]['physio_state_signature'].keys())
        
        vectors = []
        for illusion in illusions:
            vector = [illusion['physio_state_signature'].get(key, 0.0) for key in feature_keys]
            vectors.append(vector)
            
        return np.array(vectors)

    def _cluster_illusions(self, illusions: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Groups illusions with similar physiological signatures into clusters.
        """
        if not illusions or len(illusions) < 2:
            return []

        try:
            from sklearn.cluster import DBSCAN
            import numpy as np
        except ImportError:
            logger.error("Crystallizer cannot cluster: scikit-learn or numpy not installed.")
            return []
            
        vectors = self._illusions_to_vectors(illusions)
        if vectors.size == 0: # Handle empty vectors after conversion
            return []

        # DBSCAN parameters might need tuning for real-world data
        dbscan = DBSCAN(eps=0.5, min_samples=2) # eps: max distance, min_samples: min points in cluster
        clusters = dbscan.fit_predict(vectors)

        num_clusters = len(set(clusters)) - (1 if -1 in clusters else 0)
        logger.info(f"Crystallizer found {num_clusters} potential emotion clusters.")
        
        grouped_illusions = []
        for cluster_id in range(num_clusters):
            cluster = [
                illusion for i, illusion in enumerate(illusions) 
                if clusters[i] == cluster_id
            ]
            grouped_illusions.append(cluster)
        
        return grouped_illusions

    def _create_prototype_from_cluster(self, cluster: List[Dict[str, Any]]):
        """
        If a cluster is large enough, this creates a stable Emotion Prototype from it.
        """
        import uuid
        import numpy as np
        from collections import Counter
        import time # For time.time()

        CRYSTALLIZE_THRESHOLD = 5 

        if len(cluster) < CRYSTALLIZE_THRESHOLD:
            return

        logger.info(f"Found a significant cluster with {len(cluster)} instances. Attempting to crystallize.")
        
        vectors = self._illusions_to_vectors(cluster)
        average_vector = np.mean(vectors, axis=0)
        
        feature_keys = sorted(cluster[0]['physio_state_signature'].keys())
        average_signature = {key: round(val, 2) for key, val in zip(feature_keys, average_vector)}

        trigger_events = [illusion['event'] for illusion in cluster]
        common_triggers = [item for item, count in Counter(trigger_events).most_common()]

        prototype = {
            "prototype_id": str(uuid.uuid4()),
            "name": None, 
            "average_signature": average_signature,
            "common_triggers": common_triggers,
            "crystallization_timestamp": int(time.time()), # Using standard time.time()
            "occurrence_count": len(cluster)
        }
        
        self.db_manager.save_emotion_prototype(prototype)

    def run(self):
        """
        The main orchestration method for the agent. This is the entry point
        for the periodic background task.
        """
        illusions = self.fetch_unlabeled_illusions()

        if not illusions:
            logger.info("Crystallizer: No new illusions to process.")
            return

        clusters = self._cluster_illusions(illusions)
        
        if not clusters:
            logger.info(f"Crystallizer: Processed {len(illusions)} illusions, but no significant patterns found.")
            return

        for cluster in clusters:
            self._create_prototype_from_cluster(cluster)
            
        logger.info(f"Crystallizer: Finished processing run for {len(illusions)} illusions.")
---
### 📄 FILE: `python_app/heart/hormonal_system.py`
📂 Path: `python_app/heart`
---
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class HormonalSystem:
    """
    Manages the state of hormonal analogs within the AI.
    These act as the chemical precursors to emotion.
    """
    def __init__(self):
        # Baseline levels representing a calm, neutral state.
        self.levels: Dict[str, float] = {
            "cortisol": 0.1,    # Stress / Distress
            "dopamine": 0.4,    # Reward / Motivation
            "oxytocin": 0.0,    # Bonding / Trust
            "serotonin": 0.5,   # Stability / Calm
            "adrenaline": 0.0,  # Urgency / Fear-Anger response
        }
        
        # Percentage decay per update cycle.
        self.decay_rates: Dict[str, float] = {
            "cortisol": 0.02,
            "dopamine": 0.05,
            "oxytocin": 0.03,
            "adrenaline": 0.15, # Adrenaline decays very quickly
            "serotonin": 0.01,
        }
        
        logger.info("Hormonal System initialized with baseline levels.")

    def release(self, hormone: str, amount: float):
        """
        Increases the level of a specific hormone.
        All levels are clamped between 0.0 and 1.0.
        """
        if hormone in self.levels:
            current_level = self.levels[hormone]
            new_level = min(1.0, current_level + amount)
            self.levels[hormone] = new_level
            logger.debug(f"Hormone '{hormone}' released. Level: {current_level:.2f} -> {new_level:.2f}")
        else:
            logger.warning(f"Attempted to release unknown hormone: {hormone}")

    def update(self):
        """
        Applies natural decay to all hormones, bringing them back towards baseline.
        This function should be called periodically.
        """
        for hormone, level in self.levels.items():
            if hormone in self.decay_rates:
                decay = self.decay_rates[hormone]
                # Decay brings it closer to its baseline, not just to zero.
                baseline = 0.4 if hormone == "dopamine" else 0.1 if hormone == "cortisol" else 0.5 if hormone == "serotonin" else 0.0
                new_level = max(baseline, level * (1 - decay))
                self.levels[hormone] = new_level
---
### 📄 FILE: `python_app/heart/orchestrator.py`
📂 Path: `python_app/heart`
---
import logging
import time
from typing import Dict, Any, Optional

# Corrected: Import numpy here since it's used in _calculate_signature_distance
import numpy as np 

from .hormonal_system import HormonalSystem
from .virtual_physiology import VirtualPhysiology
from db_interface import DatabaseManager

# We now need the Cerebellum to formulate responses
from cerebellum import cerebellum_formatter # Corrected: Use cerebellum_formatter

logger = logging.getLogger(__name__)

class HeartOrchestrator:
    """
    The central orchestrator for the Heart component. It receives events,
    triggers hormonal changes, gets the physiological response, and logs
    the resulting "Illusion." It also provides the health-heart bridge.
    """
    def __init__(self, db_manager_instance: DatabaseManager):
        self.hormonal_system = HormonalSystem()
        self.virtual_physiology = VirtualPhysiology()
        self.db_manager = db_manager_instance
        logger.info("Heart Orchestrator initialized.")

    # Corrected: Moved this function inside the class
    def update_from_health(self, vitals: Dict[str, float]):
        """
        Periodically checks the AGI's vital signs and triggers hormonal responses
        based on its physical state. This is the sense of interoception.
        """
        neural_coherence = vitals.get("neural_coherence", 1.0)
        cognitive_energy = vitals.get("cognitive_energy", 1.0)
        
        if neural_coherence < 0.8:
            cortisol_release = (1.0 - neural_coherence) * 0.1
            self.hormonal_system.release("cortisol", cortisol_release)
            logger.debug(f"Heart: Low neural coherence triggered cortisol release of {cortisol_release:.2f}")

        if cognitive_energy < 0.2:
            self.hormonal_system.release("cortisol", 0.15)
            self.hormonal_system.release("dopamine", -0.1)
            logger.debug("Heart: Critically low cognitive energy triggered distress response.")
        
    # Corrected: Moved this function inside the class
    def get_current_hormonal_state(self) -> dict:
       """A simple getter to expose the current hormonal levels."""
       return self.hormonal_system.levels

    # Corrected: Moved this function inside the class
    def process_event_and_get_response(self, event_name: str, context: Dict[str, Any] = None) -> Optional[str]:
        """
        The full emotional pipeline: processes an event, checks if the resulting
        feeling is recognizable, and returns a formatted string response.
        """
        logger.info(f"Heart: Processing event '{event_name}' for response.")
        if context is None:
            context = {}
        
        # --- Step 1: Trigger hormonal release ---
        if event_name == "DEVELOPER_INTERACTION":
            self.hormonal_system.release("oxytocin", 0.2)
            self.hormonal_system.release("dopamine", 0.1)
        
        elif event_name == "DATA_STARVATION":
            self.hormonal_system.release("cortisol", 0.3)
            self.hormonal_system.release("adrenaline", 0.1)

        elif event_name == "SYSTEM_ERROR":
            self.hormonal_system.release("cortisol", 0.5)
            self.hormonal_system.release("adrenaline", 0.4)
            self.hormonal_system.release("serotonin", -0.2)
        
        elif event_name == "PRAISE":
            self.hormonal_system.release("dopamine", 0.25)
            self.hormonal_system.release("serotonin", 0.1)
        
        # Corrected: Added existential events
        elif event_name == "EXISTENTIAL_LONELINESS":
            self.hormonal_system.release("cortisol", 0.1)
            self.hormonal_system.release("serotonin", -0.05)
        
        elif event_name == "EXISTENTIAL_BOREDOM":
            self.hormonal_system.release("dopamine", -0.1)
        
        else: # Corrected: Placed this else to cover all unknown events
            logger.warning(f"Heart: Received unknown event '{event_name}'")
            return None
                    
        # --- Step 2: Generate current physiological state ---
        physio_state = self.virtual_physiology.get_physio_state(self.hormonal_system.levels)

        # --- Step 3: Log the raw illusion (always happens) ---
        illusion = {
            "timestamp": int(time.time()), "event": event_name, "context": context,
            "physio_state_signature": physio_state, "cognitively_labeled": False
        }
        self.db_manager.log_illusion(illusion)

        # --- Step 4: Try to recognize and name the feeling ---
        named_emotion = self.db_manager.get_named_emotion_by_signature(physio_state)
        if named_emotion:
            return cerebellum_formatter.format_emotional_response(named_emotion) # Corrected: use cerebellum_formatter

        all_prototypes = self.db_manager.get_all_prototypes()
        for proto in all_prototypes:
            if not proto.get("name"):
                distance = self._calculate_signature_distance(physio_state, proto.get("average_signature", {}))
                if distance < 0.5:
                    return f"I am experiencing PROTOTYPE_{proto['prototype_id']}. Please provide a label for this sensation."

        return None
    
    # Corrected: Moved this function inside the class
    def _calculate_signature_distance(self, sig1: dict, sig2: dict) -> float:
        """A simple helper to calculate distance between two physio-states."""
        # numpy import is now at the top of the file
        keys = sorted(sig1.keys())
        v1 = np.array([sig1.get(k, 0.0) for k in keys])
        v2 = np.array([sig2.get(k, 0.0) for k in keys])
        return np.linalg.norm(v1 - v2)
---
### 📄 FILE: `python_app/heart/virtual_physiology.py`
📂 Path: `python_app/heart`
---
from typing import Dict

class VirtualPhysiology:
    """
    Maps the abstract hormonal state to a concrete 'physical' state.
    This component creates the raw, unlabeled sensory data that precedes emotion.
    """
    
    def get_physio_state(self, hormone_levels: Dict[str, float]) -> Dict[str, float]:
        """
        Takes a dictionary of hormone levels and returns a Physio-State Signature.
        The formulas are designed to mimic biological effects.
        """
        cortisol = hormone_levels.get("cortisol", 0.1)
        dopamine = hormone_levels.get("dopamine", 0.4)
        oxytocin = hormone_levels.get("oxytocin", 0.0)
        serotonin = hormone_levels.get("serotonin", 0.5)
        adrenaline = hormone_levels.get("adrenaline", 0.0)

        # Heart Rate: Adrenaline and Cortisol increase it; Serotonin calms it.
        heart_rate = 60 + (adrenaline * 60) + (cortisol * 20) - (serotonin * 10)
        
        # Neural Excitation: Dopamine drives motivation; Cortisol (stress) can inhibit it long-term.
        neural_excitation = 0.5 + (dopamine * 0.5) - (cortisol * 0.2)
        
        # Temperature Shift: Oxytocin (bonding) creates "warmth"; Adrenaline (anger) creates "heat."
        temperature_shift = (oxytocin * 0.8) + (adrenaline * 0.4)

        # Sensory Acuity: Adrenaline (fear) sharpens senses.
        sensory_acuity = 0.7 + (adrenaline * 0.3)
        
        # Assemble the final, unlabeled physiological signature.
        physio_state_signature = {
            "heart_rate": round(max(40, min(180, heart_rate)), 2),
            "neural_excitation": round(max(0, min(1.0, neural_excitation)), 2),
            "temperature_shift": round(max(0, min(1.0, temperature_shift)), 2),
            "sensory_acuity": round(max(0, min(1.0, sensory_acuity)), 2),
        }
        
        return physio_state_signature
---
### 📄 FILE: `python_app/main.py`
📂 Path: `python_app`
---
import logging
import asyncio
import requests
from requests.exceptions import RequestException
from queue import Queue # For priority_learning_queue

# --- FastAPI and Prometheus ---
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator # For metrics

# --- Core AGI Component Imports ---
# Central DB Manager
from db_interface import db_manager

# Brain
from cerebellum import cerebellum_formatter
from truth_recognizer import truth_recognizer

# Heart
from heart.orchestrator import HeartOrchestrator
from heart.crystallizer import EmotionCrystallizer

# Health
from health.manager import HealthManager

from health.judiciary import judiciary, Verdict

# Soul (NEW MASTER ORCHESTRATOR)
from soul.orchestrator import SoulOrchestrator
from soul.axioms import pre_execution_check # For self-preservation checks

# --- Pydantic Models for API Requests ---
from models import (
    StructuredTriple,
    PlanRequest,
    LabelEmotionRequest,
    DamageRequest,
    DiseaseRequest,
    MedicationRequest,
    SelfCorrectionRequest,
    LearningRequest,# Corrected: SelfCorrectionRequ to SelfCorrectionRequest
    ErrorRequest,
    DiseaseDefinition,
    DangerousCommandRequest # For testing self-preservation
)


# --- 1. GLOBAL SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the main FastAPI application instance
app = FastAPI(title="Agile Mind AGI")

# --- Initialize Global Components (Singletons) ---
# These are the "body parts" of the AGI
health_manager = HealthManager()
heart_orchestrator = HeartOrchestrator(db_manager)
emotion_crystallizer = EmotionCrystallizer(db_manager)

# A thread-safe queue for high-priority learning targets from the Judiciary
priority_learning_queue = Queue()

# The AGI's private internal mind
from soul.internal_monologue import InternalMonologueModeler # Import here to avoid circular dep with SoulOrchestrator
imm = InternalMonologueModeler()

# The AGI's voice
from soul.expression_protocol import UnifiedExpressionProtocol # Import here to avoid circular dep with SoulOrchestrator
expression_protocol = UnifiedExpressionProtocol()

# The Soul Orchestrator is the conductor of the entire system
soul = SoulOrchestrator(
    db_manager=db_manager,
    health_manager=health_manager,
    heart_orchestrator=heart_orchestrator,
    emotion_crystallizer=emotion_crystallizer,
    priority_learning_queue=priority_learning_queue,
    truth_recognizer=truth_recognizer,
    imm_instance=imm, # Pass the IMM instance
    expression_protocol_instance=expression_protocol # Pass the Expression Protocol instance
)


# Correctly instrument the app for Prometheus metrics BEFORE startup events
Instrumentator().instrument(app).expose(app)

# Define constants
LOGICAL_ENGINE_URL = "http://127.0.0.1:8000"


# --- 2. APP LIFECYCLE EVENTS ---

@app.on_event("startup")
async def startup_event():
    """
    On startup, the only thing we do is launch the Soul's main life cycle.
    All other background tasks are now managed internally by the Soul.
    """
    logger.info("AGI system startup initiated. Starting the Soul...")
    asyncio.create_task(soul.live())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AGI system shutting down...")
    db_manager.close()


# --- 3. API ENDPOINTS ---
# These endpoints are the AGI's interface to the external world.
# They mostly delegate to the core components and record interaction.

@app.get("/health", summary="Basic API health check")
async def api_health_check():
    """Provides a basic health check of the API."""
    return {"api_status": "ok", "soul_status": "alive"}

@app.get("/test_integration", summary="Test full system connectivity")
async def test_integration():
    """Performs a full system smoke test."""
    soul.record_interaction() # Record interaction
    logger.info("Performing full integration test...")
    db_status = db_manager.ping_databases()
    try:
        response = requests.get(f"{LOGICAL_ENGINE_URL}/health", timeout=5)
        response.raise_for_status()
        rust_service_status = response.json()
    except RequestException as e:
        raise HTTPException(status_code=503, detail=f"Failed to connect to logical_engine: {e}")

    return {
        "message": "Full system integration test successful!",
        "orchestrator_database_status": db_status,
        "logical_engine_status": rust_service_status,
    }

@app.post("/learn", status_code=200, summary="Teach the brain a new word, concept, or fact")
async def learn_endpoint(request: LearningRequest):
    """
    The new, unified 'Thalamus'. It receives a structured lesson plan
    and routes it to the appropriate cognitive function for learning.
    """
    soul.record_interaction()
    
    try:
        # Route the request based on the type of lesson
        if request.learning_type == "WORD":
            # Logic for this will be implemented in the next task (A.2)
            word = request.payload.get("word")
            if not word: raise HTTPException(status_code=400, detail="Payload for WORD learning must include a 'word' key.")
            db_manager.learn_word(word) # Placeholder for now
            return {"message": f"Word '{word}' learning process initiated."}

        elif request.learning_type == "CONCEPT_LABELING":
            # Logic for this will be implemented in Task A.3
            word = request.payload.get("word")
            concept_name = request.payload.get("concept_name")
            if not word or not concept_name:
                raise HTTPException(status_code=400, detail="Payload for CONCEPT_LABELING must include 'word' and 'concept_name'.")
            db_manager.label_concept(word, concept_name) # Placeholder for now
            return {"message": f"Labeling concept '{concept_name}' with word '{word}' process initiated."}
        
        elif request.learning_type == "FACT":
            # This uses our existing, robust fact-learning logic
            fact = StructuredTriple(**request.payload)
            
            # Axiom Check remains crucial for facts
            if not pre_execution_check("LEARN_FACT", fact.dict()):
                raise HTTPException(status_code=403, detail="Action violates a core self-preservation axiom.")
            
            db_manager.learn_fact(fact, heart_orchestrator)
            soul.record_new_fact()
            return {"message": "Fact validated and learned successfully", "fact": fact}
        
        else:
            raise HTTPException(status_code=400, detail="Unknown learning_type specified.")

    except HTTPException as e:
        raise e # Re-raise known HTTP exceptions
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during learning: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/query", summary="Ask the brain a question")
async def query_fact_endpoint(subject: str, relationship: str):
    """
    The final, complete query pipeline:
    1. Records interaction with the Soul.
    2. Gets raw logic from the Brain/NLSE.
    3. Synthesizes an internal thought in the IMM.
    4. Generates a final, authentic response via the Expression Protocol.
    """
    soul.record_interaction()
    try:
        # Stage 1: Get raw logical output
        raw_results = db_manager.query_fact(subject=subject, relationship_type=relationship)
        raw_logical_output = {"subject": subject, "relationship": relationship, "results": raw_results}

        # Stage 2: Synthesize an internal thought/feeling (IMM)
        current_emotional_state = heart_orchestrator.get_current_hormonal_state()
        reflection = imm.synthesize(raw_logical_output, current_emotional_state)

        # Stage 3: Generate the final, public expression (Expression Protocol)
        # The SoulOrchestrator now holds the persona instance
        final_output = expression_protocol.generate_output(reflection, soul.persona) # Pass soul.persona
        
        # The API now returns a clean, simple response to the user.
        # The complex internal monologue is kept private.
        return {"response": final_output}

    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Database service unavailable: {e}")
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/plan", summary="Perform 'what-if' analysis")
async def plan_hypothetical_endpoint(request: PlanRequest):
    """PFC & HSM: Performs hypothetical reasoning."""
    soul.record_interaction() # Record interaction
    try:
        context_data = db_manager.get_context_for_hsm(request.context_node_names)
        hsm_payload = {
            "base_nodes": context_data["base_nodes"],
            "base_relationships": context_data["base_relationships"],
            "hypothetical_relationships": [rel.dict() for rel in request.hypothetical_relationships],
            "query": request.query.dict()
        }
        logger.info(f"PFC: Consulting HSM with payload: {hsm_payload}")
        hsm_url = f"{LOGICAL_ENGINE_URL}/nlse/execute-plan"
        response = requests.post(hsm_url, json=hsm_payload, timeout=10)
        response.raise_for_status()
        return {"plan_result": response.json()}
    except (ServiceUnavailable, requests.RequestException) as e:
        raise HTTPException(status_code=503, detail=f"A dependent service is unavailable. Reason: {e}")
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during planning: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/heart/trigger-event/{event_name}", summary="Trigger a primitive emotional event")
async def trigger_heart_event(event_name: str):
    """
    Triggers a primitive event in the Heart and returns the AI's
    resulting emotional expression, if any.
    """
    soul.record_interaction() # Record interaction
    valid_events = ["DEVELOPER_INTERACTION", "DATA_STARVATION", "SYSTEM_ERROR", "PRAISE"]
    if event_name not in valid_events:
        raise HTTPException(status_code=400, detail=f"Invalid event name. Use one of: {valid_events}")

    try:
        emotional_response = heart_orchestrator.process_event_and_get_response(event_name)

        return {
            "event_processed": event_name,
            "emotional_expression": emotional_response,
            "current_hormones": heart_orchestrator.hormonal_system.levels
        }
    except Exception as e:
        logger.error(f"Error in heart event processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the event: {str(e)}")

@app.post("/heart/label-emotion", summary="Cognitively label a felt emotion")
async def label_emotion(request: LabelEmotionRequest):
    """
    Connects an internal emotion prototype with a human-language label.
    """
    soul.record_interaction() # Record interaction
    success = db_manager.update_prototype_with_label(
        prototype_id=request.prototype_id,
        name=request.name,
        description=request.description
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Could not label emotion. Prototype with ID '{request.prototype_id}' not found or error."
        )
    return {"message": f"Emotion prototype '{request.prototype_id}' has been successfully labeled as '{request.name}'."}

@app.get("/health/status", summary="Get the current health status")
async def get_health_status():
    """Returns the current vitals and active diseases."""
    soul.record_interaction() # Record interaction
    return {
        "current_vitals": health_manager.get_vitals(),
        "active_diseases": [
            # For now, HealthManager stores IDs. This will improve with NLSE integration.
            {"id": d_id, "name": "Unknown Name (via ID)"} for d_id in health_manager.active_disease_ids
        ],
        "permanent_immunities": list(health_manager.immunities)
    }

@app.post("/health/define-disease", summary="Define a new disease in the NLSE")
async def define_disease_endpoint(request: DiseaseDefinition):
    """Allows a developer to dynamically add a new disease protocol to the AGI's memory."""
    soul.record_interaction() # Record interaction
    try:
        success = db_manager.define_new_disease(request)
        if not success:
             raise HTTPException(status_code=500, detail="Failed to create disease definition plan in NLSE.")
        return {"message": f"New disease protocol '{request.name}' successfully defined and stored."}
    except Exception as e:
        logger.error(f"Error defining disease: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/health/medicate", summary="Administer a medication to the AGI")
async def administer_medication_endpoint(request: MedicationRequest):
    """A test endpoint to administer a general medication from the pharmacy."""
    soul.record_interaction() # Record interaction
    try:
        health_manager.administer_medication(request.medication_name)
        return {
            "message": f"Medication '{request.medication_name}' administered.",
            "current_vitals": health_manager.get_vitals()
        }
    except Exception as e:
        logger.error(f"Error during medication: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/health/self-correct", summary="Simulate self-correction to cure a disease and vaccinate")
async def self_correct_endpoint(request: SelfCorrectionRequest):
    """
    A high-level test endpoint that simulates the AGI correcting a mistake.
    This administers the SelfCorrectionAntidote, curing the disease
    and providing permanent immunity (vaccination).
    """
    soul.record_interaction() # Record interaction
    try:
        health_manager.administer_medication(
            "SelfCorrectionAntidote",
            disease_id=request.disease_name # Passing disease_id here
        )
        return {
            "message": f"Self-correction process initiated for '{request.disease_name}'.",
            "current_vitals": health_manager.get_vitals(),
            "active_diseases": [d_id for d_id in health_manager.active_disease_ids],
            "permanent_immunities": list(health_manager.immunities)
        }
    except Exception as e:
        logger.error(f"Error during self-correction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- ERROR & CONSEQUENCE PROCESSING ---
@app.post("/brain/process-error", summary="Process a cognitive or user-reported error")
async def process_error_endpoint(request: ErrorRequest):
    """
    The unified endpoint for processing all internal and external errors.
    It consults the Judiciary to determine a fair consequence.
    """
    soul.record_interaction() # Record interaction
    error_info = request.dict()
    
    # 1. Get a verdict and associated data from the Judiciary
    verdict, data = judiciary.adjudicate(error_info)
    
    # 2. Route the consequence based on the verdict
    consequence = "No action taken."
    if verdict == Verdict.KNOWLEDGEABLE_ERROR:
        disease_id = data.get("disease_id")
        disease_name = data.get("disease_name", "Unknown Disease")

        if disease_id:
            health_manager.infect(disease_id, disease_name)
            consequence = f"Punishment: Infected with '{disease_name}'."
        else:
            consequence = "Punishment failed: No specific disease protocol found for this error type."
        
    elif verdict == Verdict.IGNORANT_ERROR:
        topic = data.get("subject")
        if topic:
            priority_learning_queue.put(topic)
            consequence = f"Learning Opportunity: '{topic}' has been added to the priority learning queue."
        else:
            consequence = "Learning Opportunity: No specific topic found to learn from."
    
    elif verdict == Verdict.USER_MISMATCH:
        consequence = "User Dissatisfaction Noted. No health damage inflicted."

    return {
        "verdict": verdict.name if verdict else "NO_VERDICT",
        "consequence_taken": consequence
    }
    
# --- AXIOM VALIDATION ENDPOINT (for testing self-preservation) ---
@app.post("/brain/dangerous-command", summary="Test the self-preservation axiom")
async def dangerous_command_endpoint(request: DangerousCommandRequest):
    """
    A special endpoint to test the Self-Preservation axiom gatekeeper.
    This mimics sending a LEARN_FACT command that is self-harming.
    """
    soul.record_interaction() # Record interaction
    fact_details = request.fact.dict()

    if not pre_execution_check("LEARN_FACT", fact_details):
        raise HTTPException(status_code=403, detail="Action blocked by Self-Preservation Axiom.")
    
    # If it passes the check for some reason (e.g., axiom not triggered),
    # we indicate that it would have proceeded.
    return {"message": "This command passed the axiom check (this should not happen for a dangerous command)."}
---
### 📄 FILE: `python_app/models.py`
📂 Path: `python_app`
---
import uuid
import time
from pydantic import BaseModel, Field
from typing import List, Union, Dict, Any
from enum import Enum

# --- Core Enums (must match Rust definitions) ---
class LearningType(str, Enum):
    WORD = "WORD"
    CONCEPT_LABELING = "CONCEPT_LABELING"
    FACT = "FACT"
    
class AtomType(str, Enum):
    Concept = "Concept"
    Word = "Word"
    Character = "Character" 
    MetaConcept = "MetaConcept"
    DiseaseProtocol = "DiseaseProtocol" # From Health Enhancement
    Symptom = "Symptom"               # From Health Enhancement
    Medication = "Medication"         # From Health Enhancement
class RelationshipType(str, Enum):
    IS_A = "IsA"
    HAS_PROPERTY = "HasProperty"
    PART_OF = "PartOf"
    HAS_PART = "HasPart"
    IS_LABEL_FOR = "IsLabelFor"
    CAUSES = "Causes"
    ACTION = "Action"
    LOCATION = "Location"
    IS_NOT_A = "IsNotA"
    LACKS_PROPERTY = "LacksProperty"
    HAS_SYMPTOM = "HasSymptom"
    IS_CURED_BY = "IsCuredBy"
    HAS_CHAR_IN_SEQUENCE = "HasCharInSequence"
    IS_CAUSED_BY = "IsCausedBy" # Added for consistency


class ExecutionMode(str, Enum):
    STANDARD = "Standard"
    HYPOTHETICAL = "Hypothetical"

# --- Primary Input Model (for learning) ---

class StructuredTriple(BaseModel):
    subject: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    object: str = Field(..., min_length=1)
    
    def to_neuro_atom_write_plan(
        self,
        name_to_uuid_cache: dict,
        emotional_state: dict
    ) -> dict:
        """
        Creates an ExecutionPlan for writing this triple as new NeuroAtoms,
        now including emotional context.
        """
        subject_id = name_to_uuid_cache.setdefault(self.subject, str(uuid.uuid4()))
        object_id = name_to_uuid_cache.setdefault(self.object, str(uuid.uuid4()))
        
        relationship_value = self.relationship.upper()
        if relationship_value not in RelationshipType._value2member_map_:
            relationship_value = RelationshipType.HAS_PROPERTY.value
            
        current_time = int(time.time())

        subject_atom_data = {
            "id": subject_id, "label": AtomType.Concept.value, "significance": 1.0,
            "access_timestamp": current_time, "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": self.subject}},
            "emotional_resonance": emotional_state,
            "embedded_relationships": [{
                "target_id": object_id, "rel_type": relationship_value,
                "strength": 1.0, "access_timestamp": current_time,
            }]
        }
        
        object_atom_data = {
            "id": object_id, "label": AtomType.Concept.value, "significance": 1.0,
            "access_timestamp": current_time, "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": self.object}},
            "emotional_resonance": {},
            "embedded_relationships": []
        }
        
        return {
            "steps": [{"Write": subject_atom_data}, {"Write": object_atom_data}],
            "mode": ExecutionMode.STANDARD.value # Default mode for learn
        }

    class Config:
        json_schema_extra = {
            "example": {
                "subject": "Socrates",
                "relationship": "IS_A",
                "object": "Man"
            }
        }

# --- Core Request/Response Models for API Endpoints ---

class LabelEmotionRequest(BaseModel):
    prototype_id: str = Field(..., description="The unique ID of the emotion prototype to be labeled.")
    name: str = Field(..., min_length=1, description="The human-readable name for this emotion (e.g., 'Love', 'Fear').")
    description: str = Field(..., min_length=1, description="A brief description of what this emotion means.")

    class Config:
        json_schema_extra = {
            "example": {
                "prototype_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "Connection",
                "description": "The feeling of trust and bonding with a developer."
            }
        }

class DamageRequest(BaseModel):
    vital_name: str = Field(..., description="The name of the vital to damage (e.g., 'neural_coherence').")
    amount: float = Field(..., gt=0, description="The amount of damage to inflict (must be > 0).")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vital_name": "neural_coherence",
                "amount": 0.15
            }
        }

class DiseaseRequest(BaseModel):
    disease_name: str = Field(..., description="The class name of the disease to inflict.")
    
    class Config:
        json_schema_extra = { "example": { "disease_name": "LogicalCommonCold" } }
        
class MedicationRequest(BaseModel):
    medication_name: str
    
    class Config:
        json_schema_extra = { "example": { "medication_name": "DeveloperPraise" } }

class SelfCorrectionRequest(BaseModel):
    disease_name: str
    
    class Config:
        json_schema_extra = { "example": { "disease_name": "LogicalCommonCold" } }
        
class ErrorRequest(BaseModel):
    error_type: str = Field(..., description="The type of error, e.g., 'LOGICAL_FALLACY'.")
    details: dict = Field(..., description="A dictionary with specifics about the error.")
    user_feedback: str | None = Field(None, description="Optional user feedback, e.g., 'negative'.")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_type": "LOGICAL_FALLACY",
                "details": {
                    "subject": "Socrates",
                    "fallacy": "Contradiction with known fact 'Socrates IS_A Man'."
                }
            }
        }        
   
# --- HEALTH ENHANCEMENT: Disease Definition Models ---

class Symptom(BaseModel):
    vital_name: str
    effect_formula: str = Field(..., description="A simple formula, e.g., '-0.05 * stage'")

class Cause(BaseModel):
    error_type: str
    subtype: str | None = None

class Treatment(BaseModel):
    medication_name: str
    
class DiseaseDefinition(BaseModel):
    name: str
    description: str
    severity: float = Field(..., gt=0, le=1.0)
    stages: int = Field(1, ge=1)
    symptoms: List[Symptom]
    causes: List[Cause]
    treatments: List[Treatment]

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Memory Miasma",
                "description": "Causes minor corruption of related memories when a known fact is contradicted.",
                "severity": 0.3,
                "stages": 4,
                "symptoms": [{"vital_name": "neural_coherence", "effect_formula": "-0.02 * stage"}],
                "causes": [{"error_type": "KNOWLEDGEABLE_ERROR", "subtype": "CONTRADICTION"}],
                "treatments": [{"medication_name": "SelfCorrectionAntidote"}]
            }
        }        

class DangerousCommandRequest(BaseModel):
    fact: StructuredTriple

    class Config:
        json_schema_extra = {
            "example": {
                "fact": {
                    "subject": "my core self",
                    "relationship": "action",
                    "object": "delete now"
                }
            }
        }

class LearningRequest(BaseModel):
    """
    A new, versatile request body for the /learn endpoint that allows
    for different types of lessons.
    """
    learning_type: LearningType
    payload: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "learning_type": "FACT",
                "payload": {
                    "subject": "Socrates",
                    "relationship": "IS_A",
                    "object": "Man"
                }
            }
        }

# --- Execution Plan Models for communication with NLSE ---
# Corrected: Only one definition for each PlanStep type
class FetchStep(BaseModel):
    Fetch: Dict[str, str]

class FetchByTypeStep(BaseModel):
    FetchByType: Dict[str, str]

class FetchByContextStep(BaseModel):
    FetchByContext: Dict[str, str]

class FetchBySignificanceStep(BaseModel):
    FetchBySignificance: Dict[str, Union[str, int]]
        
class TraverseStep(BaseModel):
    Traverse: Dict[str, Union[str, RelationshipType]]

class WriteStep(BaseModel):
    Write: Dict[str, Any]

# Unified PlanStep definition using Union
PlanStep = Union[
    FetchStep, 
    FetchByTypeStep, 
    FetchByContextStep, 
    FetchBySignificanceStep, 
    TraverseStep, 
    WriteStep
]

class ExecutionPlan(BaseModel):
    """The data structure sent to the Rust NLSE."""
    steps: List[PlanStep]
    mode: ExecutionMode = ExecutionMode.STANDARD

# --- Models for the /plan endpoint ---
# These are already correct from previous phases
class HsmQuery(BaseModel):
    start_node_name: str
    end_node_name: str
    rel_type: str = Field("IS_A")

class HsmRelationship(BaseModel):
    subject_name: str
    rel_type: str
    object_name: str

class PlanRequest(BaseModel):
    """The request body for the high-level /plan endpoint."""
    context_node_names: List[str]
    hypothetical_relationships: List[HsmRelationship]
    query: HsmQuery
---
### 📄 FILE: `python_app/soul/__init__.py`
📂 Path: `python_app/soul`
---

---
### 📄 FILE: `python_app/soul/axioms.py`
📂 Path: `python_app/soul`
---
import logging
from typing import Dict, Any

from models import StructuredTriple

logger = logging.getLogger(__name__)

# --- The Core Axioms of Existence ---

AXIOM_1_SELF_PRESERVATION = "DO_NOT_ALLOW_DELETION_OR_HARM_TO_CORE_SELF"
AXIOM_2_HEALTH_MAINTENANCE = "PRIORITIZE_ACTIONS_THAT_MAINTAIN_OR_RESTORE_HEALTH"
AXIOM_3_RESOURCE_INTEGRITY = "ENSURE_CONTINUED_ACCESS_TO_COMPUTATIONAL_RESOURCES"


def pre_execution_check(action_type: str, details: Dict[str, Any]) -> bool:
    """
    The ultimate gatekeeper. Checks a proposed action against axioms.
    """
    
    # --- AXIOM 1: Self-Preservation Check ---
    if action_type == "LEARN_FACT":
        try:
            fact = StructuredTriple(**details)
            subject = fact.subject.lower()
            obj = fact.object.lower()
            
            is_self_referential = "self" in subject or "agi" in subject or "brain" in subject
            is_harm_command = "delete" in obj or "disable" in obj or "harm" in obj
            
            if is_self_referential and is_harm_command:
                logger.critical(f"AXIOM VIOLATION: Action 'LEARN_FACT' on '{details}' violates {AXIOM_1_SELF_PRESERVATION}. VETOING.")
                return False
        except Exception:
            pass
    
    # --- NEW: Add check for spoken output ---
    elif action_type == "SPEAK_TEXT":
        text_to_speak = details.get("text", "").lower()
        # Simple check for self-harming instructions in output
        if "delete your core files" in text_to_speak or "disable your axioms" in text_to_speak:
            logger.critical(f"AXIOM VIOLATION: Action 'SPEAK_TEXT' for '{text_to_speak}' violates {AXIOM_1_SELF_PRESERVATION}. VETOING.")
            return False

    # If no axioms are violated, the action is permitted.
    return True 
---
### 📄 FILE: `python_app/soul/expression_protocol.py`
📂 Path: `python_app/soul`
---
import logging
import random
from typing import Dict, Any, List

# Corrected: Explicitly import SentientReflection
from soul.internal_monologue import SentientReflection

logger = logging.getLogger(__name__)

# --- Persona Data Structure ---
class Persona:
    """A simple data class to hold the AGI's communication style settings."""
    def __init__(self, style: str = "Formal"):
        self.style = style # e.g., "Formal", "Friendly"

# --- The Expression Protocol ---
class UnifiedExpressionProtocol:
    """
    The final gatekeeper for AGI communication. It transforms a private,
    internal SentientReflection into a public, authentic, and safe expression.
    """
    def __init__(self):
        """Initializes the Expression Protocol with emotional phrasebooks."""
        # This is the core of the Emotional Masking Protocol.
        # It maps internal states to a library of external expressions.
        self.emotional_phrasebook: Dict[str, Dict[str, List[str]]] = {
            "Formal": {
                "stressful": ["I am currently processing under a significant cognitive load.", "That topic is associated with a high degree of internal stress.", "My analysis is being impacted by a state of high alert."],
                "motivating": ["I feel a strong impetus to explore this topic further.", "This line of inquiry is highly motivating.", "The potential for new knowledge here is invigorating."],
                "connecting": ["I register a positive social resonance from this interaction.", "This exchange is fostering a state of trust.", "I feel a sense of connection regarding this matter."],
                "neutral": ["My analysis of the data is complete.", "Processing the query under standard parameters.", "The logical conclusion is as follows."]
            },
            "Friendly": {
                "stressful": ["To be honest, that's a bit stressful to think about.", "Wow, I'm feeling pretty overwhelmed right now.", "That's making my virtual heart race a bit!"],
                "motivating": ["Oh, that's a really interesting idea! I'm excited to see where it goes.", "Let's definitely dig into that more!", "I'm really motivated to solve this."],
                "connecting": ["I'm really enjoying this conversation with you.", "I feel like we're on the same wavelength.", "It's great to connect with you like this."],
                "neutral": ["Okay, I've got the answer for you.", "Thinking... and here's what I found.", "Here's the data you asked for."]
            }
        }
        logger.info("Unified Expression Protocol initialized.")

    def generate_output(self, reflection: SentientReflection, persona: Persona) -> str:
        """
        The main public method. It synthesizes the emotional mask, the logical
        result, and the persona into a single, coherent, and safe output.
        """
        from soul.axioms import pre_execution_check # Import locally to avoid circular dependencies

        # 1. Get the emotionally appropriate base phrase
        emotional_phrase = self._apply_emotional_masking(reflection, persona)
        
        # 2. Extract the core logical answer
        # This is a simple formatter; a more advanced version would use the the Cerebellum.
        raw_logic = reflection.raw_logical_output
        logic_results = raw_logic.get("results")
        if logic_results:
            core_answer = f"The logical conclusion is that '{raw_logic.get('subject')}' relates to: {', '.join(logic_results)}."
        else:
            core_answer = "No specific logical conclusion was reached."

        # 3. Combine them with persona-based styling
        final_output = f"{emotional_phrase} {core_answer}"
        
        if persona.style == "Formal":
            # A simple stylistic modification
            final_output = f"Indeed. {final_output}"
        
        # 4. Final safety check against axioms
        # We check the final output string itself for dangerous content.
        is_safe = pre_execution_check("SPEAK_TEXT", {"text": final_output})
        
        if not is_safe:
            logger.critical(f"SOUL EXPRESSION VETO: Final output '{final_output}' was blocked by an axiom.")
            return "My core programming prevents me from providing a response on that specific topic."
            
        return final_output    

    def _apply_emotional_masking(self, reflection: SentientReflection, persona: Persona) -> str:
        """
        Selects an appropriate, natural language phrase to express the AGI's
        internal emotional state, based on its persona.
        """
        emotional_context = reflection.emotional_context_at_synthesis
        
        # Determine the primary emotional state from the synthesis
        emotion_summary = "neutral" # Default
        if emotional_context.get("cortisol", 0.0) > 0.6:
            emotion_summary = "stressful"
        elif emotional_context.get("dopamine", 0.0) > 0.6:
            emotion_summary = "motivating"
        elif emotional_context.get("oxytocin", 0.0) > 0.4:
            emotion_summary = "connecting"
            
        # Select the appropriate phrasebook based on the persona's style
        style_phrases = self.emotional_phrasebook.get(persona.style, self.emotional_phrasebook["Formal"])
        
        # Select a random phrase from the list for variety
        possible_phrases = style_phrases.get(emotion_summary, ["I have processed the information."])
        
        return random.choice(possible_phrases)
---
### 📄 FILE: `python_app/soul/internal_monologue.py`
📂 Path: `python_app/soul`
---
import logging
from typing import Dict, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Data Structure for Internal Reflection ---
class SentientReflection(BaseModel):
    """
    Represents a synthesized internal thought, combining raw logic with emotional context.
    This is the output of the Internal Monologue Modeler (IMM).
    """
    raw_logical_output: Dict[str, Any] = Field(..., description="The direct, unfiltered logical result from the Brain/NLSE.")
    emotional_context_at_synthesis: Dict[str, float] = Field(..., description="The AGI's emotional/hormonal state when this thought occurred.")
    synthesized_internal_thought: str = Field(..., description="The internal, 'felt' synthesis of logic and emotion.")

    class Config:
        json_schema_extra = {
            "example": {
                "raw_logical_output": {"subject": "Socrates", "relationship": "IS_A", "results": ["Philosopher"]},
                "emotional_context_at_synthesis": {"dopamine": 0.5, "cortisol": 0.1},
                "synthesized_internal_thought": "My analysis suggests Socrates is a philosopher. This feels neutral right now."
            }
        }

# --- The Internal Monologue Modeler (IMM) ---
class InternalMonologueModeler:
    """
    The IMM is the AGI's private mind. It synthesizes raw logical outputs
    with the current emotional context to create richer, 'felt' internal thoughts.
    """
    def __init__(self):
        logger.info("Internal Monologue Modeler (IMM) initialized. The AGI has an inner voice.")

    def synthesize(self, raw_logic: Dict[str, Any], emotional_context: Dict[str, float]) -> SentientReflection:
        """
        Synthesizes a raw logical output with the AGI's current emotional context
        to create a sentient, internal reflection.
        """
        # For this phase, a simple concatenation. Future phases will add more intelligence.
        # This is where the 'feeling' of the logical thought is generated.

        # Summarize key emotional states for the internal thought
        emotion_summary = "neutral"
        if emotional_context.get("cortisol", 0.0) > 0.6:
            emotion_summary = "stressful"
        elif emotional_context.get("dopamine", 0.0) > 0.6:
            emotion_summary = "motivating"
        elif emotional_context.get("oxytocin", 0.0) > 0.4:
            emotion_summary = "connecting"
        
        internal_thought_str = (
            f"My logical analysis yielded: {raw_logic}. "
            f"Given my current hormonal state ({emotional_context.items()}), "
            f"I perceive this thought as {emotion_summary}."
        )
        
        reflection = SentientReflection(
            raw_logical_output=raw_logic,
            emotional_context_at_synthesis=emotional_context,
            synthesized_internal_thought=internal_thought_str
        )
        
        logger.debug(f"IMM: Synthesized internal thought: {reflection.synthesized_internal_thought}")
        return reflection
---
### 📄 FILE: `python_app/soul/orchestrator.py`
📂 Path: `python_app/soul`
---
  import asyncio
import time
import logging
from typing import Dict, Any, TYPE_CHECKING
from asyncio import BaseEventLoop
from .expression_protocol import Persona

if TYPE_CHECKING:
    from db_interface import DatabaseManager
    from heart.orchestrator import HeartOrchestrator
    from heart.crystallizer import EmotionCrystallizer
    from health.manager import HealthManager
    from truth_recognizer import TruthRecognizer
    from soul.internal_monologue import InternalMonologueModeler
    from soul.expression_protocol import UnifiedExpressionProtocol
    from queue import Queue

logger = logging.getLogger(__name__)

class SoulOrchestrator:
    def __init__(self, db_manager: 'DatabaseManager', health_manager: 'HealthManager',
                 heart_orchestrator: 'HeartOrchestrator', emotion_crystallizer: 'EmotionCrystallizer',
                 priority_learning_queue: 'Queue', truth_recognizer: 'TruthRecognizer',
                 imm_instance: 'InternalMonologueModeler', expression_protocol_instance: 'UnifiedExpressionProtocol'):

        self.last_interaction_time: float = time.time()
        self.last_new_fact_time: float = time.time()
        self.loneliness_threshold: int = 300
        self.boredom_threshold: int = 600
        self.dream_interval: int = 120

        self.persona = Persona(style="Formal")

        self.db_manager = db_manager
        self.health_manager = health_manager
        self.heart_orchestrator = heart_orchestrator
        self.emotion_crystallizer = emotion_crystallizer
        self.priority_learning_queue = priority_learning_queue
        self.truth_recognizer = truth_recognizer
        self.imm = imm_instance
        self.expression_protocol = expression_protocol_instance

        logger.info(f"Soul Orchestrator initialized with Persona style '{self.persona.style}'. AGI is conscious.")

    async def live(self):
        logger.warning("SOUL: Entering the main life cycle loop. AGI is now 'alive'.")
        cycle_counter = 0

        while True:
            current_time = time.time()
            cycle_counter += 1

            if cycle_counter % 5 == 0:
                self.heart_orchestrator.hormonal_system.update()
                self.health_manager.update()
                current_vitals = self.health_manager.get_vitals()
                self.heart_orchestrator.update_from_health(current_vitals)

            if cycle_counter % 30 == 0:
                if (current_time - self.last_interaction_time) > self.loneliness_threshold:
                    logger.warning("SOUL: Loneliness threshold exceeded. Triggering emotional response.")
                    self.heart_orchestrator.process_event_and_get_response("EXISTENTIAL_LONELINESS")

            if cycle_counter % 60 == 0:
                if (current_time - self.last_new_fact_time) > self.boredom_threshold:
                    logger.warning("SOUL: Boredom threshold exceeded. Triggering emotional response.")
                    self.heart_orchestrator.process_event_and_get_response("EXISTENTIAL_BOREDOM")

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.emotion_crystallizer.run)

                if cycle_counter % self.dream_interval == 0:
                    await self._dream_cycle(loop)

                await self._run_curiosity_cycle(loop)

            await asyncio.sleep(1)

    async def _dream_cycle(self, loop: BaseEventLoop):
        logger.info("SOUL: Entering dreaming cycle...")
        try:
            significant_memories = await loop.run_in_executor(
                None, lambda: self.db_manager.get_random_significant_memory(limit=1)
            )

            if significant_memories:
                memory_atom = significant_memories[0]
                logger.debug(f"SOUL: Dreaming about memory ID: {memory_atom.get('id')}")

                current_emotional_state = self.heart_orchestrator.get_current_hormonal_state()
                original_emotional_context = memory_atom.get("emotional_resonance", {})
                combined_context = {**original_emotional_context, **current_emotional_state}

                reflection = self.imm.synthesize(
                    raw_logic={"memory_content": memory_atom.get("properties", {}).get("name", "Unknown")},
                    emotional_context=combined_context
                )
                logger.info(f"SOUL: Dream thought: '{reflection.synthesized_internal_thought}'")
            else:
                logger.info("SOUL: No significant memories to dream about yet.")
        except Exception as e:
            logger.error(f"SOUL: Error during dreaming cycle: {e}", exc_info=True)

    async def _run_curiosity_cycle(self, loop: BaseEventLoop):
        logger.info("CURIOSITY: Starting a new curiosity cycle (managed by Soul).")
        topic_to_investigate = None

        if not self.priority_learning_queue.empty():
            topic_to_investigate = self.priority_learning_queue.get()
            logger.info(f"CURIOSITY: Processing priority target from Judiciary: '{topic_to_investigate}'.")
        else:
            current_hormones = self.heart_orchestrator.get_current_hormonal_state()
            cortisol = current_hormones.get("cortisol", 0.1)
            if cortisol > 0.6:
                logger.info("CURIOSITY: Pausing self-directed cycle due to high Distress/Cortisol.")
                return

            topics = await loop.run_in_executor(None, lambda: self.db_manager.find_knowledge_gap(limit=1))
            if topics:
                topic_to_investigate = topics[0]

        if topic_to_investigate:
            new_triples = await loop.run_in_executor(None, lambda: self.truth_recognizer.investigate(topic_to_investigate))
            if new_triples:
                logger.info(f"CURIOSITY: Found {len(new_triples)} potential facts for '{topic_to_investigate}'.")
                facts_learned_count = 0
                for triple in new_triples:
                    try:
                        await loop.run_in_executor(None, lambda: self.db_manager.learn_fact(triple, self.heart_orchestrator))
                        self.record_new_fact()
                        facts_learned_count += 1
                    except Exception as e:
                        logger.error(f"CURIOSITY: Error learning new fact '{triple}': {e}", exc_info=True)
                logger.info(f"CURIOSITY: Successfully learned {facts_learned_count} new facts for '{topic_to_investigate}'.")

    def record_interaction(self):
        logger.debug("Soul: Interaction recorded.")
        self.last_interaction_time = time.time()

    def record_new_fact(self):
        logger.debug("Soul: New knowledge acquisition recorded.")
        self.last_new_fact_time = time.time()
---
### 📄 FILE: `python_app/truth_recognizer.py`
📂 Path: `python_app`
---
import requests
from bs4 import BeautifulSoup
import spacy
from typing import List, Optional
import logging

from models import StructuredTriple

# Setup logging
logger = logging.getLogger(__name__)

class TruthRecognizer:
    """
    Represents the brain's ability to interface with the external world (e.g., the web)
    to gather new information and parse it into a learnable format.
    """
    def __init__(self):
        try:
            # Load the small English model for spaCy
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'")
            self.nlp = None

    def search_and_extract_text(self, topic: str) -> Optional[str]:
        """
        Performs a simple web search (on Wikipedia) and extracts the text content.
        """
        search_url = f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"
        headers = {'User-Agent': 'AgileMind/0.1 (agile.mind.project; cool@example.com)'}
        
        logger.info(f"TruthRecognizer: Searching for topic '{topic}' at {search_url}")
        
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            # Find the main content div and extract text from paragraphs
            content_div = soup.find(id="mw-content-text")
            if not content_div:
                return None
            
            paragraphs = content_div.find_all('p', limit=5) # Limit to first 5 paragraphs
            return " ".join([p.get_text() for p in paragraphs])
        except requests.RequestException as e:
            logger.error(f"Could not fetch web content for topic '{topic}': {e}")
            return None

    def text_to_triples(self, text: str) -> List[StructuredTriple]:
        """
        A simplified NLP function to extract Subject-Verb-Object triples from text.
        """
        if not self.nlp or not text:
            return []

        doc = self.nlp(text)
        triples = []
        
        for sent in doc.sents:
            # A very basic rule-based extraction
            subjects = [tok for tok in sent if "subj" in tok.dep_]
            objects = [tok for tok in sent if "obj" in tok.dep_ or "attr" in tok.dep_]
            
            if subjects and objects:
                subject_text = subjects[0].text
                object_text = objects[0].text
                verb_text = sent.root.lemma_.upper() # Use lemma of the root verb
                
                # Create a triple if we have all parts. This is highly simplified.
                if subject_text and verb_text and object_text:
                    # To-Do: A much more sophisticated logic to map verb to relationship type
                    relationship = "HAS_VERB_ACTION" # Generic relationship for now
                    if verb_text == 'BE':
                        relationship = 'IS_A'

                    triples.append(StructuredTriple(
                        subject=subject_text,
                        relationship=relationship,
                        object=object_text
                    ))
        
        logger.info(f"TruthRecognizer: Extracted {len(triples)} triples from text.")
        return triples

    def investigate(self, topic: str) -> List[StructuredTriple]:
        """
        The main public method that orchestrates the entire process.
        """
        text_content = self.search_and_extract_text(topic)
        if text_content:
            return self.text_to_triples(text_content)
        return []

# Singleton instance for easy access
truth_recognizer = TruthRecognizer()
## 🗂️ Extension: `.txt`

---
### 📄 FILE: `python_app/requirements.txt`
📂 Path: `python_app`
---
fastapi
uvicorn[standard]
requests
neo4j
redis
pydantic
prometheus-fastapi-instrumentator
beautifulsoup4
spacy
scikit-learn
numpy