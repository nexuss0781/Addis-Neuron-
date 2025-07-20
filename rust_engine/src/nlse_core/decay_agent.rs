use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use super::storage_manager::StorageManager;

/// An autonomous agent that runs in the background to manage the data lifecycle.
pub struct DecayAgent;

impl DecayAgent {
    /// Starts the decay agent in a new thread.
    pub fn start(storage_manager: Arc<Mutex<StorageManager>>) {
        println!("NLSE: Starting DecayAgent background process...");

        thread::spawn(move || {
            loop {
                thread::sleep(Duration::from_secs(30));
                
                println!("DECAY AGENT: Running demotion cycle...");
                let mut manager = storage_manager.lock().unwrap();
                
                match manager.demote_cold_atoms(60) {
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