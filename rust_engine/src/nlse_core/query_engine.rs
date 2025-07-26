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
    use crate::nlse_core::models::{AtomType, RelationshipType, Value, NeuroAtom, Relationship};
    use std::fs;
    use std::sync::{Arc, Mutex};
    use uuid::Uuid;
    use std::collections::HashMap;

    fn setup_test_engine(test_name: &str) -> (QueryEngine, Uuid, Uuid) {
        let data_dir = format!("./test_data/{}", test_name);
        let _ = fs::remove_dir_all(&data_dir);
        
        let sm = Arc::new(Mutex::new(StorageManager::new(&data_dir).unwrap()));
        let qe = QueryEngine::new(Arc::clone(&sm));

        let socrates_id = Uuid::new_v4();
        let man_id = Uuid::new_v4();

        let socrates_atom = NeuroAtom {
            id: socrates_id, label: AtomType::Concept,
            properties: HashMap::from([("name".to_string(), Value::String("Socrates".to_string()))]),
            embedded_relationships: vec![Relationship { target_id: man_id, rel_type: RelationshipType::IsA, strength: 1.0, access_timestamp: 0 }],
            significance: 1.0, access_timestamp: 0, context_id: None, state_flags: 0, emotional_resonance: HashMap::new()
        };
        let man_atom = NeuroAtom {
            id: man_id, label: AtomType::Concept,
            properties: HashMap::from([("name".to_string(), Value::String("Man".to_string()))]),
            embedded_relationships: vec![],
            significance: 1.0, access_timestamp: 0, context_id: None, state_flags: 0, emotional_resonance: HashMap::new()
        };

        let plan = ExecutionPlan {
            steps: vec![ PlanStep::Write(socrates_atom), PlanStep::Write(man_atom) ],
            mode: ExecutionMode::Standard,
        };
        qe.execute(plan);
        (qe, socrates_id, man_id)
    }

    #[test]
    fn test_execute_fetch_plan() {
        let (qe, _, man_id) = setup_test_engine("fetch_plan");
        let fetch_plan = ExecutionPlan {
            steps: vec![PlanStep::Fetch { id: man_id, context_key: "result".to_string() }],
            mode: ExecutionMode::Standard,
        };

        let result = qe.execute(fetch_plan);
        assert!(result.success);
        
        // --- THE UNDENIABLE FIX ---
        // `result.atoms` is a Vec<NeuroAtom>, not a Vec<Vec<NeuroAtom>>.
        // We can assert its length directly.
        assert_eq!(result.atoms.len(), 1);
        assert_eq!(result.atoms[0].id, man_id);
    }

    #[test]
    fn test_execute_traverse_plan() {
        let (qe, socrates_id, man_id) = setup_test_engine("traverse_plan");
        let traverse_plan = ExecutionPlan {
            steps: vec![
                PlanStep::Fetch { id: socrates_id, context_key: "start_nodes".to_string() },
                PlanStep::Traverse { 
                    from_context_key: "start_nodes".to_string(), 
                    rel_type: RelationshipType::IsA, 
                    output_key: "end_nodes".to_string() 
                }
            ],
            mode: ExecutionMode::Standard,
        };

        let result = qe.execute(traverse_plan);
        assert!(result.success, "Execution should succeed");

        // --- THE UNDENIABLE FIX ---
        // `result.atoms` is a Vec<NeuroAtom>.
        assert_eq!(result.atoms.len(), 1, "Should find exactly one related atom");
        assert_eq!(result.atoms[0].id, man_id, "The atom found should be Man");
    }
}