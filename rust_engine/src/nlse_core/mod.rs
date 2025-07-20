// Declare the sub-modules within nlse_core
pub mod models;
pub mod storage_manager;
pub mod decay_agent; // <-- ADD THIS LINE

// Re-export the most important public types
pub use models::NeuroAtom;