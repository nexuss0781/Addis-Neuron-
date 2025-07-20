use std::fs::{File, OpenOptions};
use std::io::{self, Write, Seek, SeekFrom, Read};
use std::path::Path;
use std::collections::HashMap;
use uuid::Uuid;

use super::models::{NeuroAtom, RelationshipType};

/// A tuple containing both indexes for easier management.
struct Indexes {
    primary: HashMap<Uuid, u64>,
    relationship: HashMap<RelationshipType, Vec<Uuid>>,
}

/// Manages the physical storage of NeuroAtoms in an append-only file.
pub struct StorageManager {
    file: File,
    primary_index: HashMap<Uuid, u64>,
    relationship_index: HashMap<RelationshipType, Vec<Uuid>>,
}

impl StorageManager {
    /// Creates a new StorageManager or opens an existing database file.
    /// On startup, it rebuilds the in-memory indexes from the file.
    pub fn new<P: AsRef<Path>>(path: P) -> io::Result<Self> {
        let mut file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .open(path)?;

        let indexes = Self::rebuild_indexes(&mut file)?;

        Ok(StorageManager {
            file,
            primary_index: indexes.primary,
            relationship_index: indexes.relationship,
        })
    }

    /// Serializes a NeuroAtom and writes it to the end of the database file.
    /// Also updates the in-memory indexes.
    pub fn write_atom(&mut self, atom: &NeuroAtom) -> io::Result<()> {
        let encoded_atom: Vec<u8> = bincode::serialize(atom)
            .map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        
        let data_len = encoded_atom.len() as u64;
        let write_offset = self.file.seek(SeekFrom::End(0))?;

        self.file.write_all(&data_len.to_le_bytes())?;
        self.file.write_all(&encoded_atom)?;
        self.file.sync_data()?;

        // After a successful write, update the in-memory indexes.
        self.primary_index.insert(atom.id, write_offset);
        for rel in &atom.embedded_relationships {
            self.relationship_index
                .entry(rel.rel_type.clone())
                .or_insert_with(Vec::new)
                .push(atom.id);
        }

        Ok(())
    }
    
    /// Reads a NeuroAtom from the file using its ID.
    pub fn read_atom(&mut self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
        if let Some(&offset) = self.primary_index.get(&id) {
            self.file.seek(SeekFrom::Start(offset))?;

            let mut len_bytes = [0u8; 8];
            self.file.read_exact(&mut len_bytes)?;
            let data_len = u64::from_le_bytes(len_bytes);

            let mut buffer = vec![0u8; data_len as usize];
            self.file.read_exact(&mut buffer)?;

            let atom: NeuroAtom = bincode::deserialize(&buffer)
                .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
            
            Ok(Some(atom))
        } else {
            Ok(None)
        }
    }

    /// Scans the entire database file to rebuild all in-memory indexes.
    fn rebuild_indexes(file: &mut File) -> io::Result<Indexes> {
        let mut primary_index = HashMap::new();
        let mut relationship_index = HashMap::new();
        
        let mut current_pos = file.seek(SeekFrom::Start(0))?;
        let file_len = file.metadata()?.len();
        
        println!("NLSE: Rebuilding indexes from database file...");

        while current_pos < file_len {
            let atom_offset = current_pos;

            let mut len_bytes = [0u8; 8];
            if file.read_exact(&mut len_bytes).is_err() { break; }
            let data_len = u64::from_le_bytes(len_bytes);
            
            if current_pos + 8 + data_len > file_len { break; }
            
            let mut buffer = vec![0u8; data_len as usize];
            file.read_exact(&mut buffer)?;
            let atom: NeuroAtom = bincode::deserialize(&buffer)
                .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
            
            // Populate primary index
            primary_index.insert(atom.id, atom_offset);
            
            // Populate relationship index
            for rel in &atom.embedded_relationships {
                relationship_index
                    .entry(rel.rel_type.clone())
                    .or_insert_with(Vec::new)
                    .push(atom.id);
            }
            
            current_pos += 8 + data_len;
        }
        
        println!("NLSE: Index rebuild complete. {} atoms loaded.", primary_index.len());
        Ok(Indexes {
            primary: primary_index,
            relationship: relationship_index,
        })
    }

