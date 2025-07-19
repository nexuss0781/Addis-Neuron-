use serde::{Deserialize, Serialize};
use petgraph::graph::{Graph, NodeIndex};
use petgraph::algo::has_path_connecting;
use std::collections::HashMap;

#[derive(Deserialize, Debug)]
pub struct HsmNode {
    pub name: String,
}

#[derive(Deserialize, Debug)]
pub struct HsmRelationship {
    pub subject_name: String,
    pub rel_type: String,
    pub object_name: String,
}

#[derive(Deserialize, Debug)]
pub struct HsmQuery {
    pub start_node_name: String,
    pub end_node_name: String,
    pub rel_type: String, // We only support one relationship type for traversal in this simple version
}

#[derive(Deserialize, Debug)]
pub struct HsmRequest {
    pub base_nodes: Vec<HsmNode>,
    pub base_relationships: Vec<HsmRelationship>,
    pub hypothetical_relationships: Vec<HsmRelationship>,
    pub query: HsmQuery,
}

#[derive(Serialize, Debug)]
pub struct HsmResponse {
    pub query_result: bool,
    pub reason: String,
}


/// Core HSM logic. Builds an in-memory graph from a base state and
/// hypotheticals, then runs a query on it.
pub fn reason_hypothetically(request: &HsmRequest) -> HsmResponse {
    let mut graph = Graph::<String, String>::new();
    let mut node_map: HashMap<String, NodeIndex> = HashMap::new();

    // 1. Populate the graph with the "base reality" nodes
    for node in &request.base_nodes {
        let name = node.name.clone();
        if !node_map.contains_key(&name) {
            let index = graph.add_node(name.clone());
            node_map.insert(name, index);
        }
    }
    
    // Combine base and hypothetical relationships for the temporary model
    let all_relationships = request.base_relationships.iter().chain(request.hypothetical_relationships.iter());

    // 2. Add all relationships (base + hypothetical) to the graph
    for rel in all_relationships {
        // Ensure all nodes exist in our map before adding edges
        for name in [&rel.subject_name, &rel.object_name] {
            if !node_map.contains_key(name) {
                let index = graph.add_node(name.clone());
                node_map.insert(name.clone(), index);
            }
        }
        
        let subject_index = node_map[&rel.subject_name];
        let object_index = node_map[&rel.object_name];

        // For now, we only care about the relationship type for the query itself,
        // but we add it as the edge weight.
        graph.add_edge(subject_index, object_index, rel.rel_type.clone());
    }

    // 3. Execute the query on the combined, in-memory graph
    if let (Some(&start_node), Some(&end_node)) = (node_map.get(&request.query.start_node_name), node_map.get(&request.query.end_node_name)) {
        // Use a petgraph algorithm to see if a path exists.
        // A more complex query engine would be built here in the future.
        let path_exists = has_path_connecting(&graph, start_node, end_node, None);
        
        HsmResponse {
            query_result: path_exists,
            reason: format!(
                "Hypothetical model evaluated. Path existence from '{}' to '{}': {}.",
                request.query.start_node_name, request.query.end_node_name, path_exists
            )
        }
    } else {
        HsmResponse {
            query_result: false,
            reason: "Query failed: one or more nodes in the query do not exist in the model.".to_string(),
        }
    }
}