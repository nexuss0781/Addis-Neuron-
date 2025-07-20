use serde::{Deserialize, Serialize};
use uuid::Uuid;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use super::models::{NeuroAtom, RelationshipType};
use super::storage_manager::StorageManager;

#[derive(Serialize, Deserialize, Debug)]
pub enum FilterCondition {
    ByLabel(String),
}

#[derive(Serialize, Deserialize, Debug)]
pub enum PlanStep {
    Fetch { id: Uuid, context_key: String },
    Traverse { from_context_key: String, rel_type: RelationshipType, output_key: String },
    // Filter not implemented in this step, but the structure is here.
    // Filter(FilterCondition),
    // Write not implemented in this step.
    // Write(super::models::NeuroAtom),
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ExecutionPlan {
    pub steps: Vec<PlanStep>,
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

    /// Executes a plan and returns the result. This is the brain's "thinking" process.
    pub fn execute(&self, plan: ExecutionPlan) -> QueryResult {
        // --- T0 Synaptic Cache ---
        // A temporary workspace for this specific thought process.
        // It holds named results from previous steps.
        let mut t0_cache: HashMap<String, Vec<NeuroAtom>> = HashMap::new();

        for step in plan.steps {
            match step {
                PlanStep::Fetch { id, context_key } => {
                    let mut manager = self.storage_manager.lock().unwrap();
                    match manager.read_atom(id) {
                        Ok(Some(atom)) => {
                            t0_cache.insert(context_key, vec![atom]);
                        }
                        _ => return self.fail("Fetch failed: Atom ID not found."),
                    }
                }
                PlanStep::Traverse { from_context_key, rel_type, output_key } => {
                    if let Some(source_atoms) = t0_cache.get(&from_context_key) {
                        let mut results = Vec::new();
                        let mut manager = self.storage_manager.lock().unwrap();

                        for source_atom in source_atoms {
                            for rel in &source_atom.embedded_relationships {
                                if rel.rel_type == rel_type {
                                    if let Ok(Some(target_atom)) = manager.read_atom(rel.target_id) {
                                        results.push(target_atom);
                                    }
                                }
                            }
                        }
                        t0_cache.insert(output_key, results);
                    } else {
                        return self.fail("Traverse failed: Source context key not found in T0 cache.");
                    }
                }
            }
        }

        // After all steps, we assume the final result is in a key named "final".
        // This is a simple convention for now.
        let final_result = t0_cache.remove("final").unwrap_or_default();
        
        QueryResult {
            atoms: final_result,
            success: true,
            message: "Execution plan completed successfully.".to_string(),
        }
    }
    
    /// Helper function to return a failure state.
    fn fail(&self, message: &str) -> QueryResult {
        QueryResult {
            atoms: vec![],
            success: false,
            message: message.to_string(),
        }
    }
}