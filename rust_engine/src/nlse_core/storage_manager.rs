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