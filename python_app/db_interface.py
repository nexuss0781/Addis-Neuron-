import os
import redis
from neo4j import GraphDatabase, Result
from neo4j.exceptions import ServiceUnavailable
import logging
import json
import requests
from typing import Optional # <-- ADD THIS IMPORT
import numpy as np # <-- ADD THIS LINE
# The other imports...
from models import StructuredTriple
from models import DiseaseDefinition
# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages connections and interactions with Neo4j and Redis databases.
    """
    def __init__(self):
        # Neo4j connection details from environment variables
        NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://nlse_db:7687")
        NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password123")
        
        # Redis connection details from environment variables
        REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
        REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
        
        self.neo4j_driver = None
        self.redis_client = None

        self._connect_to_neo4j(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
        self._connect_to_redis(REDIS_HOST, REDIS_PORT)
    # --- SOUL INTERFACE: For Dreaming ---
    def get_random_significant_memory(self, limit: int = 1) -> list[dict]:
    """
    Queries the NLSE for a random significant memory (NeuroAtom) to be used
    for subconscious processing (dreaming).
    """
    plan = {
        "steps": [{
            "FetchBySignificance": {
                "limit": limit,
                "context_key": "final"
            }
        }],
        "mode": "Standard"
    }

    nlse_url = f"{LOGICAL_ENGINE_URL}/nlse/execute-plan"
    try:
        response = requests.post(nlse_url, json=plan)
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            return result.get("atoms", [])
        else:
            logger.error(f"NLSE failed to fetch significant memories: {result.get('message')}")
            return []
    except requests.RequestException as e:
        logger.error(f"Could not get random significant memory from NLSE: {e}")
        return []

    def get_symptoms_for_disease(self, disease_id: str) -> list[dict]:
    """
    Queries the NLSE to get the symptoms for a given disease protocol.
    """
    plan = {
        "steps": [
            { "Fetch": {"id": disease_id, "context_key": "disease"} },
            { "Traverse": {
                "from_context_key": "disease",
                "rel_type": "HAS_SYMPTOM",
                "output_key": "final"
            }}
        ],
        "mode": "Standard"
    }

    nlse_url = f"{LOGICAL_ENGINE_URL}/nlse/execute-plan"
    try:
        response = requests.post(nlse_url, json=plan)
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            symptom_atoms = result.get("atoms", [])
            return [s.get("properties", {}) for s in symptom_atoms]
        return []
    except requests.RequestException as e:
        logger.error(f"Could not get symptoms for disease {disease_id}: {e}")
        return []

    def get_all_diseases(self) -> list[dict]:
    """
    Gets all defined disease protocols from the NLSE using the FetchByType step.
    """
    plan = {
        "steps": [{
            "FetchByType": {
                "atom_type": "DiseaseProtocol",
                "context_key": "final"
            }
        }],
        "mode": "Standard"
    }

    nlse_url = f"{LOGICAL_ENGINE_URL}/nlse/execute-plan"
    try:
        response = requests.post(nlse_url, json=plan)
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            logger.info(f"NLSE: Found {len(result.get('atoms', []))} disease protocols.")
            return result.get("atoms", [])
        else:
            logger.error(f"NLSE failed to fetch disease types: {result.get('message')}")
            return []
    except requests.RequestException as e:
        logger.error(f"Could not get all diseases from NLSE: {e}")
        return []


    def find_disease_for_error(self, error_type: str, error_details: dict) -> tuple[str | None, str | None]:
    """
    Queries the NLSE to find a DiseaseProtocol that is caused by a specific error.
    Returns a tuple of (disease_id, disease_name) or (None, None).
    """
    logger.info(f"Querying NLSE for disease caused by '{error_type}'.")

    all_diseases = self.get_all_diseases()

    for disease in all_diseases:
        cause_prop_name = f"cause_{error_type}"
        if cause_prop_name in disease.get("properties", {}):
            disease_id = disease.get("id")
            disease_name = disease.get("properties", {}).get("name", {}).get("String")
            logger.info(f"Found matching disease: '{disease_name}' (ID: {disease_id})")
            return disease_id, disease_name

    logger.info(f"Querying NLSE for disease caused by '{error_type}'.")
    if error_type == "LOGICAL_FALLACY":
        return "LogicalCommonCold_ID_placeholder", "Logical Common Cold"
    return None, None

    def define_new_disease(self, definition: 'DiseaseDefinition') -> bool:
    """
    Translates a DiseaseDefinition object into a graph of NeuroAtoms
    and sends an ExecutionPlan to the NLSE to learn it.
    """
    from models import AtomType, RelationshipType, ExecutionMode
    import time

    plan_steps = []
    current_time = int(time.time())
    disease_id = str(uuid.uuid4())
    disease_relationships = []

    disease_properties = {
        "name": {"String": definition.name},
        "description": {"String": definition.description},
        "severity": {"Float": definition.severity},
        "stages": {"Int": definition.stages},
    }

    for symptom in definition.symptoms:
        symptom_id = str(uuid.uuid4())
        symptom_properties = {
            "name": {"String": f"Symptom for {definition.name}"},
            "target_vital": {"String": symptom.vital_name},
            "effect_formula": {"String": symptom.effect_formula},
        }
        plan_steps.append({"Write": {
            "id": symptom_id, "label": AtomType.Concept.value, "significance": 1.0,
            "access_timestamp": current_time, "properties": symptom_properties,
            "emotional_resonance": {}, "embedded_relationships": [], "context_id": None, "state_flags": 0,
        }})
        disease_relationships.append({
            "target_id": symptom_id, "rel_type": "HAS_SYMPTOM", "strength": 1.0, "access_timestamp": current_time,
        })

    for cause in definition.causes:
        disease_properties[f"cause_{cause.error_type}"] = {"String": cause.subtype or "general"}

    for treatment in definition.treatments:
        med_id = self.name_to_uuid_cache.setdefault(treatment.medication_name, str(uuid.uuid4()))
        disease_relationships.append({
            "target_id": med_id, "rel_type": "IS_CURED_BY", "strength": 1.0, "access_timestamp": current_time,
        })

    disease_atom_data = {
        "id": disease_id, "label": AtomType.DiseaseProtocol.value, "significance": 5.0,
        "access_timestamp": current_time, "properties": disease_properties,
        "emotional_resonance": {}, "embedded_relationships": disease_relationships,
        "context_id": None, "state_flags": 0,
    }
    plan_steps.append({"Write": disease_atom_data})

    plan = { "steps": plan_steps, "mode": ExecutionMode.STANDARD.value }

    nlse_url = f"{LOGICAL_ENGINE_URL}/nlse/execute-plan"
    try:
        response = requests.post(nlse_url, json=plan)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            logger.error(f"NLSE failed to define disease: {result.get('message')}")
            return False

        logger.info(f"Successfully sent ExecutionPlan to define disease '{definition.name}'.")
        return True
    except requests.RequestException as e:
        logger.error(f"Could not send disease definition to NLSE: {e}")
        return False

    def does_brain_know_truth_of(self, fact_info: dict) -> bool:
      """
       Simulates the Judiciary asking if the brain had knowledge to avoid an error.
      """
      error_subject = fact_info.get("subject")
    logger.info(f"Judiciary Interface: Checking brain's knowledge regarding '{error_subject}'.")

    known_topics = ["Socrates", "Earth", "Plato"]

    if error_subject in known_topics:
        logger.info(f"Knowledge Check: Brain has established knowledge on '{error_subject}'. Concluding this was a knowable error.")
        return True
    else:
        logger.info(f"Knowledge Check: Brain has no established knowledge on '{error_subject}'. Concluding this was an ignorant error.")
        return False
        
    # --- NEW METHOD: Storing Emotion Prototypes for the Heart ---
    def save_emotion_prototype(self, prototype_data: dict) -> bool:
        """
        Saves a newly formed (but still unlabeled) Emotion Prototype to Redis.
        We use a Redis Hash for this, with a key like "prototype:<uuid>".
        """
        if not self.redis_client:
            logger.warning("Redis not available, cannot save emotion prototype.")
            return False
            
        prototype_id = prototype_data.get("prototype_id")
        if not prototype_id:
            logger.error("Cannot save prototype: missing 'prototype_id'.")
            return False
            
        redis_key = f"prototype:{prototype_id}"
        
        try:
            # Serialize the entire dictionary into a single JSON string
            prototype_json = json.dumps(prototype_data)
            # Use SET instead of HMSET for a simple value
            self.redis_client.set(redis_key, prototype_json)
            logger.info(f"Successfully saved new emotion prototype '{redis_key}'.")
            return True
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to save emotion prototype to Redis: {e}")
            return False
        except TypeError as e:
            logger.error(f"Failed to serialize prototype data to JSON: {e}")
            return False

    # --- HEART PHASE C: Emotion Prototype Management ---

    def get_all_prototypes(self) -> list[dict]:
        """Retrieves all crystallized emotion prototypes from Redis."""
        if not self.redis_client: return []
        
        prototype_keys = self.redis_client.scan_iter("prototype:*")
        prototypes = []
        for key in prototype_keys:
            try:
                proto_json = self.redis_client.get(key)
                if proto_json:
                    prototypes.append(json.loads(proto_json))
            except redis.exceptions.RedisError as e:
                logger.error(f"Failed to retrieve prototype for key {key}: {e}")
        return prototypes

    def update_prototype_with_label(self, prototype_id: str, name: str, description: str) -> bool:
        """Finds a prototype by ID, adds a name and description, and saves it."""
        if not self.redis_client: return False

        redis_key = f"prototype:{prototype_id}"
        try:
            proto_json = self.redis_client.get(redis_key)
            if not proto_json:
                logger.warning(f"Attempted to label a non-existent prototype: {prototype_id}")
                return False
            
            prototype = json.loads(proto_json)
            
            # Add the cognitive labels
            prototype['name'] = name
            prototype['description'] = description
            
            # Save it back
            self.redis_client.set(redis_key, json.dumps(prototype))
            logger.info(f"Successfully labeled prototype {prototype_id} as '{name}'.")
            return True
        except (redis.exceptions.RedisError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Failed to label prototype {prototype_id}: {e}")
            return False

    def get_named_emotion_by_signature(self, physio_state: dict) -> dict | None:
        """
        Performs a reverse-lookup. Finds the NAMED emotion prototype whose
        average signature is most similar to the current physiological state.
        """
        all_prototypes = self.get_all_prototypes()
        
        # Filter for only those that have been cognitively labeled
        named_emotions = [p for p in all_prototypes if p.get("name")]
        
        if not named_emotions:
            return None
            
        # Convert current state to a vector
        feature_keys = sorted(physio_state.keys())
        current_vector = np.array([physio_state.get(k, 0.0) for k in feature_keys])

        best_match = None
        smallest_distance = float('inf')

        for emotion in named_emotions:
            # Convert emotion's average signature to a vector
            avg_sig = emotion.get("average_signature", {})
            emotion_vector = np.array([avg_sig.get(k, 0.0) for k in feature_keys])
            
            # Calculate Euclidean distance
            distance = np.linalg.norm(current_vector - emotion_vector)
            
            if distance < smallest_distance:
                smallest_distance = distance
                best_match = emotion
        
        # Define a threshold for what constitutes a "match"
        MATCH_THRESHOLD = 0.5 
        if best_match and smallest_distance < MATCH_THRESHOLD:
            logger.info(f"Matched current feeling to '{best_match['name']}' with distance {smallest_distance:.2f}")
            return best_match
            
        return None

    name_to_uuid_cache: dict = {}

    # --- NEW METHOD: Illusion Logging for the Heart ---
    def log_illusion(self, illusion_data: dict) -> None:
        """
        Logs a raw, unlabeled 'Illusion' from the Heart to a Redis list.
        This serves as the subconscious memory of raw feelings.
        """
        if not self.redis_client:
            logger.warning("Redis not available, cannot log illusion.")
            return

        try:
            # Serialize the dictionary to a JSON string for storage
            illusion_json = json.dumps(illusion_data)
            # LPUSH adds the new illusion to the beginning of the list
            self.redis_client.lpush("illusion_log", illusion_json)
            logger.info(f"Successfully logged new illusion to Redis: {illusion_json}")
        except redis.exceptions.RedisError as e:
            logger.error(f"Failed to log illusion to Redis: {e}")
        except TypeError as e:
            logger.error(f"Failed to serialize illusion data to JSON: {e}")

    def _connect_to_neo4j(self, uri, auth):
        """Establish a connection to the Neo4j database."""
        try:
            self.neo4j_driver = GraphDatabase.driver(uri, auth=auth)
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.neo4j_driver = None

    # --- NEW METHOD: PFC "Context Gathering" Function for HSM ---
    def get_context_for_hsm(self, node_names: list[str]) -> dict:
        """
        Retrieves a subgraph of nodes and their relationships from Neo4j
        to be used as the base state for a hypothetical model.
        """
        if not self.neo4j_driver:
            raise ServiceUnavailable("Cannot get context: Neo4j driver not available.")
        
        # This query finds all specified nodes and the relationships between them.
        query = (
            "MATCH (n:Concept) WHERE n.name IN $node_names "
            "OPTIONAL MATCH (n)-[r]-(m:Concept) WHERE m.name IN $node_names "
            "RETURN "
            "COLLECT(DISTINCT {name: n.name}) AS nodes, "
            "COLLECT(DISTINCT {subject_name: startNode(r).name, rel_type: type(r), object_name: endNode(r).name}) AS relationships"
        )

        with self.neo4j_driver.session() as session:
            result = session.run(query, node_names=node_names).single()
            if result:
                # Filter out null relationships that can occur if a node has no connections
                valid_relationships = [rel for rel in result["relationships"] if rel.get("rel_type") is not None]
                return {
                    "base_nodes": result["nodes"],
                    "base_relationships": valid_relationships
                }
        return {"base_nodes": [], "base_relationships": []}

    def _connect_to_redis(self, host, port):
        """Establish a connection to the Redis server."""
        try:
            self.redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True)
            self.redis_client.ping() # Check connection
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def ping_databases(self):
        """Pings databases to check live connectivity."""
        status = {"neo4j": "disconnected", "redis": "disconnected"}
        if self.neo4j_driver:
            try:
                self.neo4j_driver.verify_connectivity()
                status["neo4j"] = "connected"
            except (ServiceUnavailable, Exception) as e:
                 logger.warning(f"Neo4j ping failed: {e}")
        
        if self.redis_client:
            try:
                if self.redis_client.ping():
                    status["redis"] = "connected"
            except Exception as e:
                logger.warning(f"Redis ping failed: {e}")

        return status


    # --- NEW METHOD: Prefrontal Cortex "Read" Function ---
    def query_fact(self, subject: str, relationship_type: str) -> list[str]:
        """
        NEW: Creates an ExecutionPlan to query for a fact.
        """
        subject_id_str = self.name_to_uuid_cache.get(subject)
        if not subject_id_str:
            return []

        from models import RelationshipType
        # This plan fetches the starting atom, then traverses its relationships.
        plan = {
            "steps": [
                { "Fetch": {"id": subject_id_str, "context_key": "subject"} },
                { "Traverse": {
                    "from_context_key": "subject",
                    "rel_type": RelationshipType[relationship_type.upper()].value,
                    "output_key": "final"
                }}
            ]
        }
        
        nlse_url = f"{LOGICAL_ENGINE_URL}/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            logger.info(f"NLSE executed 'query' plan with message: {result.get('message')}")

            # Extract the names from the resulting atoms
            if result.get("success"):
                atom_results = result.get("atoms", [])
                return [
                    atom["properties"].get("name", {}).get("String", "Unknown")
                    for atom in atom_results
                ]
            return []
        except requests.RequestException as e:
            logger.error(f"Could not execute 'query' plan on NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def _query_neo4j_and_reinforce(self, subject: str, relationship_type: str) -> list[str]:
        """
        Private helper method to run the actual Neo4j query.
        This contains the logic from the previous step.
        """
        if not self.neo4j_driver:
            raise ServiceUnavailable("Cannot query fact: Neo4j driver not available.")
        
        rel_type = "".join(filter(str.isalnum, relationship_type.upper()))
        
        query_and_reinforce = (
            "MATCH path = (s:Concept {name: $subject_name})-[r:" + rel_type + "*]->(o:Concept) "
            "WITH path, relationships(path) AS rels, o "
            "FOREACH (rel IN rels | SET rel.significance = rel.significance + 0.5, rel.last_accessed = timestamp()) "
            "RETURN DISTINCT o.name AS object_name"
        )
        
        with self.neo4j_driver.session() as session:
            result_cursor = session.run(query_and_reinforce, subject_name=subject)
            results = [record["object_name"] for record in result_cursor]
            
            if results:
                logger.info(
                    f"PFC/Amygdala: Reinforced path for '({subject})-[{rel_type}]->(?)' and found: {results}"
                )
            
            return results
            
    def learn_fact(self, triple: StructuredTriple) -> None:
    """
    NEW & FINAL: Gets current emotional state and includes it
    in the ExecutionPlan sent to the NLSE.
    """
    from heart.orchestrator import heart_orchestrator # Import locally to avoid circular deps
    
    # 1. Get current emotional context from the Heart
    current_emotional_state = heart_orchestrator.get_current_hormonal_state()

    # 2. Build the plan, now including the emotional state
    plan = triple.to_neuro_atom_write_plan(
        self.name_to_uuid_cache,
        current_emotional_state
    )
    
    # 3. Send the emotionally-charged plan to the NLSE
    nlse_url = f"{LOGICAL_ENGINE_URL}/nlse/execute-plan"
    try:
        response = requests.post(nlse_url, json=plan)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            # Pass the failure reason from the NLSE (e.g., LVE failure)
            raise Exception(f"NLSE failed to learn fact: {result.get('message')}")
        
        logger.info(f"NLSE executed 'learn' plan with result: {result.get('message')}")
    
    except requests.RequestException as e:
        logger.error(f"Could not execute 'learn' plan on NLSE: {e}")
        raise ServiceUnavailable("NLSE service is unavailable.") from e
            
    def close(self):
        """Closes database connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("Neo4j connection closed.")
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis connection closed.")

    # --- NEW METHOD: PFC "Introspection" for Curiosity ---
    def find_knowledge_gap(self, limit: int = 1) -> list[str]:
    """
    Finds concepts in the knowledge graph that are poorly understood
    (i.e., have very few relationships) to trigger curiosity.
    """
    if not self.neo4j_driver:
        return []
    
    query = (
        "MATCH (c:Concept) "
        "WITH c, size((c)--()) AS degree "
        "WHERE degree = 1 "
        "RETURN c.name AS topic "
        "LIMIT $limit"
    )
    
    with self.neo4j_driver.session() as session:
        result_cursor = session.run(query, limit=limit)
        topics = [record["topic"] for record in result_cursor]
        
        if topics:
            logger.info(f"PFC Introspection: Identified knowledge gaps for topics: {topics}.")
        
        return topics
        
    # --- NEW METHOD: Microglia "Pruning" Function ---
    def prune_weak_facts(self, significance_threshold: float = 0.0) -> int:
        """
        Finds and deletes relationships (memories) that are below a certain
        significance threshold. Represents the Microglia's pruning function.
        """
        if not self.neo4j_driver:
            # Silently return if DB is not available, as this is a background task.
            return 0
        
        # We use DETACH DELETE to also remove the relationship from the nodes.
        # This will not delete the nodes themselves, only the weak connection.
        query = (
            "MATCH ()-[r]-() "
            "WHERE r.significance <= $threshold "
            "DETACH DELETE r "
            "RETURN count(r)"
        )

        pruned_count = 0
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(query, threshold=significance_threshold).single()
                if result:
                    pruned_count = result[0]
                
                if pruned_count > 0:
                    logger.info(f"Microglia pruned {pruned_count} weak relationship(s).")
        except Exception as e:
            logger.error(f"Microglia encountered an error during pruning: {e}")
        
        return pruned_count
# Create a singleton instance to be imported by other parts of the app
db_manager = DatabaseManager()
