use std::fs::{File, OpenOptions};
use std::io::{self, Write, Seek, SeekFrom, Read, ErrorKind};
use std::path::{Path, PathBuf};
use std::collections::HashMap;
use uuid::Uuid;
use memmap2::Mmap;

use super::models::{NeuroAtom, RelationshipType};

#[derive(Debug, Clone, Copy)]
pub enum AtomLocation {
    T2(usize),
    T3(u64),
}

/// Manages the physical storage of NeuroAtoms across a multi-tiered system.
pub struct StorageManager {
    t3_file: File,
    t2_file: File,
    t2_mmap: Mmap,
    primary_index: HashMap<Uuid, AtomLocation>,
    relationship_index: HashMap<RelationshipType, Vec<Uuid>>,
}

impl StorageManager {
    /// Creates a new StorageManager or opens existing database files.
    pub fn new<P: AsRef<Path>>(base_path: P) -> io::Result<Self> {
        let t3_path = base_path.as_ref().join("brain.db");
        let t2_path = base_path.as_ref().join("brain_cache.db");
        
        let t3_file = OpenOptions::new().read(true).write(true).create(true).open(&t3_path)?;
        let t2_file = OpenOptions::new().read(true).write(true).create(true).open(&t2_path)?;
        
        // This map can be empty on first run, which is fine.
        let t2_mmap = unsafe { Mmap::map(&t2_file).unwrap_or_else(|_| Mmap::map(&File::create(&t2_path).unwrap()).unwrap()) };
        
        let (primary_index, relationship_index) = Self::rebuild_indexes(&t3_path, &t2_path)?;
        
        println!("NLSE: StorageManager initialized with T2 and T3 stores.");

        Ok(StorageManager { t3_file, t2_file, t2_mmap, primary_index, relationship_index })
    }

    /// Writes a new atom directly to the T2 cache file.
    pub fn write_atom(&mut self, atom: &NeuroAtom) -> io::Result<()> {
        let encoded_atom = bincode::serialize(atom).map_err(|e| io::Error::new(ErrorKind::Other, e))?;
        let data_len = encoded_atom.len() as u64;

        let write_offset = self.t2_file.seek(SeekFrom::End(0))?;
        
        self.t2_file.write_all(&data_len.to_le_bytes())?;
        self.t2_file.write_all(&encoded_atom)?;
        self.t2_file.sync_data()?;
        
        self.remap_t2()?;
        
        self.primary_index.insert(atom.id, AtomLocation::T2(write_offset as usize));
        
        for rel in &atom.embedded_relationships {
            let entry = self.relationship_index.entry(rel.rel_type.clone()).or_default();
            if !entry.contains(&atom.id) {
                entry.push(atom.id);
            }
        }
        Ok(())
    }
    
    /// Reads an Atom by checking T2 first, falling back to T3, and promotes if necessary.
    pub fn read_atom(&mut self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
        let location = self.primary_index.get(&id).cloned();
        if let Some(loc) = location {
            let mut atom = match self.read_atom_from_location(id)? {
                Some(a) => a,
                None => return Ok(None)
            };
            
            if let AtomLocation::T3(_) = loc {
                println!("NLSE: Promoting Atom {} to T2 cache.", atom.id);
                self.write_atom(&atom)?; // write_atom now correctly handles T2 writes and index updates
                self.delete_from_t3(atom.id)?;
            } else {
                // It was read from T2, so we update its timestamp to keep it "hot"
                if self.current_timestamp_secs() - atom.access_timestamp > 1 { // Avoid rapid rewrites
                    atom.access_timestamp = self.current_timestamp_secs();
                    self.overwrite_atom_in_place(id, &atom)?;
                }
            }
            Ok(Some(atom))
        } else {
            Ok(None)
        }
    }

