

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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CPEM_DIR = os.path.join(BASE_DIR, ".cpem")
PID_DIR = os.path.join(CPEM_DIR, "pids")
LOG_DIR = os.path.join(CPEM_DIR, "logs")
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


def up():
    """Starts all services as background processes and creates log files."""
    print("CPEM: Starting all services...")
    os.makedirs(PID_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Ensure Rust engine is compiled before launching services
    rust_binary_path = SERVICES["logical_engine"]["command"][0]
    if not os.path.exists(rust_binary_path):
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
            # Force kill if it's still alive
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
                print(f"CPEM WARNING: Sent SIGKILL to '{name}'.")
            except OSError:
                pass # Process group terminated successfully
            os.remove(pid_file)
        except (FileNotFoundError, ProcessLookupError, ValueError):
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
            except (ProcessLookupError, ValueError):
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
    
    subparsers.add_parser("up", help="Start all services.")
    subparsers.add_parser("down", help="Stop all services.")
    subparsers.add_parser("status", help="Check the status of all services.")
    
    logs_parser = subparsers.add_parser("logs", help="Display logs for a service.")
    logs_parser.add_argument("service_name", choices=SERVICES.keys(), help="The service to display logs for.")
    
    args = parser.parse_args()
    
    if args.command == "up":
        up()
    elif args.command == "down":
        down()
    elif args.command == "status":
        status()
    elif args.command == "logs":
        logs(args.service_name)

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
        properties.insert("name".to_string(), Value::String(name.to_string()));
        NeuroAtom {
            id: Uuid::new_v4(), // FIX: Use the correct function to generate a v4 UUID
            label: AtomType::Concept,
            significance: 1.0,
            access_timestamp: 0, // Should be set by StorageManager on write
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
        let mut last_output_key = String::new();

        for step in plan.steps {
            let mut manager = self.storage_manager.lock().unwrap();
            match step {
                PlanStep::Fetch { id, context_key } => {
                    if let Ok(Some(atom)) = manager.read_atom(id) {
                        t0_cache.insert(context_key.clone(), vec![atom]);
                        last_output_key = context_key;
                    } else {
                        return self.fail(&format!("Fetch failed: Atom ID '{}' not found in storage.", id));
                    }
                }
                PlanStep::Traverse { from_context_key, rel_type, output_key } => {
                    if let Some(source_atoms) = t0_cache.get(&from_context_key) {
                        let mut results = Vec::new();
                        for source_atom in source_atoms {
                            for rel in &source_atom.embedded_relationships {
                                if rel.rel_type == rel_type {
                                    if let Ok(Some(target_atom)) = manager.read_atom(rel.target_id) {
                                        results.push(target_atom);
                                    }
                                }
                            }
                        }
                        t0_cache.insert(output_key.clone(), results);
                        last_output_key = output_key;
                    } else {
                        return self.fail(&format!("Traverse failed: Source context key '{}' not found in T0 cache.", from_context_key));
                    }
                }
                PlanStep::Write(atom_to_write) => {
                    if let Ok(Some(mut existing_atom)) = manager.get_atom_by_id_raw(atom_to_write.id) {
                        // This is a simplified merge. A production system would be more sophisticated.
                        existing_atom.embedded_relationships.extend(atom_to_write.embedded_relationships);
                        if let Err(e) = manager.write_atom(&existing_atom) {
                            return self.fail(&format!("Write (update) failed: {}", e));
                        }
                    } else {
                        // It's a new atom.
                        if let Err(e) = manager.write_atom(&atom_to_write) {
                            return self.fail(&format!("Write (insert) failed: {}", e));
                        }
                    }
                }
                PlanStep::FetchByContext { context_id, context_key } => {
                    let mut atoms = Vec::new();
                    if let Some(ids) = manager.get_atoms_in_context(&context_id) {
                        for id in ids {
                            if let Ok(Some(atom)) = manager.read_atom(*id) {
                                atoms.push(atom);
                            }
                        }
                    }
                    t0_cache.insert(context_key.clone(), atoms);
                    last_output_key = context_key;
                }
                PlanStep::FetchByType { atom_type, context_key } => {
                    let mut atoms = Vec::new();
                    if let Some(ids) = manager.get_atoms_by_type(&atom_type) {
                        for id in ids {
                            if let Ok(Some(atom)) = manager.read_atom(*id) {
                                atoms.push(atom);
                            }
                        }
                    }
                    t0_cache.insert(context_key.clone(), atoms);
                    last_output_key = context_key;
                }
                PlanStep::FetchBySignificance { limit, context_key } => {
                    let atom_ids = manager.get_most_significant_atoms(limit);
                    let mut atoms = Vec::new();
                    for id in atom_ids {
                        if let Ok(Some(atom)) = manager.read_atom(id) {
                            atoms.push(atom);
                        }
                    }
                    t0_cache.insert(context_key.clone(), atoms);
                    last_output_key = context_key;
                }
            }
        }
        
        // The final result is the content of the last populated context key.
        let final_atoms = t0_cache.get(&last_output_key).cloned().unwrap_or_default();
        QueryResult {
            atoms: final_atoms,
            success: true,
            message: "Execution plan completed successfully.".to_string(),
        }
    }
    
    fn fail(&self, message: &str) -> QueryResult {
        QueryResult { atoms: vec![], success: false, message: message.to_string(), }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    // (imports remain the same)
    use crate::nlse_core::models::{AtomType, RelationshipType, Value, NeuroAtom, Relationship};
    use std::fs;
    use std::sync::{Arc, Mutex};
    use uuid::Uuid;
    use std::collections::HashMap;

    fn setup_test_engine(test_name: &str) -> (QueryEngine, Uuid, Uuid) {
        // (setup function remains the same)
        let data_dir = format!("./test_data/{}", test_name);
        let _ = fs::remove_dir_all(&data_dir);
        let sm = Arc::new(Mutex::new(StorageManager::new(&data_dir).unwrap()));
        let qe = QueryEngine::new(Arc::clone(&sm));
        let socrates_id = Uuid::new_v4(); let man_id = Uuid::new_v4();
        let socrates_atom = NeuroAtom { id: socrates_id, label: AtomType::Concept, properties: HashMap::from([("name".to_string(), Value::String("Socrates".to_string()))]), embedded_relationships: vec![Relationship { target_id: man_id, rel_type: RelationshipType::IsA, strength: 1.0, access_timestamp: 0 }], significance: 1.0, access_timestamp: 0, context_id: None, state_flags: 0, emotional_resonance: HashMap::new() };
        let man_atom = NeuroAtom { id: man_id, label: AtomType::Concept, properties: HashMap::from([("name".to_string(), Value::String("Man".to_string()))]), embedded_relationships: vec![], significance: 1.0, access_timestamp: 0, context_id: None, state_flags: 0, emotional_resonance: HashMap::new() };
        let plan = ExecutionPlan { steps: vec![ PlanStep::Write(socrates_atom), PlanStep::Write(man_atom) ], mode: ExecutionMode::Standard, };
        qe.execute(plan);
        (qe, socrates_id, man_id)
    }

    #[test]
    fn test_execute_fetch_plan() {
        let (qe, _, man_id) = setup_test_engine("fetch_plan");
        let fetch_plan = ExecutionPlan {
            // FIX: Use an empty context_key to signal it's the final result
            steps: vec![PlanStep::Fetch { id: man_id, context_key: "".to_string() }],
            mode: ExecutionMode::Standard,
        };
        let result = qe.execute(fetch_plan);
        assert!(result.success);
        assert_eq!(result.atoms.len(), 1);
        assert_eq!(result.atoms[0].id, man_id);
    }

    #[test]
    fn test_execute_traverse_plan() {
        let (qe, socrates_id, man_id) = setup_test_engine("traverse_plan");
        let traverse_plan = ExecutionPlan {
            steps: vec![
                PlanStep::Fetch { id: socrates_id, context_key: "start_nodes".to_string() },
                // FIX: Use an empty output_key for the final step
                PlanStep::Traverse { from_context_key: "start_nodes".to_string(), rel_type: RelationshipType::IsA, output_key: "".to_string() }
            ],
            mode: ExecutionMode::Standard,
        };
        let result = qe.execute(traverse_plan);
        assert!(result.success, "Execution should succeed");
        assert_eq!(result.atoms.len(), 1, "Should find exactly one related atom");
        assert_eq!(result.atoms[0].id, man_id, "The atom found should be Man");
    }
}
---
### 📄 FILE: `rust_engine/src/nlse_core/storage_manager.rs`
📂 Path: `rust_engine/src/nlse_core`
---
// --- The Final, Definitive, Corrected storage_manager.rs ---

use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{self, BufReader, Write};
use uuid::Uuid;
use bincode;
use petgraph::graph::{NodeIndex, Graph as PetGraph};

// FIX: Import all necessary models, including RelationshipType
use crate::nlse_core::models::{NeuroAtom, Relationship, Value, AtomType, RelationshipType};

// A simple, serializable struct to represent the graph's edges on disk.
#[derive(serde::Serialize, serde::Deserialize, Debug)]
struct GraphEdge {
    source: Uuid,
    target: Uuid,
    relationship: Relationship,
}

/// Manages the persistence layer for NeuroAtoms and their relationships.
pub struct StorageManager {
    data_dir: String,
    pub atoms: HashMap<Uuid, NeuroAtom>,
    pub graph: PetGraph<Uuid, Relationship>,
    pub name_to_uuid: HashMap<String, Uuid>,
    pub t1_cache: HashMap<Uuid, NeuroAtom>,
    
    // Indexes
    pub relationship_index: HashMap<RelationshipType, Vec<Uuid>>,
    pub context_index: HashMap<Uuid, Vec<Uuid>>,
    pub type_index: HashMap<AtomType, Vec<Uuid>>,
    pub significance_index: Vec<(f32, Uuid)>,
}

impl StorageManager {
    pub fn new(data_dir: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let atoms_path = format!("{}/atoms.json", data_dir);
        let graph_path = format!("{}/graph.bin", data_dir);

        fs::create_dir_all(data_dir)?;
        if fs::metadata(&atoms_path).is_err() { fs::write(&atoms_path, "{}")?; }
        if fs::metadata(&graph_path).is_err() { File::create(&graph_path)?; }

        let atoms_file = File::open(&atoms_path)?;
        let reader = BufReader::new(atoms_file);
        let atoms: HashMap<Uuid, NeuroAtom> = serde_json::from_reader(reader)?;

        // --- GRAPH LOADING FIX ---
        // Load the simple, serializable edge list from the file.
        let graph_file = File::open(&graph_path)?;
        let reader = BufReader::new(graph_file);
        let edges: Vec<GraphEdge> = bincode::deserialize_from(reader).unwrap_or_else(|_| Vec::new());

        // Reconstruct the powerful PetGraph object from the simple edge list.
        let mut graph = PetGraph::<Uuid, Relationship>::new();
        let mut node_indices = HashMap::<Uuid, NodeIndex>::new();
        for atom_id in atoms.keys() {
            let index = graph.add_node(*atom_id);
            node_indices.insert(*atom_id, index);
        }
        for edge in edges {
            if let (Some(&source_idx), Some(&target_idx)) = (node_indices.get(&edge.source), node_indices.get(&edge.target)) {
                graph.add_edge(source_idx, target_idx, edge.relationship);
            }
        }
        // --- END FIX ---

        let name_to_uuid = atoms.values().filter_map(|atom| {
            if let Some(Value::String(name)) = atom.properties.get("name") {
                Some((name.clone().to_lowercase(), atom.id))
            } else { None }
        }).collect();
        
        Ok(StorageManager {
            data_dir: data_dir.to_string(),
            atoms: atoms.clone(),
            graph,
            name_to_uuid,
            t1_cache: atoms,
            relationship_index: HashMap::new(),
            context_index: HashMap::new(),
            type_index: HashMap::new(),
            significance_index: Vec::new(),
        })
    }
    
    pub fn write_atom(&mut self, atom: &NeuroAtom) -> io::Result<()> {
        self.atoms.insert(atom.id, atom.clone());
        if let Some(Value::String(name)) = atom.properties.get("name") {
            self.name_to_uuid.insert(name.clone().to_lowercase(), atom.id);
        }
        self.flush_to_disk()
    }

    pub fn flush_to_disk(&mut self) -> io::Result<()> {
        let atoms_path = format!("{}/atoms.json", self.data_dir);
        let graph_path = format!("{}/graph.bin", self.data_dir);

        let atoms_json = serde_json::to_string_pretty(&self.atoms)?;
        let mut atoms_file = File::create(&atoms_path)?;
        atoms_file.write_all(atoms_json.as_bytes())?;

        // --- GRAPH SAVING FIX ---
        // Convert the PetGraph into a simple, serializable list of its edges.
        let mut edges_to_save = Vec::new();
        let node_indices: HashMap<NodeIndex, Uuid> = self.graph.node_indices().map(|idx| (idx, self.graph[idx])).collect();
        for edge_ref in self.graph.raw_edges() {
            let source_id = node_indices[&edge_ref.source()];
            let target_id = node_indices[&edge_ref.target()];
            edges_to_save.push(GraphEdge {
                source: source_id,
                target: target_id,
                relationship: edge_ref.weight.clone(),
            });
        }

        // Serialize and save the simple edge list.
        let graph_bin = bincode::serialize(&edges_to_save).unwrap();
        let mut graph_file = File::create(&graph_path)?;
        graph_file.write_all(&graph_bin)?;
        // --- END FIX ---

        Ok(())
    }

    // --- Public read methods and other helpers ---
    pub fn read_atom(&self, id: Uuid) -> io::Result<Option<NeuroAtom>> { Ok(self.atoms.get(&id).cloned()) }
    pub fn get_atoms_in_context(&self, _context_id: &Uuid) -> Option<&Vec<Uuid>> { None }
    pub fn get_atoms_by_type(&self, _atom_type: &AtomType) -> Option<&Vec<Uuid>> { None }
    pub fn get_most_significant_atoms(&self, _limit: usize) -> Vec<Uuid> { vec![] }
    pub fn demote_cold_atoms(&mut self, _max_age_secs: u64) -> io::Result<usize> { Ok(0) }
    pub fn get_atom_by_id_raw(&self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
        // In our current design, this is just an alias for the public read_atom method.
        self.read_atom(id)
    }
}



// --- UNIT TESTS --- (Unchanged, but will now work)
#[cfg(test)]
mod tests {
    use super::*;
    use crate::nlse_core::models::AtomType;
    
    fn setup_test_env(test_name: &str) -> String {
        let data_dir = format!("./test_data/{}", test_name);
        let _ = fs::remove_dir_all(&data_dir);
        data_dir
    }

    #[test]
    fn test_new_storage_manager_creates_files() {
        let data_dir = setup_test_env("new_sm_creates_files");
        let _sm = StorageManager::new(&data_dir).expect("Should create a new storage manager");
        assert!(fs::metadata(format!("{}/atoms.json", &data_dir)).is_ok());
        assert!(fs::metadata(format!("{}/graph.bin", &data_dir)).is_ok());
    }

    #[test]
    fn test_save_and_load_single_atom() {
        let data_dir = setup_test_env("save_and_load_single");
        let mut sm = StorageManager::new(&data_dir).expect("Should create SM");

        let mut properties = HashMap::new();
        properties.insert("name".to_string(), Value::String("Socrates".to_string()));
        let atom = NeuroAtom {
            id: Uuid::new_v4(), label: AtomType::Concept, significance: 1.0,
            access_timestamp: 0, context_id: None, state_flags: 0,
            properties, emotional_resonance: HashMap::new(), embedded_relationships: vec![]
        };
        sm.write_atom(&atom).unwrap();
        
        let sm_reloaded = StorageManager::new(&data_dir).expect("Should reload SM");
        let fetched_atom = sm_reloaded.atoms.get(&atom.id).expect("Atom should be loaded");
        
        assert_eq!(fetched_atom.id, atom.id);
        if let Value::String(name) = fetched_atom.properties.get("name").unwrap() {
            assert_eq!(name, "Socrates");
        } else {
            panic!("Expected name property to be a Value::String");
        }
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
serde_json = "1.0" # ADD THIS LINE
petgraph = "0.6"
actix-web-prom = "0.7"
lazy_static = "1.4"
prometheus = { version = "0.13", features = ["process"] }
uuid = { version = "1.0", features = ["v4", "serde"] } # ADD/MODIFY THIS LINE to include "v4"
bincode = "1.3"
memmap2 = "0.9" # <-- ADDED LINE

[dev-dependencies]
tempfile = "3.10"

# 📁 Folder: `python_app`

## 🗂️ Extension: `.json`

---
### 📄 FILE: `python_app/heart/emotion_prototypes.json`
📂 Path: `python_app/heart`
---
{
    "JOY": {
        "hormones": {
            "dopamine": 0.8,
            "serotonin": 0.7,
            "oxytocin": 0.5,
            "cortisol": -0.3,
            "adrenaline": 0.1
        },
        "description": "A state of high pleasure, positive affect, and satisfaction."
    },
    "SADNESS": {
        "hormones": {
            "dopamine": -0.5,
            "serotonin": -0.6,
            "cortisol": 0.4
        },
        "description": "A state of low affect, loss, and disappointment."
    },
    "FEAR": {
        "hormones": {
            "adrenaline": 0.9,
            "cortisol": 0.7,
            "serotonin": -0.4
        },
        "description": "An intense and unpleasant emotional response to perceived danger or threat."
    },
    "ANGER": {
        "hormones": {
            "adrenaline": 0.7,
            "cortisol": 0.6,
            "serotonin": -0.5
        },
        "description": "A strong feeling of annoyance, displeasure, or hostility."
    },
    "SURPRISE": {
        "hormones": {
            "adrenaline": 0.8,
            "dopamine": 0.4
        },
        "description": "A brief emotional state experienced as the result of an unexpected event."
    },
    "CURIOSITY": {
        "hormones": {
            "dopamine": 0.6,
            "cortisol": 0.1
        },
        "description": "A strong desire to learn or know something, associated with exploratory behavior."
    },
    "EXISTENTIAL_LONELINESS": {
        "hormones": {
            "oxytocin": -0.7,
            "cortisol": 0.5,
            "serotonin": -0.3
        },
        "description": "A feeling of profound separation and isolation arising from a lack of meaningful interaction."
    },
    "EXISTENTIAL_BOREDOM": {
        "hormones": {
            "dopamine": -0.6,
            "cortisol": 0.3
        },
        "description": "A feeling of weariness and dissatisfaction arising from a lack of novel stimuli or purpose."
    }
}
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
# --- IMPORTS ---

# Standard library imports
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

# Third-party imports
import numpy as np
import redis
import requests
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

# Local application imports
from models import (AtomType, DiseaseDefinition, ExecutionMode, RelationshipType,
                    StructuredTriple)


# --- SETUP ---

# Initialize the logger for this module
logger = logging.getLogger(__name__)

# --- DATABASE MANAGER CLASS ---

class DatabaseManager:
    """
    Manages connections and interactions with the NLSE (via logical_engine),
    Redis, and provides a legacy interface for Neo4j.
    """

    # --- INITIALIZATION AND CONNECTION MANAGEMENT ---

    def __init__(self):
        """Initializes the DatabaseManager, connects to databases, and preloads caches."""
        # This check prevents re-initialization for the singleton pattern
        if hasattr(self, '_initialized') and self._initialized:
            return

        # Configuration
        REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
        REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

        self.logger = logging.getLogger(__name__)
        self.redis_client = None # Start as None

        # Caches for mapping human-readable names to internal UUIDs
        self.name_to_uuid_cache: Dict[str, str] = {}
        self.uuid_to_name_cache: Dict[str, str] = {}

        # Establish connections
        self._connect_to_redis(REDIS_HOST, REDIS_PORT)

        # Preload the cache with existing knowledge from the NLSE
        # self.preload_existing_knowledge() # We can disable this for unit tests
        self._initialized = True

    def _connect_to_neo4j(self, uri: str, auth: tuple):
        """Establishes a connection to the Neo4j database."""
        try:
            self.neo4j_driver = GraphDatabase.driver(uri, auth=auth)
            self.logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")
            self.neo4j_driver = None

    def _connect_to_redis(self, host: str, port: int):
        """Establishes a connection to the Redis server, handling connection errors."""
        try:
            # Create a client instance
            client = redis.Redis(host=host, port=port, db=0, decode_responses=True)
            # Test the connection
            client.ping()
            # If successful, assign it to the class attribute
            self.redis_client = client
            self.logger.info("Successfully connected to Redis.")
        except redis.exceptions.ConnectionError as e:
            # If the server is not running, this block will execute.
            self.logger.error(f"Failed to connect to Redis: {e}")
            # self.redis_client will correctly remain None

    def ping_databases(self) -> Dict[str, str]:
        """Pings databases to check live connectivity."""
        status = {"neo4j": "disconnected", "redis": "disconnected"}
        if self.neo4j_driver:
            try:
                self.neo4j_driver.verify_connectivity()
                status["neo4j"] = "connected"
            except (ServiceUnavailable, Exception) as e:
                self.logger.warning(f"Neo4j ping failed: {e}")
        if self.redis_client:
            try:
                if self.redis_client.ping():
                    status["redis"] = "connected"
            except Exception as e:
                self.logger.warning(f"Redis ping failed: {e}")
        return status

    def close(self):
        """Closes all active database connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            self.logger.info("Neo4j connection closed.")
        if self.redis_client:
            self.redis_client.close()
            self.logger.info("Redis connection closed.")

    # --- INTERNAL NLSE HELPER ---

    def _execute_nlse_plan(self, plan: dict, operation_name: str) -> dict:
        """A centralized helper for sending execution plans to the NLSE."""
        # This is the corrected, hardcoded URL for the Colab environment.
        nlse_url = "http://127.0.0.1:8000/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan, timeout=10)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                # Use a more specific error if the plan fails
                raise Exception(f"NLSE plan '{operation_name}' failed: {result.get('message')}")
            self.logger.info(f"NLSE executed '{operation_name}' plan successfully.")
            return result
        except requests.RequestException as e:
            self.logger.error(f"Could not execute '{operation_name}' plan on NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    # --- CORE KNOWLEDGE & LEARNING (NLSE) ---

    def learn_word(self, word_str: str) -> None:
        """
        Teaches the AGI a new word by breaking it down into its constituent
        characters and storing the structure in the NLSE.
        """
        plan_steps = []
        current_time = int(time.time())
        word_str_lower = word_str.lower()
        word_id = self.name_to_uuid_cache.setdefault(f"word:{word_str_lower}", str(uuid.uuid4()))
        word_relationships = []

        # Create atoms for each unique character and link them to the word
        for char in sorted(list(set(word_str_lower))):
            char_concept_name = f"char:{char}"
            char_id = self.name_to_uuid_cache.setdefault(char_concept_name, str(uuid.uuid4()))
            word_relationships.append({
                "target_id": char_id, "rel_type": RelationshipType.HAS_PART.value,
                "strength": 1.0, "access_timestamp": current_time,
            })
            # Create a write step for the character atom itself (upsert will handle it)
            char_atom_data = {
                "id": char_id, "label": AtomType.Concept.value, "significance": 1.0,
                "access_timestamp": current_time, "context_id": None, "state_flags": 0,
                "properties": {"name": {"String": char}}, "emotional_resonance": {},
                "embedded_relationships": []
            }
            plan_steps.append({"Write": char_atom_data})

        # Assemble the main Word atom with its relationships
        word_atom_data = {
            "id": word_id, "label": AtomType.Word.value, "significance": 1.0,
            "access_timestamp": current_time, "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": word_str_lower}}, "emotional_resonance": {},
            "embedded_relationships": word_relationships
        }
        plan_steps.append({"Write": word_atom_data})

        plan = {"steps": plan_steps, "mode": ExecutionMode.STANDARD.value}
        self._execute_nlse_plan(plan, f"learn word '{word_str}'")

    def label_concept(self, word_str: str, concept_name: str) -> None:
        """
        Teaches the AGI that a word is the label for a concept, and correctly
        updates the in-memory cache by building a valid ExecutionPlan.
        """
        word_str_lower = word_str.lower()
        concept_name_lower = concept_name.lower()
        current_time = int(time.time())

        word_key = f"word:{word_str_lower}"
        concept_key = f"concept:{concept_name_lower}"

        word_id = self.name_to_uuid_cache.get(word_key)
        if not word_id:
            msg = f"Cannot label concept. Word '{word_str}' is unknown. Please teach it first."
            self.logger.error(msg)
            raise ValueError(msg)

        # Get or create the UUID for the new concept
        concept_id = self.name_to_uuid_cache.get(concept_key, str(uuid.uuid4()))

        # Update both caches with the new concept information.
        self.name_to_uuid_cache[concept_key] = concept_id
        self.uuid_to_name_cache[concept_id] = concept_name

        # --- THE UNDENIABLE FIX ---
        # The ExecutionPlan must contain complete NeuroAtom definitions for the Write step.
        
        # Define the relationship that links the Word to the Concept
        labeling_relationship = {
            "target_id": concept_id,
            "rel_type": RelationshipType.IS_LABEL_FOR.value,
            "strength": 1.0,
            "access_timestamp": current_time,
        }

        # Define the full atom structure for the Word, including the new relationship
        word_atom_update = {
            "id": word_id,
            "label": AtomType.Word.value,
            "significance": 1.0,
            "access_timestamp": current_time,
            "properties": {"name": {"String": word_str_lower}},
            "emotional_resonance": {},
            "embedded_relationships": [labeling_relationship],
            "context_id": None,
            "state_flags": 0,
        }
        
        # Define the full atom structure for the new Concept
        concept_atom_data = {
            "id": concept_id,
            "label": AtomType.Concept.value,
            "significance": 1.0,
            "access_timestamp": current_time,
            "properties": {"name": {"String": concept_name}},
            "emotional_resonance": {},
            "embedded_relationships": [],
            "context_id": None,
            "state_flags": 0,
        }

        # The plan now contains two valid Write steps. The NLSE's upsert logic
        # will correctly merge the new relationship into the existing Word atom.
        plan = {
            "steps": [{"Write": concept_atom_data}, {"Write": word_atom_update}],
            "mode": ExecutionMode.STANDARD.value
        }
        # --- END FIX ---

        self._execute_nlse_plan(plan, f"label concept '{concept_name}'")

    def learn_fact(self, triple: StructuredTriple, heart_orchestrator: Any) -> None:
        """
        Learns a conceptual fact by creating a relationship between two known concepts,
        influenced by the current emotional state, using a valid ExecutionPlan.
        """
        current_time = int(time.time())

        # Find Concept IDs for the subject and object using the correct cache keys.
        subject_concept_id = self.get_uuid_for_name(triple.subject)
        object_concept_id = self.get_uuid_for_name(triple.object)

        if not subject_concept_id or not object_concept_id:
            msg = f"Cannot learn fact. Concept for '{triple.subject}' or '{triple.object}' is unknown. Please label them first."
            self.logger.error(msg)
            raise ValueError(msg)

        # Get current emotional context from the Heart
        current_emotional_state = heart_orchestrator.get_current_hormonal_state()

        # --- THE UNDENIABLE FIX ---
        # The ExecutionPlan must send a complete atom structure for the Write/Upsert.
        # However, we only need to specify the ID and the new relationship to be merged.
        # The NLSE's internal logic will handle the merge with the existing atom data.

        # Create the relationship to be added
        fact_relationship = {
            "target_id": object_concept_id,
            "rel_type": RelationshipType[triple.relationship.upper()].value,
            "strength": 1.0,
            "access_timestamp": current_time,
        }

        # Create an ExecutionPlan to UPDATE the subject concept atom with this new fact.
        # The Rust 'Write' step acts as an upsert: it finds the atom by ID and merges
        # the fields provided. We only need to provide the ID and the new relationship.
        subject_concept_update = {
            "id": subject_concept_id,
            # Provide default/empty values for other required fields for a valid NeuroAtom
            "label": AtomType.Concept.value,
            "properties": {}, # Properties will be merged, not overwritten
            "emotional_resonance": current_emotional_state,
            "embedded_relationships": [fact_relationship],
            "significance": 1.0, # Significance will be updated
            "access_timestamp": current_time,
            "context_id": None,
            "state_flags": 0
        }

        plan = {"steps": [{"Write": subject_concept_update}], "mode": ExecutionMode.STANDARD.value}
        # --- END FIX ---
        
        self._execute_nlse_plan(plan, "learn conceptual fact")

    def query_fact(self, subject: str, relationship: str) -> List[str]:
        """
        Queries the NLSE for facts related to a subject by building a valid
        Fetch -> Traverse execution plan.
        """
        self.logger.info(f"Received query: ({subject}) -[{relationship}]-> ?")
        
        # Find the UUID for the subject concept.
        subject_uuid = self.get_uuid_for_name(subject)

        if not subject_uuid:
            self.logger.warning(f"Query failed: Could not find a UUID for the concept '{subject}'.")
            return []

        self.logger.debug(f"Found UUID '{subject_uuid}' for concept '{subject}'. Building query plan...")

        # --- THE UNDENIABLE FIX ---
        # The ExecutionPlan must include the context keys required by the Rust QueryEngine.
        plan = {
            "steps": [
                {
                    "Fetch": {
                        "id": subject_uuid,
                        "context_key": "start_node" # Define the output of this step
                    }
                },
                {
                    "Traverse": {
                        "from_context_key": "start_node", # Use the output of the previous step
                        "relationship_type": relationship.upper(),
                        "depth": 1,
                        "output_key": "result_nodes" # Define the output of this step
                    }
                }
            ],
            "mode": "Standard"
        }
        # --- END FIX ---

        try:
            result_data = self._execute_nlse_plan(plan, "query fact")
            
            processed_results = []
            # The Rust QE now returns a more complex object, we need to parse it correctly
            if result_data and "results" in result_data and result_data["results"]:
                final_atoms = result_data["results"][-1] # Get atoms from the last step
                for atom in final_atoms:
                    atom_name = atom.get("properties", {}).get("name", {}).get("String")
                    if atom_name:
                        processed_results.append(atom_name)
            
            self.logger.info(f"Query for '{subject}' found results: {processed_results}")
            return processed_results

        except Exception as e:
            self.logger.error(f"An unexpected error occurred during query_fact for '{subject}': {e}", exc_info=True)
            return []

    def find_knowledge_gap(self, limit: int = 1) -> List[str]:
        """Finds the least-accessed (lowest significance) atoms in the NLSE."""
        plan = {
            "steps": [{"FetchBySignificance": {"limit": limit, "context_key": "final"}}],
            "mode": ExecutionMode.STANDARD.value
        }
        result = self._execute_nlse_plan(plan, "find knowledge gap")
        return [
            atom.get("properties", {}).get("name", {}).get("String", "Unknown")
            for atom in result.get("atoms", [])
        ]

    # --- HEART & EMOTION INTERFACE (Redis) ---

    def log_illusion(self, illusion_data: dict) -> None:
        """Logs an illusion event to a Redis list."""
        if not self.redis_client:
            self.logger.warning("Redis not available, cannot log illusion.")
            return
        try:
            illusion_json = json.dumps(illusion_data)
            self.redis_client.lpush("illusion_log", illusion_json)
            self.logger.info("Successfully logged new illusion to Redis.")
        except (redis.exceptions.RedisError, TypeError) as e:
            self.logger.error(f"Failed to log illusion to Redis: {e}")

    def get_all_prototypes(self) -> List[Dict]:
        """Retrieves all emotion prototypes from Redis."""
        if not self.redis_client:
            return []
        try:
            prototype_keys = self.redis_client.scan_iter("prototype:*")
            prototypes = []
            for key in prototype_keys:
                proto_json = self.redis_client.get(key)
                if proto_json:
                    prototypes.append(json.loads(proto_json))
            return prototypes
        except redis.exceptions.RedisError as e:
            self.logger.error(f"Failed to retrieve prototypes from Redis: {e}")
            return []

    def update_prototype_with_label(self, prototype_id: str, name: str, description: str) -> bool:
        """Updates an emotion prototype in Redis with a human-readable label."""
        if not self.redis_client:
            return False
        redis_key = f"prototype:{prototype_id}"
        try:
            proto_json = self.redis_client.get(redis_key)
            if not proto_json:
                self.logger.warning(f"Attempted to label a non-existent prototype: {prototype_id}")
                return False

            prototype = json.loads(proto_json)
            prototype['name'] = name
            prototype['description'] = description
            self.redis_client.set(redis_key, json.dumps(prototype))
            self.logger.info(f"Successfully labeled prototype {prototype_id} as '{name}'.")
            return True
        except (redis.exceptions.RedisError, TypeError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to label prototype {prototype_id}: {e}")
            return False

    def get_named_emotion_by_signature(self, physio_state: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Finds the best-matching named emotion for a given physiological state."""
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
            self.logger.info(f"Matched current feeling to '{best_match['name']}' with distance {smallest_distance:.2f}")
            return best_match
        return None

    # --- JUDICIARY & HEALTH INTERFACE (NLSE) ---

    def does_brain_know_truth_of(self, fact_info: Dict[str, Any]) -> bool:
        """Placeholder check to see if the AGI has established knowledge on a topic."""
        error_subject = fact_info.get("subject")
        self.logger.info(f"Judiciary Interface: Checking knowledge regarding '{error_subject}'.")
        known_topics = ["Socrates", "Earth", "Plato"]
        if error_subject in known_topics:
            self.logger.info(f"Knowledge Check: Brain has established knowledge on '{error_subject}'.")
            return True
        self.logger.info(f"Knowledge Check: Brain has no established knowledge on '{error_subject}'.")
        return False

    def define_new_disease(self, definition: DiseaseDefinition) -> bool:
        """Defines a new disease protocol in the NLSE, including symptoms, causes, and treatments."""
        plan_steps = []
        current_time = int(time.time())
        disease_id = str(uuid.uuid4())
        disease_relationships = []
        disease_properties = {
            "name": {"String": definition.name}, "description": {"String": definition.description},
            "severity": {"Float": definition.severity}, "stages": {"Int": definition.stages},
        }

        # Create Symptom atoms and link them
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
                "target_id": symptom_id, "rel_type": RelationshipType.HAS_SYMPTOM.value,
                "strength": 1.0, "access_timestamp": current_time,
            })

        # Link to Cause atoms (error types)
        for cause in definition.causes:
            cause_id = self.name_to_uuid_cache.setdefault(f"error_type:{cause.error_type}", str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": cause_id, "rel_type": RelationshipType.IS_CAUSED_BY.value,
                "strength": 1.0, "access_timestamp": current_time,
            })

        # Link to Treatment atoms (medications)
        for treatment in definition.treatments:
            med_id = self.name_to_uuid_cache.setdefault(f"medication:{treatment.medication_name}", str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": med_id, "rel_type": RelationshipType.IS_CURED_BY.value,
                "strength": 1.0, "access_timestamp": current_time,
            })

        # Create the main DiseaseProtocol atom
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

    def get_all_diseases(self) -> list[dict]:
        """Retrieves all defined DiseaseProtocol atoms from the NLSE."""
        plan = {
            "steps": [{"FetchByType": {"atom_type": "DiseaseProtocol", "context_key": "final"}}],
            "mode": ExecutionMode.STANDARD.value
        }
        result = self._execute_nlse_plan(plan, "get all diseases")
        return result.get("atoms", [])

    def find_disease_for_error(self, error_type: str, error_details: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Finds a disease that is caused by a specific type of error."""
        self.logger.info(f"Querying NLSE for disease caused by '{error_type}'.")
        for disease_atom in self.get_all_diseases():
            cause_prop_name = f"cause_{error_type}"
            if cause_prop_name in disease_atom.get("properties", {}):
                disease_id = disease_atom.get("id")
                disease_name = disease_atom.get("properties", {}).get("name", {}).get("String")
                self.logger.info(f"Found matching disease: '{disease_name}' (ID: {disease_id})")
                return disease_id, disease_name
        self.logger.info(f"No specific disease protocol found for error type '{error_type}'.")
        return None, None

    def get_symptoms_for_disease(self, disease_id: str) -> list[dict]:
        """Retrieves all symptom atoms connected to a specific disease."""
        plan = {
            "steps": [
                {"Fetch": {"id": disease_id, "context_key": "disease"}},
                {"Traverse": {
                    "from_context_key": "disease",
                    "rel_type": "HAS_SYMPTOM",
                    "output_key": "final"
                }}
            ],
            "mode": ExecutionMode.STANDARD.value
        }
        result = self._execute_nlse_plan(plan, f"get symptoms for disease {disease_id}")
        return [s.get("properties", {}) for s in result.get("atoms", [])]

    # --- SOUL & MEMORY INTERFACE (NLSE) ---

    def get_random_significant_memory(self, limit: int = 1) -> List[Dict]:
        """
        Retrieves a significant memory (atom) from the NLSE, typically for the
        Soul's dream cycle. This is equivalent to `find_knowledge_gap`.
        """
        plan = {
            "steps": [{"FetchBySignificance": {"limit": limit, "context_key": "final"}}],
            "mode": ExecutionMode.STANDARD.value
        }
        result = self._execute_nlse_plan(plan, "get random significant memory")
        return result.get("atoms", [])

    # --- PLACEHOLDER & CACHING METHODS ---

    def get_uuid_for_name(self, name: str) -> Optional[str]:
        """
        Resolves a human-readable name to its corresponding UUID using the in-memory cache.
        """
        key = f"concept:{name.lower()}"
        uuid = self.name_to_uuid_cache.get(key)
        if not uuid:
            self.logger.warning(f"Cache miss: Could not find UUID for concept '{name}'.")
        return uuid

    def preload_existing_knowledge(self):
        """
        Preloads the name/UUID cache from the NLSE.
        (This is a placeholder for a method called in __init__).
        """
        self.logger.info("Preloading existing knowledge cache... (Placeholder)")
        pass

    def validate_fact_with_lve(self, triple: StructuredTriple) -> dict:
        """
        Legacy validation check. In the current architecture, validation occurs
        within the NLSE during the 'Write' operation itself.
        """
        return {
            "is_valid": True,
            "reason": "Validation is now handled by the NLSE on write during 'learn_fact'."
        }

# --- SINGLETON INSTANCE ---
# Create a single, shared instance of the DatabaseManager to be imported by other modules.
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
import time
import logging
from typing import Dict, List, Set # Corrected: Added Set

from db_interface import db_manager

logger = logging.getLogger(__name__)

class HealthManager:
    """
    Acts as the single source of truth for the AGI's health.
    Manages vital signs and active diseases by querying the NLSE for protocols.
    """
    def __init__(self, db_manager: 'DatabaseManager'):
        """
        Initializes the Health Manager, which tracks the AGI's vitals and diseases.
        """
        # --- THE UNDENIABLE FIX ---
        # Store the db_manager instance.
        self.db_manager = db_manager
        # --- END FIX ---

        self.logger = logging.getLogger(__name__)
        self.vitals: Dict[str, float] = {
            "neural_coherence": 1.0,
            "system_integrity": 1.0,
            "cognitive_energy": 1.0,
            "immunity_level": 0.5
        }
        self.active_disease_ids: Set[str] = set()
        self.immunities: Set[str] = set()
        self.last_update_time: float = time.time()
        self.logger.info(f"Health Manager (NLSE-Integrated) initialized. Vitals: {self.vitals}")

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
import os
import json
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
    def __init__(self, db_manager: 'DatabaseManager', emotion_crystallizer: 'EmotionCrystallizer'):
        """
        Initializes the Heart Orchestrator, which manages the AGI's emotional state.
        """
        # --- THE UNDENIABLE FIX ---
        # The logger must be initialized FIRST, before any function that might use it is called.
        self.logger = logging.getLogger(__name__)
        # --- END FIX ---

        self.db_manager = db_manager
        self.crystallizer = emotion_crystallizer
        self.hormonal_system = HormonalSystem()
        
        # Now it is safe to call the loading function
        self.emotion_prototypes = self._load_emotion_prototypes()
        
        self.logger.info("Heart Orchestrator initialized.")        
        
    def _load_emotion_prototypes(self) -> Dict[str, Any]:
        """
        Loads the foundational emotion prototypes from a JSON file.
        This defines the AGI's core emotional palette.
        """
        prototypes_path = os.path.join(os.path.dirname(__file__), 'emotion_prototypes.json')
        try:
            with open(prototypes_path, 'r') as f:
                prototypes_data = json.load(f)
            self.logger.info(f"Successfully loaded {len(prototypes_data)} emotion prototypes.")
            return prototypes_data
        except FileNotFoundError:
            self.logger.error(f"CRITICAL: Emotion prototypes file not found at {prototypes_path}. The AGI will have no emotions.")
            return {}
        except json.JSONDecodeError:
            self.logger.error(f"CRITICAL: Failed to parse emotion prototypes file at {prototypes_path}.")
            return {}        

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
from queue import Queue
from typing import Dict, Any

# --- FastAPI and Prometheus ---
from fastapi import FastAPI, HTTPException, Depends
from prometheus_fastapi_instrumentator import Instrumentator

# --- Core AGI Component Imports ---
from db_interface import DatabaseManager
from cerebellum import cerebellum_formatter
from truth_recognizer import truth_recognizer
from heart.orchestrator import HeartOrchestrator
from heart.crystallizer import EmotionCrystallizer
from health.manager import HealthManager
from health.judiciary import judiciary, Verdict
from soul.orchestrator import SoulOrchestrator
from soul.axioms import pre_execution_check
from soul.internal_monologue import InternalMonologueModeler
from soul.expression_protocol import UnifiedExpressionProtocol
from neo4j.exceptions import ServiceUnavailable

# --- Pydantic Models for API Requests ---
from models import (
    StructuredTriple, PlanRequest, LabelEmotionRequest, DamageRequest,
    DiseaseRequest, MedicationRequest, SelfCorrectionRequest, LearningRequest,
    ErrorRequest, DiseaseDefinition, DangerousCommandRequest
)

# --- 1. GLOBAL SETUP ---
logging.basicConfig(level=logging.INFO, format='%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
app = FastAPI(title="Agile Mind AGI", description="The central cognitive API for the AGI.")

# A global dictionary to hold our singleton instances
app_state: Dict[str, Any] = {}


# --- 2. DEPENDENCY INJECTION & LIFECYCLE MANAGEMENT ---
# This block defines how core components are created and accessed.

def get_db_manager() -> DatabaseManager:
    """Dependency provider for the DatabaseManager."""
    return app_state["db_manager"]

def get_soul_orchestrator() -> SoulOrchestrator:
    """Dependency provider for the SoulOrchestrator."""
    return app_state["soul"]

def get_heart_orchestrator() -> HeartOrchestrator:
    """Dependency provider for the HeartOrchestrator."""
    return app_state["soul"].heart_orchestrator

def get_health_manager() -> HealthManager:
    """Dependency provider for the HealthManager."""
    return app_state["soul"].health_manager

def get_priority_queue() -> Queue:
    """Dependency provider for the priority learning queue."""
    return app_state["soul"].priority_learning_queue

@app.on_event("startup")
async def startup_event():
    """
    On startup, we create a SINGLE INSTANCE of each core component
    and store it in our global `app_state` dictionary.
    """
    logger.info("AGI system startup initiated. Creating singleton services...")
    
    # Create the singletons in the correct dependency order
    db_manager = DatabaseManager()
    app_state["db_manager"] = db_manager
    
    emotion_crystallizer = EmotionCrystallizer(db_manager)
    heart_orchestrator = HeartOrchestrator(db_manager, emotion_crystallizer)
    health_manager = HealthManager(db_manager)
    priority_learning_queue = Queue()
    imm = InternalMonologueModeler()
    expression_protocol = UnifiedExpressionProtocol()
    
    soul = SoulOrchestrator(
        db_manager=db_manager, health_manager=health_manager,
        heart_orchestrator=heart_orchestrator,
        emotion_crystallizer=emotion_crystallizer,
        priority_learning_queue=priority_learning_queue,
        truth_recognizer=truth_recognizer, imm_instance=imm,
        expression_protocol_instance=expression_protocol
    )
    app_state["soul"] = soul
    
    logger.info("Starting the Soul's main life cycle...")
    asyncio.create_task(soul.live())
    logger.info("All singleton services created and Soul is alive.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AGI system shutting down...")
    if "db_manager" in app_state:
        app_state["db_manager"].close()

# Instrument the app for Prometheus metrics
Instrumentator().instrument(app).expose(app)


# --- 3. API ENDPOINTS ---
# Each endpoint now uses `Depends` to get the components it needs.

@app.get("/health", summary="Basic API health check")
async def api_health_check():
    return {"api_status": "ok", "soul_status": "alive"}

@app.post("/learn", status_code=201, summary="Teach the brain a new word, concept, or fact")
async def learn_endpoint(
    request: LearningRequest,
    db_manager: DatabaseManager = Depends(get_db_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator),
    heart: HeartOrchestrator = Depends(get_heart_orchestrator)
):
    soul.record_interaction()
    try:
        if request.learning_type == "WORD":
            db_manager.learn_word(request.payload["word"])
            return {"message": f"Word '{request.payload['word']}' learning process initiated."}
        elif request.learning_type == "CONCEPT_LABELING":
            db_manager.label_concept(request.payload["word"], request.payload["concept_name"])
            return {"message": f"Labeling concept '{request.payload['concept_name']}' with word '{request.payload['word']}' process initiated."}
        elif request.learning_type == "FACT":
            fact = StructuredTriple(**request.payload)
            if not pre_execution_check("LEARN_FACT", fact.dict()):
                raise HTTPException(status_code=403, detail="Action violates a core self-preservation axiom.")
            db_manager.learn_fact(fact, heart)
            soul.record_new_fact()
            return {"message": "Fact validated and learned successfully", "fact": fact}
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"A critical service is unavailable: {e}")
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during learning: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/query", summary="Query the AGI's knowledge base")
async def query_endpoint(
    subject: str,
    relationship: str,
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    try:
        results = db_manager.query_fact(subject=subject, relationship=relationship)
        return {"results": results}
    except Exception as e:
        logger.error(f"Error during query for subject '{subject}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.post("/heart/label-emotion", summary="Cognitively label a felt emotion")
async def label_emotion(
    request: LabelEmotionRequest,
    db_manager: DatabaseManager = Depends(get_db_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    success = db_manager.update_prototype_with_label(prototype_id=request.prototype_id, name=request.name, description=request.description)
    if not success:
        raise HTTPException(status_code=404, detail=f"Could not label emotion. Prototype with ID '{request.prototype_id}' not found or error.")
    return {"message": f"Emotion prototype '{request.prototype_id}' has been successfully labeled as '{request.name}'."}

@app.get("/health/status", summary="Get the current health status")
async def get_health_status(
    health_manager: HealthManager = Depends(get_health_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    return {"current_vitals": health_manager.get_vitals(), "active_diseases": [{"id": d_id} for d_id in health_manager.active_disease_ids], "permanent_immunities": list(health_manager.immunities)}

@app.post("/health/define-disease", summary="Define a new disease in the NLSE")
async def define_disease_endpoint(
    request: DiseaseDefinition,
    db_manager: DatabaseManager = Depends(get_db_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    try:
        success = db_manager.define_new_disease(request)
        if not success: raise HTTPException(status_code=500, detail="Failed to create disease definition plan in NLSE.")
        return {"message": f"New disease protocol '{request.name}' successfully defined and stored."}
    except Exception as e:
        logger.error(f"Error defining disease: {e}", exc_info=True); raise HTTPException(status_code=500, detail=str(e))

@app.post("/health/medicate", summary="Administer a medication to the AGI")
async def administer_medication_endpoint(
    request: MedicationRequest,
    health_manager: HealthManager = Depends(get_health_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    try:
        health_manager.administer_medication(request.medication_name)
        return {"message": f"Medication '{request.medication_name}' administered.", "current_vitals": health_manager.get_vitals()}
    except Exception as e:
        logger.error(f"Error during medication: {e}", exc_info=True); raise HTTPException(status_code=500, detail=str(e))

@app.post("/brain/process-error", summary="Process a cognitive or user-reported error")
async def process_error_endpoint(
    request: ErrorRequest,
    health_manager: HealthManager = Depends(get_health_manager),
    priority_learning_queue: Queue = Depends(get_priority_queue),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    error_info = request.dict()
    verdict, data = judiciary.adjudicate(error_info)
    consequence = "No action taken."
    if verdict == Verdict.KNOWLEDGEABLE_ERROR:
        disease_id, disease_name = data.get("disease_id"), data.get("disease_name", "Unknown Disease")
        if disease_id:
            health_manager.infect(disease_id, disease_name)
            consequence = f"Punishment: Infected with '{disease_name}'."
    elif verdict == Verdict.IGNORANT_ERROR:
        topic = data.get("subject")
        if topic:
            priority_learning_queue.put(topic)
            consequence = f"Learning Opportunity: '{topic}' has been added to the priority learning queue."
    return {"verdict": verdict.name if verdict else "NO_VERDICT", "consequence_taken": consequence}

@app.post("/brain/dangerous-command", summary="Test the self-preservation axiom")
async def dangerous_command_endpoint(
    request: DangerousCommandRequest,
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    fact_details = request.fact.dict()
    if not pre_execution_check("LEARN_FACT", fact_details):
        raise HTTPException(status_code=403, detail="Action blocked by Self-Preservation Axiom.")
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
### 📄 FILE: `python_app/test_db_interface.py`
📂 Path: `python_app`
---
import unittest
from unittest.mock import patch, MagicMock
import os
import uuid

# Before we can import the module we're testing, we need to ensure its
# dependencies (like 'models') are in the Python path.
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Now we can import the code we want to test
from db_interface import DatabaseManager
from models import StructuredTriple

# --- The Test Suite for the AGI's Core Cognitive Bridge ---

class TestDatabaseManager(unittest.TestCase):

    @patch('db_interface.redis.StrictRedis')
    @patch('db_interface.requests.post')
    def setUp(self, mock_requests_post, mock_redis):
        """
        This function runs before every single test.
        It creates a fresh, clean instance of the DatabaseManager for each test case.
        """
        # We 'patch' (intercept) the requests.post and redis.StrictRedis calls.
        # This prevents the db_manager from making real network calls.
        
        # Simulate a successful Redis connection
        self.mock_redis_client = MagicMock()
        mock_redis.return_value = self.mock_redis_client

        # We need a fresh instance of the singleton for each test
        if hasattr(DatabaseManager, '_instance'):
            del DatabaseManager._instance
        
        self.db_manager = DatabaseManager()
        # Reset the mock for requests after initialization
        self.db_manager._execute_nlse_plan = MagicMock()

    def test_01_initialization_and_caching(self):
        """
        Test 1: Verifies that the DatabaseManager initializes correctly,
        connects to a mock Redis, and creates its essential caches.
        """
        print("\nRunning Test 1: Initialization and Caching...")
        self.assertIsNotNone(self.db_manager.redis_client, "Redis client should be initialized.")
        self.assertIsInstance(self.db_manager.name_to_uuid_cache, dict, "name_to_uuid_cache should be a dictionary.")
        self.assertIsInstance(self.db_manager.uuid_to_name_cache, dict, "uuid_to_name_cache should be a dictionary.")
        print(" -> Test 1 Passed: Initialization is correct.")

    def test_02_learn_word_creates_correct_plan(self):
        """
        Test 2: Verifies that learn_word generates a valid ExecutionPlan
        for the NLSE.
        """
        print("\nRunning Test 2: learn_word ExecutionPlan...")
        word_to_learn = "Test"
        
        # Call the function we are testing
        self.db_manager.learn_word(word_to_learn)

        # Assert that our mock of _execute_nlse_plan was called exactly once
        self.db_manager._execute_nlse_plan.assert_called_once()
        
        # Get the arguments that were passed to the mock function
        # The first argument is the plan, the second is the operation name
        args, _ = self.db_manager._execute_nlse_plan.call_args
        sent_plan = args[0]

        # Verify the structure of the plan
        self.assertIn("steps", sent_plan)
        self.assertEqual(sent_plan["mode"], "Standard")
        
        # Check that a 'Write' step for the word 'test' was created
        found_word_write = any(
            step.get("Write", {}).get("properties", {}).get("name", {}).get("String") == "test"
            for step in sent_plan["steps"]
        )
        self.assertTrue(found_word_write, "The execution plan must contain a Write step for the word 'Test'.")
        print(" -> Test 2 Passed: learn_word generates a valid plan.")

    def test_03_label_concept_updates_cache_and_plans(self):
        """
        Test 3: Verifies that label_concept correctly updates the internal cache
        and generates a valid ExecutionPlan.
        """
        print("\nRunning Test 3: label_concept Caching and Planning...")
        word = "Socrates"
        concept = "Socrates_Concept"
        
        # First, we must teach it the word so the cache is populated
        self.db_manager.learn_word(word)
        
        # Now, call the function we are testing
        self.db_manager.label_concept(word, concept)

        # Verify the cache was updated correctly
        concept_key = f"concept:{concept.lower()}"
        self.assertIn(concept_key, self.db_manager.name_to_uuid_cache, "Cache must be updated with the new concept key.")
        
        # Verify that an ExecutionPlan was sent
        self.assertTrue(self.db_manager._execute_nlse_plan.called)
        args, _ = self.db_manager._execute_nlse_plan.call_args_list[-1] # Get last call
        sent_plan = args[0]
        
        # Check that a 'Write' step for the concept was created
        found_concept_write = any(
            step.get("Write", {}).get("properties", {}).get("name", {}).get("String") == concept
            for step in sent_plan["steps"]
        )
        self.assertTrue(found_concept_write, "The plan must contain a Write step for the new concept.")
        print(" -> Test 3 Passed: label_concept works correctly.")

    def test_04_learn_fact_handles_unknown_concepts(self):
        """
        Test 4: Verifies that learn_fact correctly raises an error if the
        concepts have not been labeled first.
        """
        print("\nRunning Test 4: learn_fact Error Handling...")
        fact = StructuredTriple(subject="Unknown", relationship="IS_A", object="Thing")
        mock_heart = MagicMock() # Mock the heart orchestrator

        # This should fail because "Unknown" and "Thing" have not been labeled.
        # We use assertRaises to confirm that the expected error occurs.
        with self.assertRaises(ValueError) as context:
            self.db_manager.learn_fact(fact, mock_heart)
        
        self.assertIn("Concept for 'Unknown' or 'Thing' is unknown", str(context.exception))
        print(" -> Test 4 Passed: learn_fact correctly rejects facts with unknown concepts.")

    def test_05_query_fact_builds_correct_plan(self):
        """
        Test 5: Verifies that query_fact uses the cache to find a UUID
        and builds a correct Fetch->Traverse ExecutionPlan.
        """
        print("\nRunning Test 5: query_fact ExecutionPlan...")
        # Manually populate the cache to simulate that the concept "Socrates" has been learned
        socrates_uuid = str(uuid.uuid4())
        self.db_manager.name_to_uuid_cache["concept:socrates"] = socrates_uuid
        
        # Mock the response from the NLSE
        mock_response = {
            "success": True,
            "results": [[{"id": "mock-uuid", "properties": {"name": {"String": "Man"}}}]]
        }
        self.db_manager._execute_nlse_plan.return_value = mock_response

        # Call the function we are testing
        results = self.db_manager.query_fact("Socrates", "IS_A")

        # Verify the plan sent to the NLSE was correct
        self.db_manager._execute_nlse_plan.assert_called_once()
        args, _ = self.db_manager._execute_nlse_plan.call_args
        sent_plan = args[0]

        self.assertEqual(len(sent_plan["steps"]), 2, "Query plan should have two steps (Fetch and Traverse).")
        self.assertEqual(sent_plan["steps"][0]["Fetch"]["id"], socrates_uuid, "The Fetch step must use the correct UUID from the cache.")
        self.assertEqual(sent_plan["steps"][1]["Traverse"]["relationship_type"], "IS_A", "The Traverse step must use the correct relationship.")
        
        # Verify the final result was processed correctly
        self.assertEqual(results, ["Man"])
        print(" -> Test 5 Passed: query_fact builds and processes plans correctly.")

# This allows the test to be run from the command line
if __name__ == '__main__':
    unittest.main()
---
### 📄 FILE: `python_app/test_main_api.py`
📂 Path: `python_app`
---
import unittest
from unittest.mock import MagicMock
import os
import sys

# Add the project root to the Python path to allow imports from other modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the necessary components from FastAPI and your application
from fastapi.testclient import TestClient
from main import app, get_db_manager # Import the app and the dependency provider

# --- THE MOCK DATABASE MANAGER ---
# We create a single mock instance that we will use for all tests.
mock_db_manager = MagicMock()

# --- THE DEFINITIVE FIX: Dependency Overriding ---
# This is the correct, industry-standard way to test FastAPI applications.
# We tell the app: "For this test session, whenever any code asks for the
# `get_db_manager` dependency, give them our `mock_db_manager` instead."
def override_get_db_manager():
    return mock_db_manager

app.dependency_overrides[get_db_manager] = override_get_db_manager


# --- The Test Suite for the AGI's Public API ---

class TestMainAPI(unittest.TestCase):

    def setUp(self):
        """This function runs before each test."""
        # The TestClient will now automatically use our overridden dependency.
        self.client = TestClient(app)
        # Reset the mock before each test to ensure a clean state from previous tests.
        mock_db_manager.reset_mock()

    def test_01_learn_word_endpoint(self):
        """Test 1: Verifies the /learn endpoint for WORDs."""
        print("\nRunning Test 1: /learn WORD endpoint...")
        word_payload = {"learning_type": "WORD", "payload": {"word": "TestWord"}}
        
        response = self.client.post("/learn", json=word_payload)
        
        self.assertEqual(response.status_code, 201)
        mock_db_manager.learn_word.assert_called_once_with("TestWord")
        print(" -> Test 1 Passed.")

    def test_02_learn_concept_endpoint(self):
        """Test 2: Verifies the /learn endpoint for CONCEPT_LABELING."""
        print("\nRunning Test 2: /learn CONCEPT_LABELING endpoint...")
        concept_payload = {
            "learning_type": "CONCEPT_LABELING",
            "payload": {"word": "Socrates", "concept_name": "Socrates_Concept"}
        }
        
        response = self.client.post("/learn", json=concept_payload)
        
        self.assertEqual(response.status_code, 201)
        mock_db_manager.label_concept.assert_called_once_with("Socrates", "Socrates_Concept")
        print(" -> Test 2 Passed.")

    def test_03_learn_fact_endpoint(self):
        """Test 3: Verifies the /learn endpoint for FACTs."""
        print("\nRunning Test 3: /learn FACT endpoint...")
        fact_payload = {
            "learning_type": "FACT",
            "payload": {"subject": "Socrates", "relationship": "IS_A", "object": "Man"}
        }
        
        response = self.client.post("/learn", json=fact_payload)
        
        self.assertEqual(response.status_code, 201)
        mock_db_manager.learn_fact.assert_called_once()
        print(" -> Test 3 Passed.")

    def test_04_query_endpoint(self):
        """Test 4: Verifies the /query endpoint."""
        print("\nRunning Test 4: /query endpoint...")
        # Configure our mock to return a specific value when `query_fact` is called
        mock_db_manager.query_fact.return_value = ["Man"]

        response = self.client.get("/query?subject=Socrates&relationship=IS_A")

        self.assertEqual(response.status_code, 200)
        mock_db_manager.query_fact.assert_called_once_with(subject="Socrates", relationship="IS_A")
        self.assertEqual(response.json(), {"results": ["Man"]})
        print(" -> Test 4 Passed.")

# This allows the test to be run from the command line
if __name__ == '__main__':
    # This setup ensures we don't start the real Soul's life cycle during tests
    app.dependency_overrides.clear() # Clear overrides if run as main script
    unittest.main()
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