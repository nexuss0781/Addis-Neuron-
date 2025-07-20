use std::fs::{File, OpenOptions};
use std::io::{self, Write, Seek, SeekFrom, Read};
use std::path::{Path, PathBuf};
use std::collections::HashMap;
use uuid::Uuid;
use memmap2::{Mmap, MmapMut}; // Import MmapMut for writing

use super::models::{NeuroAtom, RelationshipType};

#[derive(Debug, Clone, Copy)] // Add derive for easier debugging and copying
enum AtomLocation {
    T2(usize), // Byte offset within the T2 memory map
    T3(u64),  // Byte offset within the T3 file
}

/// Manages the physical storage of NeuroAtoms across a multi-tiered system.
pub struct StorageManager {
    // Tier 3 Deep Store
    t3_file: File,
    
    // Tier 2 Recent Memory Core
    t2_file: File,
    t2_mmap: Mmap, // Read-only map
    
    // Combined Indexes
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

        let t2_mmap = unsafe { Mmap::map(&t2_file)? };
        
        let (primary_index, relationship_index) = Self::rebuild_indexes(&t3_path, &t2_path)?;
        
        println!("NLSE: StorageManager initialized with T2 and T3 stores.");

        Ok(StorageManager {
            t3_file,
            t2_file,
            t2_mmap,
            primary_index,
            relationship_index,
        })
    }

    /// Writes a new atom directly to the T2 cache file.
    pub fn write_atom(&mut self, atom: &NeuroAtom) -> io::Result<()> {
        let encoded_atom: Vec<u8> = bincode::serialize(atom).map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        let data_len = encoded_atom.len() as u64;

        let mut file = &self.t2_file;
        let write_offset = file.seek(SeekFrom::End(0))?;
        
        file.write_all(&data_len.to_le_bytes())?;
        file.write_all(&encoded_atom)?;
        file.sync_data()?;
        
        self.remap_t2()?; // Remap the file after writing to make it visible
        
        self.primary_index.insert(atom.id, AtomLocation::T2(write_offset as usize));
        // We will update the relationship index later to avoid duplicates
        
        Ok(())
    }
    
    /// Reads an Atom by checking T2 first, then falling back to T3.
    /// If an atom is read from T3, it is PROMOTED to T2.
    pub fn read_atom(&mut self, id: Uuid) -> io::Result<Option<NeuroAtom>> {
        let location = self.primary_index.get(&id).cloned(); // Clone to avoid borrow checker issues
        if let Some(loc) = location {
            match loc {
                AtomLocation::T2(offset) => {
                    println!("NLSE: Reading Atom {} from T2 cache.", id);
                    let offset = offset as usize;
                    let mut len_bytes = [0u8; 8];
                    len_bytes.copy_from_slice(&self.t2_mmap[offset..offset+8]);
                    let data_len = u64::from_le_bytes(len_bytes) as usize;
                    
                    let data = &self.t2_mmap[offset + 8 .. offset + 8 + data_len];
                    let atom: NeuroAtom = bincode::deserialize(data)
                        .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
                    
                    Ok(Some(atom))
                }
                AtomLocation::T3(offset) => {
                    println!("NLSE: T3 Read miss. Reading Atom {} from T3 deep store.", id);
                    self.t3_file.seek(SeekFrom::Start(offset))?;

                    let mut len_bytes = [0u8; 8];
                    self.t3_file.read_exact(&mut len_bytes)?;
                    let data_len = u64::from_le_bytes(len_bytes) as usize;

                    let mut buffer = vec![0u8; data_len];
                    self.t3_file.read_exact(&mut buffer)?;
                    
                    let atom: NeuroAtom = bincode::deserialize(&buffer)
                        .map_err(|e| io::Error::new(io.ErrorKind::InvalidData, e))?;
                        
                    // --- PROMOTION LOGIC STARTS HERE ---
                    println!("NLSE: Promoting Atom {} to T2 cache.", atom.id);
                    // Write the atom to the T2 cache. This also remaps T2 and updates the primary index.
                    self.write_atom(&atom)?;

                    // Once promoted, remove it from the T3 store.
                    // This is a placeholder for now until we have a compaction strategy.
                    self.delete_from_t3(atom.id)?;
                    // --- PROMOTION LOGIC ENDS HERE ---
                    
                    Ok(Some(atom))
                }
            }
        } else {
            Ok(None)
        }
    }
    
    fn overwrite_atom_in_place(&mut self, _id: Uuid, _atom: &NeuroAtom) -> io::Result<()> {
        // This is another complex operation in an append-only log, as it can lead
        // to fragmentation or requires a re-write. For now, it is a placeholder.
        // True overwrites are better handled by a different storage model (not append-only),
        // which we might consider for T1/T2 in the future.
        Ok(())
    }
    
    pub fn write_to_t3(&mut self, atom: &NeuroAtom) -> io::Result<u64> {
        // This is a new helper for demotion logic
        let encoded_atom: Vec<u8> = bincode::serialize(atom).map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        let data_len = encoded_atom.len() as u64;

        let write_offset = self.t3_file.seek(SeekFrom::End(0))?;
        self.t3_file.write_all(&data_len.to_le_bytes())?;
        self.t3_file.write_all(&encoded_atom)?;
        self.t3_file.sync_data()?;
        Ok(write_offset)
    }

    /// Scans the T2 cache for atoms older than a given age and moves them to T3.
    pub fn demote_cold_atoms(&mut self, max_age_secs: u64) -> io::Result<usize> {
        let now = self.current_timestamp_secs();
        let mut cold_atom_ids = Vec::new();

        // Phase 1: Identify all "cold" atoms in the T2 cache
        for (id, location) in &self.primary_index {
            if let AtomLocation::T2(_) = location {
                // We have to read the atom to check its timestamp. This is inefficient
                // and highlights the need for a separate timestamp index in the future.
                if let Some(atom) = self.read_atom_from_location(*id)? {
                    if now.saturating_sub(atom.access_timestamp) > max_age_secs {
                        cold_atom_ids.push(*id);
                    }
                }
            }
        }

        if cold_atom_ids.is_empty() {
            return Ok(0); // Nothing to do
        }

        let demoted_count = cold_atom_ids.len();

        // Phase 2: Demote the identified cold atoms
        for id in cold_atom_ids {
            if let Some(atom_to_demote) = self.read_atom_from_location(id)? {
                // 1. Write the atom to the T3 deep store
                let new_t3_offset = self.write_to_t3(&atom_to_demote)?;

                // 2. Update the primary index to point to the new T3 location
                self.primary_index.insert(id, AtomLocation::T3(new_t3_offset));

                // 3. To-Do: Remove the atom from the T2 file.
                // This is a complex step in an append-only file, requiring compaction.
                // For now, the old data in T2 becomes "garbage" to be cleaned later.
                // The index change ensures it is no longer read from T2.
            }
        }
        
        // After demoting, we should run a T2 compaction process. Placeholder for now.
        println!("NLSE: Placeholder for T2 compaction after demoting {} atoms.", demoted_count);
        
        Ok(demoted_count)
    }    
    
    fn delete_from_t3(&mut self, _id: Uuid) -> io::Result<()> {
        // This is a complex operation. An append-only log requires compaction
        // to truly delete data. For now, this is a placeholder.
        // We will implement this with a compaction daemon later.
        println!("NLSE: Placeholder for deleting Atom {} from T3.", _id);
        Ok(())
    }

    /// Rebuilds all indexes by scanning both T3 and T2 files.
    fn rebuild_indexes<P: AsRef<Path>>(t3_path: P, t2_path: P) -> io::Result<(HashMap<Uuid, AtomLocation>, HashMap<RelationshipType, Vec<Uuid>>)> {
        let mut primary = HashMap::new();
        let mut relationship = HashMap::new();
        
        println!("NLSE: Rebuilding indexes...");
        Self::scan_file_for_index(t3_path, AtomLocation::T3(0), &mut primary, &mut relationship)?;
        Self::scan_file_for_index(t2_path, AtomLocation::T2(0), &mut primary, &mut relationship)?;
        println!("NLSE: Index rebuild complete. {} total atoms loaded.", primary.len());
        
        Ok((primary, relationship))
    }
    
    /// Helper function to scan a single database file and populate index maps.
    fn scan_file_for_index<P: AsRef<Path>>(
        path: P,
        location_enum: AtomLocation,
        primary: &mut HashMap<Uuid, AtomLocation>,
        relationship: &mut HashMap<RelationshipType, Vec<Uuid>>,
    ) -> io::Result<()> {
        let mut file = File::open(path)?;
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer)?;

        let mut cursor = 0;
        while cursor < buffer.len() {
            let atom_offset = cursor;

            // Read length
            let mut len_bytes = [0u8; 8];
            len_bytes.copy_from_slice(&buffer[cursor..cursor+8]);
            let data_len = u64::from_le_bytes(len_bytes) as usize;
            cursor += 8;
            
            // Deserialize and update indexes
            let data_slice = &buffer[cursor..cursor + data_len];
            let atom: NeuroAtom = bincode::deserialize(data_slice)
                .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
            
            let location = match location_enum {
                AtomLocation::T2(_) => AtomLocation::T2(atom_offset),
                AtomLocation::T3(_) => AtomLocation::T3(atom_offset as u64),
            };

            // T2 data overrides T3 data
            primary.insert(atom.id, location); 
            for rel in &atom.embedded_relationships {
                 relationship
                    .entry(rel.rel_type.clone())
                    .or_default()
                    .push(atom.id);
            }
            
            cursor += data_len;
        }
        Ok(())
    }

    /// Helper to remap the T2 file after it has been written to.
    fn remap_t2(&mut self) -> io::Result<()> {
        self.t2_mmap = unsafe { Mmap::map(&self.t2_file)? };
        Ok(())
    }
}

// --- TESTS ---
#[cfg(test)]
mod tests {
    use super::*;
    use crate::nlse_core::models::{NeuroAtom, Relationship, Value, AtomType, RelationshipType};
    use tempfile::tempdir; // Use tempdir for directory-based tests
    use std::thread;
    use std::time::Duration;

    // Helper to create a dummy atom for testing
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

