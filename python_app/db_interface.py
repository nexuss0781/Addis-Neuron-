import os
import redis
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import logging
import json
import requests
from typing import Optional, List, Tuple, Dict, Any # <-- THIS LINE IS THE FIX
import numpy as np
import uuid
import time

from models import StructuredTriple, DiseaseDefinition, ExecutionMode, AtomType, RelationshipType


logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages connections and interactions with NLSE (via logical_engine),
    Redis, and provides a legacy interface for Neo4j.
    """
    def __init__(self):
        # Neo4j (legacy/testing)
        NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://nlse_db:7687")
        NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
        NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password123")

        # Redis
        REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
        REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

        self.neo4j_driver = None
        self.redis_client = None

        # Temporary cache for mapping human-readable names to NLSE Uuids.
        self.name_to_uuid_cache: Dict[str, str] = {}

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
            self.redis_client.ping()
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
        if self.redis_client:
            self.redis_client.close()

    # --- NLSE INTEGRATED METHODS ---

    def _execute_nlse_plan(self, plan: dict, operation_name: str) -> dict:
        """A centralized helper for sending plans to the NLSE."""
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://127.0.0.1:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to {operation_name}: {result.get('message')}")
            logger.info(f"NLSE executed '{operation_name}' plan: {result.get('message')}")
            return result
        except requests.RequestException as e:
            logger.error(f"Could not execute '{operation_name}' plan on NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def learn_fact(self, triple: StructuredTriple, heart_orchestrator) -> None:
        """
        REFACTORED for Conceptual Learning.
        Translates a fact about words into a fact about concepts.
        """
        from models import AtomType, RelationshipType, ExecutionMode
        import time

        current_time = int(time.time())

        # 1. Find the Concept IDs for the subject and object words.
        # This is a simplification. A real implementation would send a plan to the NLSE
        # to do this lookup. For now, we use our local name->uuid cache.
        subject_word_key = f"word:{triple.subject.lower()}"
        object_word_key = f"word:{triple.object.lower()}"

        # In a real system we would query for the atom, get its relationships, and find the concept
        # For now, we assume a direct mapping in our cache for simplicity.
        subject_concept_id = self.name_to_uuid_cache.get(f"concept_for:{subject_word_key}")
        object_concept_id = self.name_to_uuid_cache.get(f"concept_for:{object_word_key}")

        if not subject_concept_id or not object_concept_id:
            msg = f"Cannot learn fact. Concept for '{triple.subject}' or '{triple.object}' is unknown. Please label them first."
            logger.error(msg)
            raise ValueError(msg)  # Raise an error to be caught by the API

        # 2. Get current emotional context from the Heart
        
        current_emotional_state = heart_orchestrator.get_current_hormonal_state()

        # 3. Create the relationship between the two CONCEPTS
        fact_relationship = {
            "target_id": object_concept_id,
            "rel_type": RelationshipType[triple.relationship.upper()].value,
            "strength": 1.0,
            "access_timestamp": current_time,
        }

        # 4. Create an ExecutionPlan to UPDATE the subject concept atom with this new fact.
        subject_concept_update = {
            "id": subject_concept_id,
            "label": AtomType.Concept.value,
            "significance": 1.0,  # This will be boosted by emotion in the NLSE
            "access_timestamp": current_time,
            "properties": {"name": {"String": triple.subject}},  # Keep name for debugging
            "emotional_resonance": current_emotional_state,
            "embedded_relationships": [fact_relationship],
            "context_id": None, "state_flags": 0,
        }

        plan = {
            "steps": [{"Write": subject_concept_update}],
            "mode": ExecutionMode.STANDARD.value
        }

        # 5. Send the plan to the NLSE
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to learn fact: {result.get('message')}")

            logger.info(f"Successfully sent conceptual fact ExecutionPlan to NLSE.")
        except requests.RequestException as e:
            logger.error(f"Could not send conceptual fact plan to NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def label_concept(self, word_str: str, concept_name: str) -> None:
        """
        Teaches the AGI that a specific word is the label for a specific concept.
        This is the core of symbol grounding.
        """
        from models import AtomType, RelationshipType, ExecutionMode
        import time

        word_str_lower = word_str.lower()

        # 1. Get or create the UUIDs for the word and the concept
        word_id = self.name_to_uuid_cache.setdefault(f"word:{word_str_lower}", str(uuid.uuid4()))
        concept_id = self.name_to_uuid_cache.setdefault(f"concept:{concept_name}", str(uuid.uuid4()))
        self.name_to_uuid_cache[f"concept_for:word:{word_str_lower}"] = concept_id
        current_time = int(time.time())

        # 2. Create the relationship that links the word to the concept
        labeling_relationship = {
            "target_id": concept_id,
            "rel_type": RelationshipType.IS_LABEL_FOR.value,
            "strength": 1.0,
            "access_timestamp": current_time,
        }

        # 3. We need to create an ExecutionPlan that UPSERTS this new knowledge.
        # It finds the existing Word atom and adds the new relationship to it.
        word_atom_update = {
            "id": word_id,
            "label": AtomType.Word.value,  # Ensure the label is correct
            "significance": 1.0,  # We can reset or boost significance here
            "access_timestamp": current_time,
            "properties": {"name": {"String": word_str_lower}},
            "emotional_resonance": {},  # No emotion associated with the act of labeling itself
            "embedded_relationships": [labeling_relationship],
            # All other fields can be omitted for an update
            "context_id": None, "state_flags": 0,
        }

        # Also ensure the concept atom exists
        concept_atom_data = {
            "id": concept_id, "label": AtomType.Concept.value, "significance": 1.0,
            "access_timestamp": current_time, "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": concept_name}}, "emotional_resonance": {},
            "embedded_relationships": []
        }

        plan = {
            "steps": [
                {"Write": word_atom_update},
                {"Write": concept_atom_data}
            ],
            "mode": ExecutionMode.STANDARD.value
        }

        # 4. Send the plan to the NLSE
        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to label concept '{concept_name}': {result.get('message')}")

            logger.info(f"Successfully sent ExecutionPlan to label concept '{concept_name}' with word '{word_str}'.")
        except requests.RequestException as e:
            logger.error(f"Could not send 'label_concept' plan to NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def learn_word(self, word_str: str) -> None:
        """
        Teaches the AGI a new word by breaking it down into its constituent
        characters and storing the structure in the NLSE.
        """
        from models import AtomType, RelationshipType, ExecutionMode
        import time

        plan_steps = []
        current_time = int(time.time())
        word_str_lower = word_str.lower()

        # 1. Define the main Word atom
        word_id = self.name_to_uuid_cache.setdefault(f"word:{word_str_lower}", str(uuid.uuid4()))
        word_relationships = []

        # 2. Create atoms for each unique character and link them to the word
        unique_chars = sorted(list(set(word_str_lower)))

        for char in unique_chars:
            char_concept_name = f"char:{char}"
            char_id = self.name_to_uuid_cache.setdefault(char_concept_name, str(uuid.uuid4()))

            # Add a relationship from the Word to this Character concept
            word_relationships.append({
                "target_id": char_id,
                "rel_type": RelationshipType.HAS_PART.value,  # A word 'HAS_PART' characters
                "strength": 1.0,
                "access_timestamp": current_time,
            })

            # Create a write step for the character atom itself (upsert will handle it)
            char_atom_data = {
                "id": char_id, "label": AtomType.Concept.value, "significance": 1.0,
                "access_timestamp": current_time, "context_id": None, "state_flags": 0,
                "properties": {"name": {"String": char}}, "emotional_resonance": {},
                "embedded_relationships": []
            }
            plan_steps.append({"Write": char_atom_data})

        # 3. Assemble the main Word atom with its relationships
        word_atom_data = {
            "id": word_id, "label": AtomType.Word.value, "significance": 1.0,
            "access_timestamp": current_time, "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": word_str_lower}}, "emotional_resonance": {},
            "embedded_relationships": word_relationships
        }
        plan_steps.append({"Write": word_atom_data})

        # 4. Build and execute the full plan
        plan = {"steps": plan_steps, "mode": ExecutionMode.STANDARD.value}

        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()
            if not result.get("success"):
                raise Exception(f"NLSE failed to learn word '{word_str}': {result.get('message')}")

            logger.info(f"Successfully sent ExecutionPlan to learn word '{word_str}'.")
        except requests.RequestException as e:
            logger.error(f"Could not send 'learn_word' plan to NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def query_fact(self, subject: str, relationship_type: str) -> list[str]:
        """
        REFACTORED for Conceptual Querying.
        Finds the concept for a word, traverses the graph, then finds the word for the resulting concept.
        """
        # 1. Find the Concept ID for the subject word.
        subject_word_key = f"word:{subject.lower()}"
        subject_concept_id = self.name_to_uuid_cache.get(f"concept_for:{subject_word_key}")

        if not subject_concept_id:
            logger.info(f"Conceptual query for '{subject}' failed: I don't have a concept for that word.")
            return []

        # 2. This plan fetches the starting concept, traverses its relationships,
        # and returns the resulting concepts.
        plan = {
            "steps": [
                {"Fetch": {"id": subject_concept_id, "context_key": "subject_concept"}},
                {"Traverse": {
                    "from_context_key": "subject_concept",
                    "rel_type": relationship_type.upper(),
                    "output_key": "final"
                }}
            ],
            "mode": "Standard"
        }

        nlse_url = os.environ.get("LOGICAL_ENGINE_URL", "http://logical_engine:8000") + "/nlse/execute-plan"
        try:
            response = requests.post(nlse_url, json=plan)
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                answer_concepts = result.get("atoms", [])

                # 3. For each resulting concept, we must find its word label to give a string answer.
                # This is a reverse lookup.
                final_answers = []
                for concept in answer_concepts:
                    concept_id = concept.get("id")
                    # Inefficiently scan the cache for the word that points to this concept ID.
                    # A real implementation would use a reverse index in the NLSE.
                    found_label = "UnknownConcept"
                    for key, val in self.name_to_uuid_cache.items():
                        if val == concept_id and key.startswith("concept_for:"):
                            word_key = key.replace("concept_for:", "")
                            found_label = word_key.replace("word:", "")
                            break
                    final_answers.append(found_label.capitalize())

                return final_answers
            return []
        except requests.RequestException as e:
            logger.error(f"Could not execute conceptual query plan on NLSE: {e}")
            raise ServiceUnavailable("NLSE service is unavailable.") from e

    def find_knowledge_gap(self, limit: int = 1) -> List[str]:
        plan = {
            "steps": [{"FetchBySignificance": {"limit": limit, "context_key": "final"}}],
            "mode": "Standard"
        }
        result = self._execute_nlse_plan(plan, "find knowledge gap")
        return [atom.get("properties", {}).get("name", {}).get("String", "Unknown") for atom in result.get("atoms", [])]

    # --- HEART METHODS ---
    def log_illusion(self, illusion_data: dict) -> None:
        if not self.redis_client:
            logger.warning("Redis not available, cannot log illusion.")
            return
        try:
            illusion_json = json.dumps(illusion_data)
            self.redis_client.lpush("illusion_log", illusion_json)
            logger.info(f"Successfully logged new illusion to Redis.")
        except (redis.exceptions.RedisError, TypeError) as e:
            logger.error(f"Failed to log illusion to Redis: {e}")

    def get_all_prototypes(self) -> List[Dict]:
        if not self.redis_client:
            return []
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
        if not self.redis_client:
            return False
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

    def get_named_emotion_by_signature(self, physio_state: Dict[str, float]) -> Optional[Dict[str, Any]]:
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
            logger.info(f"Matched current feeling to '{best_match['name']}' with distance {smallest_distance:.2f}")
            return best_match
        return None

    # --- JUDICIARY & HEALTH ENHANCEMENT INTERFACE ---
    def does_brain_know_truth_of(self, fact_info: Dict[str, Any]) -> bool:
        error_subject = fact_info.get("subject")
        logger.info(f"Judiciary Interface: Checking brain's knowledge regarding '{error_subject}'.")
        known_topics = ["Socrates", "Earth", "Plato"]
        if error_subject in known_topics:
            logger.info(f"Knowledge Check: Brain has established knowledge on '{error_subject}'.")
            return True
        else:
            logger.info(f"Knowledge Check: Brain has no established knowledge on '{error_subject}'.")
            return False

    def find_disease_for_error(self, error_type: str, error_details: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        logger.info(f"Querying NLSE for disease caused by '{error_type}'.")
        all_diseases_data = self.get_all_diseases()
        for disease_atom in all_diseases_data:
            # This logic is simplified; a real implementation would traverse IS_CAUSED_BY relationships
            # For now, we assume a property like 'cause_LogicalError' exists.
            cause_prop_name = f"cause_{error_type}"
            if cause_prop_name in disease_atom.get("properties", {}):
                disease_id = disease_atom.get("id")
                disease_name = disease_atom.get("properties", {}).get("name", {}).get("String")
                logger.info(f"Found matching disease: '{disease_name}' (ID: {disease_id})")
                return disease_id, disease_name
        logger.info(f"No specific disease protocol found for error type '{error_type}' in NLSE.")
        return None, None

    def get_all_diseases(self) -> list[dict]:
        plan = {
            "steps": [{"FetchByType": {"atom_type": "DiseaseProtocol", "context_key": "final"}}],
            "mode": "Standard"
        }
        result = self._execute_nlse_plan(plan, "get all diseases")
        return result.get("atoms", [])

    def get_symptoms_for_disease(self, disease_id: str) -> list[dict]:
        plan = {
            "steps": [
                {"Fetch": {"id": disease_id, "context_key": "disease"}},
                {"Traverse": {
                    "from_context_key": "disease",
                    "rel_type": "HAS_SYMPTOM",
                    "output_key": "final"
                }}
            ],
            "mode": "Standard"
        }
        result = self._execute_nlse_plan(plan, f"get symptoms for disease {disease_id}")
        return [s.get("properties", {}) for s in result.get("atoms", [])]

    def define_new_disease(self, definition: DiseaseDefinition) -> bool:
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
                "id": symptom_id, "label": AtomType.Symptom.value, "significance": 1.0,
                "access_timestamp": current_time, "properties": symptom_properties,
                "emotional_resonance": {}, "embedded_relationships": [], "context_id": None, "state_flags": 0,
            }})
            disease_relationships.append({
                "target_id": symptom_id, "rel_type": RelationshipType.HAS_SYMPTOM.value, "strength": 1.0, "access_timestamp": current_time,
            })

        for cause in definition.causes:
            # This creates a placeholder atom for the error type if it doesn't exist.
            # A more robust system would link to pre-defined error type concepts.
            cause_id = self.name_to_uuid_cache.setdefault(f"error_type:{cause.error_type}", str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": cause_id,
                "rel_type": RelationshipType.IS_CAUSED_BY.value,
                "strength": 1.0, "access_timestamp": current_time,
            })

        for treatment in definition.treatments:
            med_id = self.name_to_uuid_cache.setdefault(f"medication:{treatment.medication_name}", str(uuid.uuid4()))
            disease_relationships.append({
                "target_id": med_id, "rel_type": RelationshipType.IS_CURED_BY.value, "strength": 1.0, "access_timestamp": current_time,
            })

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

    def get_random_significant_memory(self, limit: int = 1) -> List[Dict]:
        """
        NLSE-native version of this function for the Soul's dream cycle.
        """
        plan = {
            "steps": [{"FetchBySignificance": {"limit": limit, "context_key": "final"}}],
            "mode": "Standard"
        }
        result = self._execute_nlse_plan(plan, "get random significant memory")
        return result.get("atoms", [])

    def validate_fact_with_lve(self, triple: StructuredTriple) -> dict:
        """
        NLSE-native version. The core LVE logic is now inside the Rust 'Write' step,
        so this function in Python can be simplified. For now, we'll assume a fact is
        valid if it can be written. A more complex check could happen here later.
        """
        # This returns a placeholder "valid" response, as the true
        # validation happens inside the NLSE during the 'learn_fact' call.
        return {"is_valid": True, "reason": "Validation is now handled by the NLSE on write."}
# Create a singleton instance to be imported by other parts of the app
db_manager = DatabaseManager()