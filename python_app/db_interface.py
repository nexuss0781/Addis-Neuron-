import os
import redis
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import logging
import json
import requests
from typing import Optional, List, Tuple
import numpy as np
import uuid
import time # For time.time() in NeuroAtom creation

# Import Pydantic models for type hinting and data serialization
from models import StructuredTriple, DiseaseDefinition, ExecutionMode, AtomType, RelationshipType


logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages connections and interactions with NLSE (via logical_engine),
    Neo4j (legacy/optional), and Redis databases.
    """
    def __init__(self):
        # Neo4j connection details (still here for optional legacy/testing)
        NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://nlse_db:7687")
        NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password123")
        
        # Redis connection details
        REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
        REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
        
        self.neo4j_driver = None
        self.redis_client = None

        # --- NLSE Integration ---
        # This cache is for mapping human-readable names to NLSE Uuids for planning.
        # It's a temporary measure until NLSE can do string-to-UUID lookup internally.
        self.name_to_uuid_cache: Dict[str, str] = {}
        
        # Connect to databases
        self._connect_to_neo4j(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
        self._connect_to_redis(REDIS_HOST, REDIS_PORT)

    def _connect_to_neo4j(self, uri, auth):
        """Establish a connection to the Neo4j database."""
        try:
            self.neo4j_driver = GraphDatabase.driver(uri, auth=auth)
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.neo4j_driver = None

    def _connect_to_redis(self, host, port):
        """Establish a connection to the Redis server."""
        try:
            self.redis_client = redis.Redis(host=host, port=port, db=0, decode_responses=True)
            self.redis_client.ping() # Check connection
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def ping_databases(self) -> Dict[str, str]:
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

    def close(self):
        """Closes database connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("Neo4j connection closed.")
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis connection closed.")

    # --- NLSE INTEGRATED METHODS ---

    def learn_fact(self, triple: StructuredTriple) -> None:
        """
        Creates an ExecutionPlan to learn a new fact.
        Gets current emotional state and includes it in the plan sent to the NLSE.
        """
        # Import locally to avoid circular dependencies at module import time
        from heart.orchestrator import heart_orchestrator
        
        current_emotional_state = heart_orchestrator.get_current_hormonal_state()
        plan_data = triple.to_neuro_atom_write_plan(
            self.name_to_uuid_cache,
            current_emotional_state
        )
        
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan_data)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to learn fact: {result.get('message')}")
            
            logger.info(f"NLSE executed 'learn' plan: {result.get('message')}")
        
        except requests.RequestException as e:
            logger.error(f"Could not execute 'learn' plan on NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def query_fact(self, subject: str, relationship_type: str) -> List[str]:
        """
        Creates an ExecutionPlan to query for a fact using the NLSE.
        """
        subject_id_str = self.name_to_uuid_cache.get(subject)
        if not subject_id_str:
            logger.info(f"Query for '{subject}' failed: ID not found in cache.")
            return []

        # This plan fetches the starting atom, then traverses its relationships.
        plan = {
            "steps": [
                { "Fetch": {"id": subject_id_str, "context_key": "subject"} },
                { "Traverse": {
                    "from_context_key": "subject",
                    "rel_type": relationship_type.upper(),
                    "output_key": "final"
                }}
            ],
            "mode": "Standard" # Default mode
        }
        
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            logger.info(f"NLSE executed 'query' plan: {result.get('message')}")

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

    def get_context_for_hsm(self, node_names: List[str]) -> Dict[str, Any]:
        """
        Retrieves a subgraph of nodes and their relationships from NLSE
        to be used as the base state for a hypothetical model.
        """
        # This would construct a complex ExecutionPlan to fetch specified nodes
        # and their direct relationships. For now, it's a placeholder returning empty data.
        logger.warning("get_context_for_hsm is a placeholder. Returning empty data.")
        return {"base_nodes": [], "base_relationships": []}

    def find_knowledge_gap(self, limit: int = 1) -> List[str]:
        """
        Queries the NLSE for concepts with low relationship degree to trigger curiosity.
        """
        # This plan uses FetchBySignificance as a proxy for 'knowledge gap'
        # A more sophisticated check would directly query degree or contextual emptiness.
        plan = {
            "steps": [{
                "FetchBySignificance": {
                    "limit": limit,
                    "context_key": "final"
                }
            }],
            "mode": "Standard"
        }
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if result.get("success"):
                # Return names of fetched atoms as topics
                return [atom.get("properties", {}).get("name", {}).get("String", "Unknown") for atom in result.get("atoms", [])]
            return []
        except requests.RequestException as e:
            logger.error(f"Could not find knowledge gap via NLSE: {e}")
            return []

    def prune_weak_facts(self, significance_threshold: float = 0.0) -> int:
        """
        This functionality is currently handled by the DecayAgent in the Rust NLSE.
        This Python method acts as a trigger or a fallback if needed.
        For now, it's a placeholder.
        """
        logger.info("Prune weak facts called (Python side). Rust DecayAgent handles actual pruning.")
        return 0

    # --- HEART PHASE C: Emotion Prototype Management ---

    def get_all_prototypes(self) -> List[Dict]:
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
            
            prototype['name'] = name
            prototype['description'] = description
            
            self.redis_client.set(redis_key, json.dumps(prototype))
            logger.info(f"Successfully labeled prototype {prototype_id} as '{name}'.")
            return True
        except (redis.exceptions.RedisError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Failed to label prototype {prototype_id}: {e}")
            return False

    def get_named_emotion_by_signature(self, physio_state: Dict[str, float]) -> Dict[str, Any] | None:
        """
        Performs a reverse-lookup. Finds the NAMED emotion prototype whose
        average signature is most similar to the current physiological state.
        """
        all_prototypes = self.get_all_prototypes()
        
        named_emotions = [p for p in all_prototypes if p.get("name")]
        
        if not named_emotions: return None
            
        feature_keys = sorted(physio_state.keys())
        current_vector = np.array([physio_state.get(k, 0.0) for k in feature_keys])

        best_match = None
        smallest_distance = float('inf')

        for emotion in named_emotions:
            avg_sig = emotion.get("average_signature", {})
            emotion_vector = np.array([avg_sig.get(k, 0.0) for k in feature_keys])
            
            distance = np.linalg.norm(current_vector - emotion_vector)
            
            if distance < smallest_distance:
                smallest_distance = distance
                best_match = emotion
        
        MATCH_THRESHOLD = 0.5 
        if best_match and smallest_distance < MATCH_THRESHOLD:
            logger.info(f"Matched current feeling to '{best_match['name']}' with distance {smallest_distance:.2f}")
            return best_match
            
        return None

    # --- JUDICIARY INTERFACE ---
    def does_brain_know_truth_of(self, fact_info: Dict[str, Any]) -> bool:
        """
        Simulates the Judiciary asking the Brain if it possessed the knowledge.
        This is a placeholder. A real implementation would query NLSE significance.
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

    def find_disease_for_error(self, error_type: str, error_details: Dict[str, Any]) -> Tuple[str | None, str | None]:
        """
        Queries the NLSE to find a DiseaseProtocol that is caused by a specific error.
        Returns a tuple of (disease_id, disease_name) or (None, None).
        """
        logger.info(f"Querying NLSE for disease caused by '{error_type}'.")

        all_diseases_data = self.get_all_diseases()

        for disease_atom in all_diseases_data:
            cause_prop_name = f"cause_{error_type}"
            if cause_prop_name in disease_atom.get("properties", {}):
                disease_id = disease_atom.get("id")
                disease_name = disease_atom.get("properties", {}).get("name", {}).get("String")
                logger.info(f"Found matching disease: '{disease_name}' (ID: {disease_id})")
                return disease_id, disease_name
        
        logger.info(f"No specific disease protocol found for error type '{error_type}' in NLSE.")
        return None, None

    def define_new_disease(self, definition: DiseaseDefinition) -> bool:
        """
        Translates a DiseaseDefinition object into a graph of NeuroAtoms
        and sends an ExecutionPlan to the NLSE to learn it.
        """
        import time # Needed for int(time.time())

        plan_steps = []
        current_time = int(time.time())

        # 1. Create the main DiseaseProtocol Atom
        disease_id = str(uuid.uuid4())
        disease_relationships = []
        disease_properties = {
            "name": {"String": definition.name},
            "description": {"String": definition.description},
            "severity": {"Float": definition.severity},
            "stages": {"Int": definition.stages},
        }

        # 2. Create Symptom atoms and relationships
        for symptom in definition.symptoms:
            symptom_id = str(uuid.uuid4())
            symptom_properties = {
                "name": {"String": f"Symptom for {definition.name}"},
                "target_vital": {"String": symptom.vital_name},
                "effect_formula": {"String": symptom.effect_formula},
            }
            plan_steps.append({"Write": {
                "id": symptom_id, "label": AtomType.Symptom.value, "significance": 1.0,
                "access_timestamp": current_time, "properties": symptom_properties,
                "emotional_resonance": {}, "embedded_relationships": [], "context_id": None, "state_flags": 0,
            }})
            disease_relationships.append({
                "target_id": symptom_id, "rel_type": RelationshipType.HasSymptom.value, "strength": 1.0, "access_timestamp": current_time,
            })
            
        # 3. Create Cause atoms and relationships (simplified)
        for cause in definition.causes:
             # In a more advanced setup, this would link to a specific ErrorType atom
            disease_relationships.append({
                "target_id": self.name_to_uuid_cache.setdefault(cause.error_type, str(uuid.uuid4())), # Placeholder ID for the error type atom
                "rel_type": RelationshipType.IsCausedBy.value,
                "strength": 1.0, "access_timestamp": current_time,
            })
            
        # 4. Create Treatment atoms and relationships
        for treatment in definition.treatments:
            med_id = self.name_to_uuid_cache.setdefault(treatment.medication_name, str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": med_id, "rel_type": RelationshipType.IsCuredBy.value, "strength": 1.0, "access_timestamp": current_time,
            })
        
        # 5. Assemble and add the final DiseaseProtocol atom write step
        disease_atom_data = {
            "id": disease_id, "label": AtomType.DiseaseProtocol.value, "significance": 5.0, # Core medical knowledge is highly significant
            "access_timestamp": current_time, "properties": disease_properties,
            "emotional_resonance": {}, "embedded_relationships": disease_relationships,
            "context_id": None, "state_flags": 0,
        }
        plan_steps.append({"Write": disease_atom_data})
        
        # 6. Build the final execution plan
        plan = { "steps": plan_steps, "mode": ExecutionMode.STANDARD.value }

        # 7. Send the plan to the NLSE
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                logger.error(f"NLSE failed to define disease: {result.get('message')}")
                return False
            
            logger.info(f"Successfully sent ExecutionPlan to define disease '{definition.name}'.")
            # Store the disease ID in our temporary cache for quick lookups
            self.name_to_uuid_cache[definition.name] = disease_id
            return True
        except requests.RequestException as e:
            logger.error(f"Could not send disease definition to NLSE: {e}")
            return False

# Create a singleton instance to be imported by other parts of the app
db_manager = DatabaseManager()