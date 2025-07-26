# --- IMPORTS ---

# Standard library imports
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

# Third-party imports
import numpy as np
import redis
import requests
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

# Local application imports
from models import (AtomType, DiseaseDefinition, ExecutionMode, RelationshipType,
                    StructuredTriple)


# --- SETUP ---

# Initialize the logger for this module
logger = logging.getLogger(__name__)

# --- DATABASE MANAGER CLASS ---

class DatabaseManager:
    """
    Manages connections and interactions with the NLSE (via logical_engine),
    Redis, and provides a legacy interface for Neo4j.
    """

    # --- INITIALIZATION AND CONNECTION MANAGEMENT ---

    def __init__(self):
        """Initializes the DatabaseManager, connects to databases, and preloads caches."""
        # This check prevents re-initialization for the singleton pattern
        if hasattr(self, '_initialized') and self._initialized:
            return

        # Configuration
        REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
        REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

        self.logger = logging.getLogger(__name__)
        self.redis_client = None # Start as None

        # Caches for mapping human-readable names to internal UUIDs
        self.name_to_uuid_cache: Dict[str, str] = {}
        self.uuid_to_name_cache: Dict[str, str] = {}

        # Establish connections
        self._connect_to_redis(REDIS_HOST, REDIS_PORT)

        # Preload the cache with existing knowledge from the NLSE
        # self.preload_existing_knowledge() # We can disable this for unit tests
        self._initialized = True

    def _connect_to_neo4j(self, uri: str, auth: tuple):
        """Establishes a connection to the Neo4j database."""
        try:
            self.neo4j_driver = GraphDatabase.driver(uri, auth=auth)
            self.logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")
            self.neo4j_driver = None

    def _connect_to_redis(self, host: str, port: int):
        """Establishes a connection to the Redis server, handling connection errors."""
        try:
            # Create a client instance
            client = redis.Redis(host=host, port=port, db=0, decode_responses=True)
            # Test the connection
            client.ping()
            # If successful, assign it to the class attribute
            self.redis_client = client
            self.logger.info("Successfully connected to Redis.")
        except redis.exceptions.ConnectionError as e:
            # If the server is not running, this block will execute.
            self.logger.error(f"Failed to connect to Redis: {e}")
            # self.redis_client will correctly remain None

    def ping_databases(self) -> Dict[str, str]:
        """Pings databases to check live connectivity."""
        status = {"neo4j": "disconnected", "redis": "disconnected"}
        if self.neo4j_driver:
            try:
                self.neo4j_driver.verify_connectivity()
                status["neo4j"] = "connected"
            except (ServiceUnavailable, Exception) as e:
                self.logger.warning(f"Neo4j ping failed: {e}")
        if self.redis_client:
            try:
                if self.redis_client.ping():
                    status["redis"] = "connected"
            except Exception as e:
                self.logger.warning(f"Redis ping failed: {e}")
        return status

    def close(self):
        """Closes all active database connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            self.logger.info("Neo4j connection closed.")
        if self.redis_client:
            self.redis_client.close()
            self.logger.info("Redis connection closed.")

    # --- INTERNAL NLSE HELPER ---

    def _execute_nlse_plan(self, plan: dict, operation_name: str) -> dict:
        """A centralized helper for sending execution plans to the NLSE."""
        # This is the corrected, hardcoded URL for the Colab environment.
        nlse_url = "http://127.0.0.1:8000/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan, timeout=10)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                # Use a more specific error if the plan fails
                raise Exception(f"NLSE plan '{operation_name}' failed: {result.get('message')}")
            self.logger.info(f"NLSE executed '{operation_name}' plan successfully.")
            return result
        except requests.RequestException as e:
            self.logger.error(f"Could not execute '{operation_name}' plan on NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    # --- CORE KNOWLEDGE & LEARNING (NLSE) ---

    def learn_word(self, word_str: str) -> None:
        """
        Teaches the AGI a new word by breaking it down into its constituent
        characters and storing the structure in the NLSE.
        """
        plan_steps = []
        current_time = int(time.time())
        word_str_lower = word_str.lower()
        word_id = self.name_to_uuid_cache.setdefault(f"word:{word_str_lower}", str(uuid.uuid4()))
        word_relationships = []

        # Create atoms for each unique character and link them to the word
        for char in sorted(list(set(word_str_lower))):
            char_concept_name = f"char:{char}"
            char_id = self.name_to_uuid_cache.setdefault(char_concept_name, str(uuid.uuid4()))
            word_relationships.append({
                "target_id": char_id, "rel_type": RelationshipType.HAS_PART.value,
                "strength": 1.0, "access_timestamp": current_time,
            })
            # Create a write step for the character atom itself (upsert will handle it)
            char_atom_data = {
                "id": char_id, "label": AtomType.Concept.value, "significance": 1.0,
                "access_timestamp": current_time, "context_id": None, "state_flags": 0,
                "properties": {"name": {"String": char}}, "emotional_resonance": {},
                "embedded_relationships": []
            }
            plan_steps.append({"Write": char_atom_data})

        # Assemble the main Word atom with its relationships
        word_atom_data = {
            "id": word_id, "label": AtomType.Word.value, "significance": 1.0,
            "access_timestamp": current_time, "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": word_str_lower}}, "emotional_resonance": {},
            "embedded_relationships": word_relationships
        }
        plan_steps.append({"Write": word_atom_data})

        plan = {"steps": plan_steps, "mode": ExecutionMode.STANDARD.value}
        self._execute_nlse_plan(plan, f"learn word '{word_str}'")

    def label_concept(self, word_str: str, concept_name: str) -> None:
        """
        Teaches the AGI that a word is the label for a concept, and correctly
        updates the in-memory cache by building a valid ExecutionPlan.
        """
        word_str_lower = word_str.lower()
        concept_name_lower = concept_name.lower()
        current_time = int(time.time())

        word_key = f"word:{word_str_lower}"
        concept_key = f"concept:{concept_name_lower}"

        word_id = self.name_to_uuid_cache.get(word_key)
        if not word_id:
            msg = f"Cannot label concept. Word '{word_str}' is unknown. Please teach it first."
            self.logger.error(msg)
            raise ValueError(msg)

        # Get or create the UUID for the new concept
        concept_id = self.name_to_uuid_cache.get(concept_key, str(uuid.uuid4()))

        # Update both caches with the new concept information.
        self.name_to_uuid_cache[concept_key] = concept_id
        self.uuid_to_name_cache[concept_id] = concept_name

        # --- THE UNDENIABLE FIX ---
        # The ExecutionPlan must contain complete NeuroAtom definitions for the Write step.
        
        # Define the relationship that links the Word to the Concept
        labeling_relationship = {
            "target_id": concept_id,
            "rel_type": RelationshipType.IS_LABEL_FOR.value,
            "strength": 1.0,
            "access_timestamp": current_time,
        }

        # Define the full atom structure for the Word, including the new relationship
        word_atom_update = {
            "id": word_id,
            "label": AtomType.Word.value,
            "significance": 1.0,
            "access_timestamp": current_time,
            "properties": {"name": {"String": word_str_lower}},
            "emotional_resonance": {},
            "embedded_relationships": [labeling_relationship],
            "context_id": None,
            "state_flags": 0,
        }
        
        # Define the full atom structure for the new Concept
        concept_atom_data = {
            "id": concept_id,
            "label": AtomType.Concept.value,
            "significance": 1.0,
            "access_timestamp": current_time,
            "properties": {"name": {"String": concept_name}},
            "emotional_resonance": {},
            "embedded_relationships": [],
            "context_id": None,
            "state_flags": 0,
        }

        # The plan now contains two valid Write steps. The NLSE's upsert logic
        # will correctly merge the new relationship into the existing Word atom.
        plan = {
            "steps": [{"Write": concept_atom_data}, {"Write": word_atom_update}],
            "mode": ExecutionMode.STANDARD.value
        }
        # --- END FIX ---

        self._execute_nlse_plan(plan, f"label concept '{concept_name}'")

    def learn_fact(self, triple: StructuredTriple, heart_orchestrator: Any) -> None:
        """
        Learns a conceptual fact by creating a relationship between two known concepts,
        influenced by the current emotional state, using a valid ExecutionPlan.
        """
        current_time = int(time.time())

        # Find Concept IDs for the subject and object using the correct cache keys.
        subject_concept_id = self.get_uuid_for_name(triple.subject)
        object_concept_id = self.get_uuid_for_name(triple.object)

        if not subject_concept_id or not object_concept_id:
            msg = f"Cannot learn fact. Concept for '{triple.subject}' or '{triple.object}' is unknown. Please label them first."
            self.logger.error(msg)
            raise ValueError(msg)

        # Get current emotional context from the Heart
        current_emotional_state = heart_orchestrator.get_current_hormonal_state()

        # --- THE UNDENIABLE FIX ---
        # The ExecutionPlan must send a complete atom structure for the Write/Upsert.
        # However, we only need to specify the ID and the new relationship to be merged.
        # The NLSE's internal logic will handle the merge with the existing atom data.

        # Create the relationship to be added
        fact_relationship = {
            "target_id": object_concept_id,
            "rel_type": RelationshipType[triple.relationship.upper()].value,
            "strength": 1.0,
            "access_timestamp": current_time,
        }

        # Create an ExecutionPlan to UPDATE the subject concept atom with this new fact.
        # The Rust 'Write' step acts as an upsert: it finds the atom by ID and merges
        # the fields provided. We only need to provide the ID and the new relationship.
        subject_concept_update = {
            "id": subject_concept_id,
            # Provide default/empty values for other required fields for a valid NeuroAtom
            "label": AtomType.Concept.value,
            "properties": {}, # Properties will be merged, not overwritten
            "emotional_resonance": current_emotional_state,
            "embedded_relationships": [fact_relationship],
            "significance": 1.0, # Significance will be updated
            "access_timestamp": current_time,
            "context_id": None,
            "state_flags": 0
        }

        plan = {"steps": [{"Write": subject_concept_update}], "mode": ExecutionMode.STANDARD.value}
        # --- END FIX ---
        
        self._execute_nlse_plan(plan, "learn conceptual fact")

    def query_fact(self, subject: str, relationship: str) -> List[str]:
        """
        Queries the NLSE for facts related to a subject by building a valid
        Fetch -> Traverse execution plan.
        """
        self.logger.info(f"Received query: ({subject}) -[{relationship}]-> ?")
        
        # Find the UUID for the subject concept.
        subject_uuid = self.get_uuid_for_name(subject)

        if not subject_uuid:
            self.logger.warning(f"Query failed: Could not find a UUID for the concept '{subject}'.")
            return []

        self.logger.debug(f"Found UUID '{subject_uuid}' for concept '{subject}'. Building query plan...")

        # The ExecutionPlan must exactly match the Rust data structures.
        plan = {
            "steps": [
                {
                    "Fetch": {
                        "id": subject_uuid,
                        "context_key": "start_node" # Define the output of this step
                    }
                },
                {
                    "Traverse": {
                        "from_context_key": "start_node", # Use the output of the previous step
                        "rel_type": relationship.upper(), # Corrected key
                        "output_key": "result_nodes" # Define the output of this step
                    }
                }
            ],
            "mode": "Standard"
        }

        try:
            result_data = self._execute_nlse_plan(plan, "query fact")
            
            processed_results = []
            # The Rust QueryResult returns the final list of atoms directly in the "atoms" key.
            if result_data and "atoms" in result_data:
                for atom in result_data.get("atoms", []):
                    # Ensure properties and name exist before trying to access them
                    name_property = atom.get("properties", {}).get("name", {})
                    if isinstance(name_property, dict):
                         atom_name = name_property.get("String")
                         if atom_name:
                            processed_results.append(atom_name)
            
            self.logger.info(f"Query for '{subject}' found results: {processed_results}")
            return processed_results

        except ServiceUnavailable:
            self.logger.error(f"Query plan for '{subject}' was rejected by the NLSE. The plan may be invalid.")
            return []
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during query_fact for '{subject}': {e}", exc_info=True)
            return []

    def find_knowledge_gap(self, limit: int = 1) -> List[str]:
        """Finds the least-accessed (lowest significance) atoms in the NLSE."""
        plan = {
            "steps": [{"FetchBySignificance": {"limit": limit, "context_key": "final"}}],
            "mode": ExecutionMode.STANDARD.value
        }
        result = self._execute_nlse_plan(plan, "find knowledge gap")
        return [
            atom.get("properties", {}).get("name", {}).get("String", "Unknown")
            for atom in result.get("atoms", [])
        ]

    # --- HEART & EMOTION INTERFACE (Redis) ---

    def log_illusion(self, illusion_data: dict) -> None:
        """Logs an illusion event to a Redis list."""
        if not self.redis_client:
            self.logger.warning("Redis not available, cannot log illusion.")
            return
        try:
            illusion_json = json.dumps(illusion_data)
            self.redis_client.lpush("illusion_log", illusion_json)
            self.logger.info("Successfully logged new illusion to Redis.")
        except (redis.exceptions.RedisError, TypeError) as e:
            self.logger.error(f"Failed to log illusion to Redis: {e}")

    def get_all_prototypes(self) -> List[Dict]:
        """Retrieves all emotion prototypes from Redis."""
        if not self.redis_client:
            return []
        try:
            prototype_keys = self.redis_client.scan_iter("prototype:*")
            prototypes = []
            for key in prototype_keys:
                proto_json = self.redis_client.get(key)
                if proto_json:
                    prototypes.append(json.loads(proto_json))
            return prototypes
        except redis.exceptions.RedisError as e:
            self.logger.error(f"Failed to retrieve prototypes from Redis: {e}")
            return []

    def update_prototype_with_label(self, prototype_id: str, name: str, description: str) -> bool:
        """Updates an emotion prototype in Redis with a human-readable label."""
        if not self.redis_client:
            return False
        redis_key = f"prototype:{prototype_id}"
        try:
            proto_json = self.redis_client.get(redis_key)
            if not proto_json:
                self.logger.warning(f"Attempted to label a non-existent prototype: {prototype_id}")
                return False

            prototype = json.loads(proto_json)
            prototype['name'] = name
            prototype['description'] = description
            self.redis_client.set(redis_key, json.dumps(prototype))
            self.logger.info(f"Successfully labeled prototype {prototype_id} as '{name}'.")
            return True
        except (redis.exceptions.RedisError, TypeError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to label prototype {prototype_id}: {e}")
            return False

    def get_named_emotion_by_signature(self, physio_state: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Finds the best-matching named emotion for a given physiological state."""
        all_prototypes = self.get_all_prototypes()
        named_emotions = [p for p in all_prototypes if p.get("name")]
        if not named_emotions:
            return None

        feature_keys = sorted(physio_state.keys())
        current_vector = np.array([physio_state.get(k, 0.0) for k in feature_keys])

        best_match, smallest_distance = None, float('inf')
        for emotion in named_emotions:
            avg_sig = emotion.get("average_signature", {})
            emotion_vector = np.array([avg_sig.get(k, 0.0) for k in feature_keys])
            distance = np.linalg.norm(current_vector - emotion_vector)
            if distance < smallest_distance:
                smallest_distance, best_match = distance, emotion

        MATCH_THRESHOLD = 0.5
        if best_match and smallest_distance < MATCH_THRESHOLD:
            self.logger.info(f"Matched current feeling to '{best_match['name']}' with distance {smallest_distance:.2f}")
            return best_match
        return None

    # --- JUDICIARY & HEALTH INTERFACE (NLSE) ---

    def does_brain_know_truth_of(self, fact_info: Dict[str, Any]) -> bool:
        """Placeholder check to see if the AGI has established knowledge on a topic."""
        error_subject = fact_info.get("subject")
        self.logger.info(f"Judiciary Interface: Checking knowledge regarding '{error_subject}'.")
        known_topics = ["Socrates", "Earth", "Plato"]
        if error_subject in known_topics:
            self.logger.info(f"Knowledge Check: Brain has established knowledge on '{error_subject}'.")
            return True
        self.logger.info(f"Knowledge Check: Brain has no established knowledge on '{error_subject}'.")
        return False

    def define_new_disease(self, definition: DiseaseDefinition) -> bool:
        """Defines a new disease protocol in the NLSE, including symptoms, causes, and treatments."""
        plan_steps = []
        current_time = int(time.time())
        disease_id = str(uuid.uuid4())
        disease_relationships = []
        disease_properties = {
            "name": {"String": definition.name}, "description": {"String": definition.description},
            "severity": {"Float": definition.severity}, "stages": {"Int": definition.stages},
        }

        # Create Symptom atoms and link them
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
                "target_id": symptom_id, "rel_type": RelationshipType.HAS_SYMPTOM.value,
                "strength": 1.0, "access_timestamp": current_time,
            })

        # Link to Cause atoms (error types)
        for cause in definition.causes:
            cause_id = self.name_to_uuid_cache.setdefault(f"error_type:{cause.error_type}", str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": cause_id, "rel_type": RelationshipType.IS_CAUSED_BY.value,
                "strength": 1.0, "access_timestamp": current_time,
            })

        # Link to Treatment atoms (medications)
        for treatment in definition.treatments:
            med_id = self.name_to_uuid_cache.setdefault(f"medication:{treatment.medication_name}", str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": med_id, "rel_type": RelationshipType.IS_CURED_BY.value,
                "strength": 1.0, "access_timestamp": current_time,
            })

        # Create the main DiseaseProtocol atom
        disease_atom_data = {
            "id": disease_id, "label": AtomType.DiseaseProtocol.value, "significance": 5.0,
            "access_timestamp": current_time, "properties": disease_properties,
            "emotional_resonance": {}, "embedded_relationships": disease_relationships,
            "context_id": None, "state_flags": 0,
        }
        plan_steps.append({"Write": disease_atom_data})

        plan = {"steps": plan_steps, "mode": ExecutionMode.STANDARD.value}
        self._execute_nlse_plan(plan, f"define disease '{definition.name}'")
        self.name_to_uuid_cache[definition.name] = disease_id
        return True

    def get_all_diseases(self) -> list[dict]:
        """Retrieves all defined DiseaseProtocol atoms from the NLSE."""
        plan = {
            "steps": [{"FetchByType": {"atom_type": "DiseaseProtocol", "context_key": "final"}}],
            "mode": ExecutionMode.STANDARD.value
        }
        result = self._execute_nlse_plan(plan, "get all diseases")
        return result.get("atoms", [])

    def find_disease_for_error(self, error_type: str, error_details: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Finds a disease that is caused by a specific type of error."""
        self.logger.info(f"Querying NLSE for disease caused by '{error_type}'.")
        for disease_atom in self.get_all_diseases():
            cause_prop_name = f"cause_{error_type}"
            if cause_prop_name in disease_atom.get("properties", {}):
                disease_id = disease_atom.get("id")
                disease_name = disease_atom.get("properties", {}).get("name", {}).get("String")
                self.logger.info(f"Found matching disease: '{disease_name}' (ID: {disease_id})")
                return disease_id, disease_name
        self.logger.info(f"No specific disease protocol found for error type '{error_type}'.")
        return None, None

    def get_symptoms_for_disease(self, disease_id: str) -> list[dict]:
        """Retrieves all symptom atoms connected to a specific disease."""
        plan = {
            "steps": [
                {"Fetch": {"id": disease_id, "context_key": "disease"}},
                {"Traverse": {
                    "from_context_key": "disease",
                    "rel_type": "HAS_SYMPTOM",
                    "output_key": "final"
                }}
            ],
            "mode": ExecutionMode.STANDARD.value
        }
        result = self._execute_nlse_plan(plan, f"get symptoms for disease {disease_id}")
        return [s.get("properties", {}) for s in result.get("atoms", [])]

    # --- SOUL & MEMORY INTERFACE (NLSE) ---

    def get_random_significant_memory(self, limit: int = 1) -> List[Dict]:
        """
        Retrieves a significant memory (atom) from the NLSE, typically for the
        Soul's dream cycle. This is equivalent to `find_knowledge_gap`.
        """
        plan = {
            "steps": [{"FetchBySignificance": {"limit": limit, "context_key": "final"}}],
            "mode": ExecutionMode.STANDARD.value
        }
        result = self._execute_nlse_plan(plan, "get random significant memory")
        return result.get("atoms", [])

    # --- PLACEHOLDER & CACHING METHODS ---

    def get_uuid_for_name(self, name: str) -> Optional[str]:
        """
        Resolves a human-readable name to its corresponding UUID using the in-memory cache.
        """
        key = f"concept:{name.lower()}"
        uuid = self.name_to_uuid_cache.get(key)
        if not uuid:
            self.logger.warning(f"Cache miss: Could not find UUID for concept '{name}'.")
        return uuid

    def preload_existing_knowledge(self):
        """
        Preloads the name/UUID cache from the NLSE.
        (This is a placeholder for a method called in __init__).
        """
        self.logger.info("Preloading existing knowledge cache... (Placeholder)")
        pass

    def validate_fact_with_lve(self, triple: StructuredTriple) -> dict:
        """
        Legacy validation check. In the current architecture, validation occurs
        within the NLSE during the 'Write' operation itself.
        """
        return {
            "is_valid": True,
            "reason": "Validation is now handled by the NLSE on write during 'learn_fact'."
        }

# --- SINGLETON INSTANCE ---
# Create a single, shared instance of the DatabaseManager to be imported by other modules.
db_manager = DatabaseManager()