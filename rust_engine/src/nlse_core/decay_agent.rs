use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use super::storage_manager::StorageManager;

/// An autonomous agent that runs in the background to manage the data lifecycle.
pub struct DecayAgent {
    // We will expand this with more functionality later
}

impl DecayAgent {
    /// Starts the decay agent in a new thread.
    /// It periodically scans the T2 cache and demotes old atoms.
    pub fn start(storage_manager: Arc<Mutex<StorageManager>>) {
        println!("NLSE: Starting DecayAgent background process...");

        thread::spawn(move || {
            loop {
                // Wait for a set interval before running the check.
                // Using a short interval for testing.
                thread::sleep(Duration::from_secs(30));
                
                println!("DECAY AGENT: Running demotion cycle...");

                // To perform the check, we need to lock the StorageManager
                // so we don't interfere with any active read/write operations.
                let mut manager = storage_manager.lock().unwrap();

                // The actual logic for demotion will be added to the
                // StorageManager in the next step. For now, we just call a
                // placeholder method.
                match manager.demote_cold_atoms(60) { // Demote atoms older than 60s
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