    // A helper method for testing
    #[cfg(test)]
    pub fn get_atoms_with_relationship_type(&self, rel_type: &RelationshipType) -> Option<&Vec<Uuid>> {
        self.relationship_index.get(rel_type)
    }
}

// --- TESTS ---
#[cfg(test)]
mod tests {
    use super::*;
    use crate::nlse_core::models::{NeuroAtom, Relationship, Value, AtomType, RelationshipType};
    use tempfile::NamedTempFile; // Crate for creating temporary files for testing

    // Helper to create a dummy atom for testing
    fn create_test_atom(name: &str, relationships: Vec<Relationship>) -> NeuroAtom {
        let mut atom = NeuroAtom::new_concept(name);
        atom.embedded_relationships = relationships;
        atom
    }

    #[test]
    fn test_write_and_read_single_atom() {
        // Create a temporary file that gets deleted automatically
        let temp_file = NamedTempFile::new().unwrap();
        let mut manager = StorageManager::new(temp_file.path()).unwrap();

        let original_atom = create_test_atom("Socrates", vec![]);
        
        // Write the atom
        manager.write_atom(&original_atom).unwrap();

        // Read it back
        let retrieved_atom = manager.read_atom(original_atom.id).unwrap().unwrap();

        // Assert that what we read is identical to what we wrote
        assert_eq!(original_atom, retrieved_atom);
    }

    #[test]
    fn test_index_rebuild() {
        let temp_file = NamedTempFile::new().unwrap();
        let temp_path = temp_file.path().to_path_buf();

        let atom1 = create_test_atom("Socrates", vec![]);
        let atom2 = create_test_atom("Plato", vec![]);

        // Scope to ensure the first manager is closed and its file is saved
        {
            let mut manager1 = StorageManager::new(&temp_path).unwrap();
            manager1.write_atom(&atom1).unwrap();
            manager1.write_atom(&atom2).unwrap();
        } // manager1 is dropped here, file handle is closed

        // Create a new manager instance from the same file
        let mut manager2 = StorageManager::new(&temp_path).unwrap();

        // The index should have been rebuilt. Let's try to read using it.
        let retrieved_atom1 = manager2.read_atom(atom1.id).unwrap().unwrap();
        let retrieved_atom2 = manager2.read_atom(atom2.id).unwrap().unwrap();
        
        assert_eq!(atom1, retrieved_atom1);
        assert_eq!(atom2, retrieved_atom2);
        assert_eq!(manager2.primary_index.len(), 2);
    }
    
    #[test]
    fn test_relationship_index() {
        let temp_file = NamedTempFile::new().unwrap();
        let mut manager = StorageManager::new(temp_file.path()).unwrap();

        let plato = create_test_atom("Plato", vec![]);
        let socrates_rels = vec![
            Relationship {
                target_id: plato.id,
                rel_type: RelationshipType::IsA,
                strength: 1.0,
                access_timestamp: 123,
            }
        ];
        let socrates = create_test_atom("Socrates", socrates_rels);
        
        let philosophy = create_test_atom("Philosophy", vec![]);
        let logic_rels = vec![
             Relationship {
                target_id: philosophy.id,
                rel_type: RelationshipType::PartOf,
                strength: 1.0,
                access_timestamp: 123,
            }
        ];
        let logic = create_test_atom("Logic", logic_rels);

        // Write all atoms to the store
        manager.write_atom(&plato).unwrap();
        manager.write_atom(&socrates).unwrap();
        manager.write_atom(&philosophy).unwrap();
        manager.write_atom(&logic).unwrap();

        // Check the relationship index
        let is_a_sources = manager.get_atoms_with_relationship_type(&RelationshipType::IsA).unwrap();
        assert_eq!(is_a_sources.len(), 1);
        assert!(is_a_sources.contains(&socrates.id));
        
        let part_of_sources = manager.get_atoms_with_relationship_type(&RelationshipType::PartOf).unwrap();
        assert_eq!(part_of_sources.len(), 1);
        assert!(part_of_sources.contains(&logic.id));
    }
}
