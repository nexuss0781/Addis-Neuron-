// Declare the sub-modules within nlse_core
pub mod models;
pub mod storage_manager; // Publicly declare this module
pub mod decay_agent;    // Publicly declare this module
pub mod query_engine;   // Publicly declare this module

// Re-export public types for easier access
pub use models::NeuroAtom;
pub use query_engine::{QueryEngine, ExecutionPlan};