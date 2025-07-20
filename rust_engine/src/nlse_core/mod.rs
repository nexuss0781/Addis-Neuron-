// Declare the sub-modules within nlse_core
pub mod models;
pub mod storage_manager; // We will create this file next

// Re-export the most important public types for easier access
// This means other parts of our app can write `use crate::nlse_core::NeuroAtom`
// instead of the longer `use crate::nlse_core::models::NeuroAtom`
pub use models::NeuroAtom;
