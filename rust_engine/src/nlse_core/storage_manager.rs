// --- The Definitive, Corrected storage_manager.rs ---

use std::collections::HashMap;
use std::fs::{self, File}; // FIX: Correctly import fs and File
use std::io::{self, BufReader, Write};
use uuid::Uuid;
use bincode;
use petgraph::graph::Graph as PetGraph; // FIX: Import PetGraph and alias it

use crate::nlse_core::models::{NeuroAtom, Relationship, Value, AtomType}; // FIX: Import necessary models

/// Manages the persistence layer for NeuroAtoms and their relationships.
pub struct StorageManager {
    data_dir: String,
    // In-memory representation of all atoms
    pub atoms: HashMap<Uuid, NeuroAtom>,
    // The graph structure of relationships
    pub graph: PetGraph<Uuid, Relationship>,
    // A fast lookup from a concept's name to its UUID
    pub name_to_uuid: HashMap<String, Uuid>,
    // A fast in-memory cache for frequently accessed atoms
    pub t1_cache: HashMap<Uuid, NeuroAtom>,
    
    // Indexes for efficient querying
    pub relationship_index: HashMap<RelationshipType, Vec<Uuid>>,
    pub context_index: HashMap<Uuid, Vec<Uuid>>,
    pub type_index: HashMap<AtomType, Vec<Uuid>>,
    pub significance_index: Vec<(f32, Uuid)>,
}

impl StorageManager {
    /// Creates a new StorageManager, creating data files if they don't exist.
    pub fn new(data_dir: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let atoms_path = format!("{}/atoms.json", data_dir);
        let graph_path = format!("{}/graph.bin", data_dir);

        // Ensure the data directory exists
        fs::create_dir_all(data_dir)?;

        // If atoms.json doesn't exist, create it with an empty map `{}`.
        if fs::metadata(&atoms_path).is_err() {
            fs::write(&atoms_path, "{}")?;
        }

        // If graph.bin doesn't exist, create an empty file.
        if fs::metadata(&graph_path).is_err() {
            File::create(&graph_path)?;
        }

        // Load atoms from JSON file
        let atoms_file = File::open(&atoms_path)?;
        let reader = BufReader::new(atoms_file);
        let atoms: HashMap<Uuid, NeuroAtom> = serde_json::from_reader(reader)?;

        // Load graph from binary file
        let graph_file = File::open(&graph_path)?;
        let reader = BufReader::new(graph_file);
        // If the file is empty, deserialize_from will fail, so we provide a default.
        let graph: PetGraph<Uuid, Relationship> =
            bincode::deserialize_from(reader).unwrap_or_else(|_| PetGraph::new());

        // Build the name_to_uuid lookup cache from the loaded atoms
        let name_to_uuid = atoms
            .values()
            .filter_map(|atom| {
                if let Some(Value::String(name)) = atom.properties.get("name") {
                    Some((name.clone().to_lowercase(), atom.id))
                } else {
                    None
                }
            })
            .collect();

        // (For simplicity, we are not rebuilding all indexes on `new`.
        // A production system would do this.)
        
        Ok(StorageManager {
            data_dir: data_dir.to_string(),
            atoms: atoms.clone(),
            graph,
            name_to_uuid,
            t1_cache: atoms, // Initialize T1 cache with all atoms
            relationship_index: HashMap::new(),
            context_index: HashMap::new(),
            type_index: HashMap::new(),
            significance_index: Vec::new(),
        })
    }
    
    /// Writes a single atom to the in-memory store and schedules a flush to disk.
    pub fn write_atom(&mut self, atom: &NeuroAtom) -> io::Result<()> {
        self.atoms.insert(atom.id, atom.clone());
        if let Some(Value::String(name)) = atom.properties.get("name") {
            self.name_to_uuid.insert(name.clone().to_lowercase(), atom.id);
        }
        // For simplicity in this version, we immediately flush to disk.
        self.flush_to_disk()
    }

    /// Persists the current in-memory state (atoms and graph) to disk.
    pub fn flush_to_disk(&self) -> io::Result<()> {
        let atoms_path = format!("{}/atoms.json", self.data_dir);
        let graph_path = format!("{}/graph.bin", self.data_dir);

        // Save atoms to JSON
        let atoms_json = serde_json::to_string_pretty(&self.atoms)?;
        let mut atoms_file = File::create(&atoms_path)?;
        atoms_file.write_all(atoms_json.as_bytes())?;

        // Save graph to binary
        let graph_bin = bincode::serialize(&self.graph).unwrap();
        let mut graph_file = File::create(&graph_path)?;
        graph_file.write_all(&graph_bin)?;

        Ok(())
    }

    // --- Public read methods needed by QueryEngine ---
    pub fn read_atom(&self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
        Ok(self.atoms.get(&id).cloned())
    }
    
    // --- Public accessors for indexes (placeholders for now) ---
    pub fn get_atoms_in_context(&self, _context_id: &Uuid) -> Option<&Vec<Uuid>> { None }
    pub fn get_atoms_by_type(&self, _atom_type: &AtomType) -> Option<&Vec<Uuid>> { None }
    pub fn get_most_significant_atoms(&self, _limit: usize) -> Vec<Uuid> { vec![] }

    // --- Legacy/Unused methods, kept for compatibility ---
    pub fn get_atom_by_id_raw(&self, id: Uuid) -> io::Result<Option<NeuroAtom>> { self.read_atom(id) }
    pub fn demote_cold_atoms(&mut self, _max_age_secs: u64) -> io::Result<usize> { Ok(0) }
}

// --- UNIT TESTS ---
// This test suite is compatible with the new, simplified StorageManager structure.
#[cfg(test)]
mod tests {
    use super::*;
    use crate::nlse_core::models::AtomType;
    
    // Helper to create a clean test environment
    fn setup_test_env(test_name: &str) -> String {
        let data_dir = format!("./test_data/{}", test_name);
        let _ = fs::remove_dir_all(&data_dir);
        data_dir
    }

    #[test]
    fn test_new_storage_manager_creates_files() {
        let data_dir = setup_test_env("new_sm_creates_files");
        let _sm = StorageManager::new(&data_dir).expect("Should create a new storage manager");

        assert!(fs::metadata(format!("{}/atoms.json", &data_dir)).is_ok(), "atoms.json should be created");
        assert!(fs::metadata(format!("{}/graph.bin", &data_dir)).is_ok(), "graph.bin should be created");
    }

    #[test]
    fn test_save_and_load_single_atom() {
        let data_dir = setup_test_env("save_and_load_single");
        let mut sm = StorageManager::new(&data_dir).expect("Should create SM");

        let mut properties = HashMap::new();
        properties.insert("name".to_string(), Value::String("Socrates".to_string()));

        let atom = NeuroAtom {
            id: Uuid::new_v4(),
            label: AtomType::Concept,
            significance: 1.0, access_timestamp: 0, context_id: None, state_flags: 0,
            properties, emotional_resonance: HashMap::new(), embedded_relationships: vec![]
        };

        sm.write_atom(&atom).unwrap();
        
        // Simulate a reload by creating a new StorageManager instance from the same directory
        let sm_reloaded = StorageManager::new(&data_dir).expect("Should reload SM from existing files");
        
        let fetched_atom = sm_reloaded.atoms.get(&atom.id).expect("Atom should be loaded into the HashMap");
        
        assert_eq!(fetched_atom.id, atom.id);
        let name_value = fetched_atom.properties.get("name").unwrap();
        if let Value::String(name) = name_value {
            assert_eq!(name, "Socrates");
        } else {
            panic!("Expected name property to be a Value::String");
        }
    }
}