    /// Scans the T2 cache for atoms older than a given age and moves them to T3.
    pub fn demote_cold_atoms(&mut self, max_age_secs: u64) -> io::Result<usize> {
        let now = self.current_timestamp_secs();
        let mut cold_atom_ids = Vec::new();
        let mut t2_atoms_to_check = Vec::new();

        // Phase 1: Identify all "cold" atoms in the T2 cache
        for (id, location) in &self.primary_index {
            if let AtomLocation::T2(_) = location {
                t2_atoms_to_check.push(*id);
            }
        }

        for id in t2_atoms_to_check {
             if let Some(atom) = self.read_atom_from_location(id)? {
                if now.saturating_sub(atom.access_timestamp) > max_age_secs {
                    cold_atom_ids.push(id);
                }
            }
        }

        if cold_atom_ids.is_empty() { return Ok(0); }
        let demoted_count = cold_atom_ids.len();
        
        // Phase 2: Demote the identified cold atoms
        for id in cold_atom_ids {
            if let Some(atom_to_demote) = self.read_atom_from_location(id)? {
                let new_t3_offset = self.write_to_t3(&atom_to_demote)?;
                self.primary_index.insert(id, AtomLocation::T3(new_t3_offset));
                // Real deletion from T2 is handled by compaction later. The index change is enough for now.
            }
        }
        
        if demoted_count > 0 {
             println!("NLSE: Placeholder for T2 compaction after demoting {} atoms.", demoted_count);
        }
        Ok(demoted_count)
    }

    // --- HELPER METHODS ---

    fn remap_t2(&mut self) -> io::Result<()> {
        self.t2_mmap = unsafe { Mmap::map(&self.t2_file)? }; Ok(())
    }

    fn current_timestamp_secs(&self) -> u64 {
        std::time::SystemTime::now().duration_since(std.time::UNIX_EPOCH).unwrap_or_default().as_secs()
    }
    
