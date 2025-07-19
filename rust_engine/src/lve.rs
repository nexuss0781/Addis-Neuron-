use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Deserialize, Debug)]
pub struct Relationship {
    pub rel_type: String,
    pub target_name: String,
}

#[derive(Deserialize, Debug)]
pub struct LveRequest {
    pub subject_name: String,
    pub existing_relationships: Vec<Relationship>,
    pub proposed_relationship: Relationship,
}

#[derive(Serialize, Debug)]
pub struct LveResponse {
    pub is_valid: bool,
    pub reason: String,
}

/// A map of contradictory relationship pairs.
/// The key is a relationship type, and the value is its direct opposite.
fn get_contradiction_map() -> HashMap<String, String> {
    let mut map = HashMap::new();
    map.insert("IS_A".to_string(), "IS_NOT_A".to_string());
    map.insert("IS_NOT_A".to_string(), "IS_A".to_string());
    map.insert("HAS_PROPERTY".to_string(), "LACKS_PROPERTY".to_string());
    map.insert("LACKS_PROPERTY".to_string(), "HAS_PROPERTY".to_string());
    // This map can be expanded with more complex logical opposites.
    map
}


/// The core logic of the LVE. Checks a proposed fact against existing facts
/// for direct contradictions.
pub fn validate_contradiction(request: &LveRequest) -> LveResponse {
    let contradiction_map = get_contradiction_map();
    let proposed_rel_type = &request.proposed_relationship.rel_type;

    // Find what the opposite of the proposed relationship is, if one exists.
    if let Some(opposite_rel_type) = contradiction_map.get(proposed_rel_type) {
        // Now, check if any of the existing relationships match this opposite.
        for existing_rel in &request.existing_relationships {
            if &existing_rel.rel_type == opposite_rel_type &&
               existing_rel.target_name == request.proposed_relationship.target_name {
                
                // A direct contradiction was found!
                return LveResponse {
                    is_valid: false,
                    reason: format!(
                        "Contradiction detected. Knowledge base contains '({})-[{}]->({})', which contradicts proposed '({})-[{}]->({})'.",
                        request.subject_name,
                        existing_rel.rel_type,
                        existing_rel.target_name,
                        request.subject_name,
                        proposed_rel_type,
                        request.proposed_relationship.target_name
                    ),
                };
            }
        }
    }
    
    // No contradictions found.
    LveResponse {
        is_valid: true,
        reason: "No direct contradictions found.".to_string(),
    }
}