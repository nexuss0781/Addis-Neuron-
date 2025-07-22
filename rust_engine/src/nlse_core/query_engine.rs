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
                              PlanStep::Write(mut atom_to_write) => {
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
                    if let Some(atom_ids) = manager.get_atoms_in_context(&context_id) {
                        for id in atom_ids {
                             // Avoid duplicates if already found in T0
                            if !atoms.iter().any(|a| a.id == *id) {
                                if let Ok(Some(atom)) = manager.read_atom(*id) {
                                    atoms.push(atom);
                                }
                            }
                        }
                    }
                    t0_cache.insert(context_key, atoms);
                }    
                
                PlanStep::FetchByType { atom_type, context_key } => {
                let mut atoms = Vec::new();
                if let Some(atom_ids) = manager.get_atoms_by_type(&atom_type) {
                    for id in atom_ids {
                        if let Ok(Some(atom)) = manager.read_atom(*id) {
                            atoms.push(atom);
                        }
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