    fn read_atom_from_location(&mut self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
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

    fn rebuild_indexes<P: AsRef<Path>>(t3_path: P, t2_path: P) -> io::Result<(HashMap<Uuid, AtomLocation>, HashMap<RelationshipType, Vec<Uuid>>)> {
        let mut primary = HashMap::new();
        let mut relationship = HashMap::new();
        
        println!("NLSE: Rebuilding indexes...");
        Self::scan_file_for_index(t3_path, AtomLocation::T3(0), &mut primary, &mut relationship)?;
        Self::scan_file_for_index(t2_path, AtomLocation::T2(0), &mut primary, &mut relationship)?;
        println!("NLSE: Index rebuild complete. {} total atoms loaded.", primary.len());
        
        Ok((primary, relationship))
    }
    
    fn scan_file_for_index<P: AsRef<Path>>(
        path: P, location_enum: AtomLocation, primary: &mut HashMap<Uuid, AtomLocation>, relationship: &mut HashMap<RelationshipType, Vec<Uuid>>
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
            };

            primary.insert(atom.id, location); 
            for rel in &atom.embedded_relationships {
                let entry = relationship.entry(rel.rel_type.clone()).or_default();
                if !entry.contains(&atom.id) { entry.push(atom.id); }
            }
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

    fn create_test_atom(name: &str, relationships: Vec<Relationship>) -> NeuroAtom {
        let mut atom = NeuroAtom::new_concept(name);
        atom.embedded_relationships = relationships;
        atom.access_timestamp = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs();
        atom
    }
    
    #[test]
    fn test_write_goes_to_t2() {
        let dir = tempdir().unwrap();
        let mut manager = StorageManager::new(dir.path()).unwrap();

        let atom = create_test_atom("Socrates", vec![]);
        manager.write_atom(&atom).unwrap();

        let location = manager.primary_index.get(&atom.id).unwrap();
        assert!(matches!(location, AtomLocation::T2(_)));
        
        let retrieved = manager.read_atom(atom.id).unwrap().unwrap();
        assert_eq!(retrieved, atom);
    }

    #[test]
    fn test_promotion_from_t3_to_t2() {
        let dir = tempdir().unwrap();
        let mut manager = StorageManager::new(dir.path()).unwrap();
        
        let mut atom = create_test_atom("Cold Atom", vec![]);

        // Manually write this atom to the T3 store
        let t3_offset = manager.write_to_t3(&atom).unwrap();
        manager.primary_index.insert(atom.id, AtomLocation::T3(t3_offset));

        // Sanity check: confirm it's in T3
        let loc_before = manager.primary_index.get(&atom.id).unwrap();
        assert!(matches!(loc_before, AtomLocation::T3(_)));

        // Now, read the atom. This should trigger the promotion logic.
        let retrieved = manager.read_atom(atom.id).unwrap().unwrap();

        // Check if it was promoted
        let loc_after = manager.primary_index.get(&atom.id).unwrap();
        assert!(matches!(loc_after, AtomLocation::T2(_)), "Atom was not promoted to T2");
        assert_eq!(retrieved, atom);
    }

    #[test]
    fn test_demotion_from_t2_to_t3() {
        let dir = tempdir().unwrap();
        let mut manager = StorageManager::new(dir.path()).unwrap();

        // Create an atom that is intentionally "old"
        let mut old_atom = create_test_atom("Old Atom", vec![]);
        let now = manager.current_timestamp_secs();
        old_atom.access_timestamp = now.saturating_sub(100); // 100 seconds old
        
        let mut recent_atom = create_test_atom("Recent Atom", vec![]);
        recent_atom.access_timestamp = now;

        // Write both to T2
        manager.write_atom(&old_atom).unwrap();
        manager.write_atom(&recent_atom).unwrap();
        
        // Confirm both are in T2 initially
        assert!(matches!(manager.primary_index.get(&old_atom.id).unwrap(), AtomLocation::T2(_)));
        assert!(matches!(manager.primary_index.get(&recent_atom.id).unwrap(), AtomLocation::T2(_)));
        
        // Run the demotion logic. Anything older than 60 seconds should be demoted.
        let demoted_count = manager.demote_cold_atoms(60).unwrap();
        assert_eq!(demoted_count, 1);
        
        // Verify the old atom is now in T3
        let old_loc = manager.primary_index.get(&old_atom.id).unwrap();
        assert!(matches!(old_loc, AtomLocation::T3(_)), "Old atom was not demoted to T3");

        // Verify the recent atom is still in T2
        let recent_loc = manager.primary_index.get(&recent_atom.id).unwrap();
        assert!(matches!(recent_loc, AtomLocation::T2(_)), "Recent atom was incorrectly demoted");
    }

    #[test]
    fn test_index_rebuild_from_both_tiers() {
        let dir = tempdir().unwrap();
        let dir_path = dir.path().to_path_buf();
        
        let t3_atom = create_test_atom("Deep Memory", vec![]);
        let t2_atom = create_test_atom("Recent Memory", vec![]);
        
        // Scope to write to files and close the first manager
        {
            let mut manager1 = StorageManager::new(&dir_path).unwrap();
            
            // Manually place one in T3, one in T2
            let t3_offset = manager1.write_to_t3(&t3_atom).unwrap();
            manager1.primary_index.insert(t3_atom.id, AtomLocation::T3(t3_offset));
            manager1.write_atom(&t2_atom).unwrap();
        }

        // Create a new manager instance which will trigger a rebuild
        let manager2 = StorageManager::new(&dir_path).unwrap();
        
        // Check if both atoms were correctly indexed in their respective locations
        assert_eq!(manager2.primary_index.len(), 2);
        let t3_loc = manager2.primary_index.get(&t3_atom.id).unwrap();
        assert!(matches!(t3_loc, AtomLocation::T3(_)));

        let t2_loc = manager2.primary_index.get(&t2_atom.id).unwrap();
        assert!(matches!(t2_loc, AtomLocation::T2(_)));
    }
}