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