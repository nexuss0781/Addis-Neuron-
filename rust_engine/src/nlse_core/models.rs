use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

// Enums provide strict typing for our core concepts.
#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Hash, Clone)]
pub enum AtomType {
    Concept,
    Word,
    MetaConcept,
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Hash, Clone)]
pub enum RelationshipType {
    IsA,
    HasProperty,
    PartOf,
    Causes,
    Action,
    Location,
    // --- Opposites for LVE ---
    IsNotA,
    LacksProperty,
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
pub enum Value {
    String(String),
    Int(i64),
    Float(f64),
    Bool(bool),
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
pub struct Relationship {
    pub target_id: Uuid,
    pub rel_type: RelationshipType,
    pub strength: f32,
    pub access_timestamp: u64,
}

#[derive(Serialize, Deserialize, Debug, PartialEq, Clone)]
pub struct NeuroAtom {
    pub id: Uuid,
    pub label: AtomType,
    pub significance: f32,
    pub access_timestamp: u64,
    pub context_id: Option<Uuid>, // E.g., ID of a Paragraph or Book atom
    pub state_flags: u8, // A bitfield for multiple boolean states
    pub properties: HashMap<String, Value>,
    pub emotional_resonance: HashMap<String, f32>,
    pub embedded_relationships: Vec<Relationship>,
}

impl NeuroAtom {
    /// Helper function to create a simple new Concept atom.
    pub fn new_concept(name: &str) -> Self {
        let mut properties = HashMap::new();
        // --- THIS LINE IS CORRECTED ---
        properties.insert("name".to_string(), Value::String(name.to_string()));

        NeuroAtom {
            id: Uuid::now_v7(),
            label: AtomType::Concept,
            significance: 1.0,
            access_timestamp: 0, // Should be set by storage manager
            context_id: None,
            state_flags: 0,
            properties,
            emotional_resonance: HashMap::new(),
            embedded_relationships: Vec::new(),
        }
    }
}
