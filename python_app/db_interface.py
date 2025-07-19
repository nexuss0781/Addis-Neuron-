import os
import redis
from neo4j import GraphDatabase, Result
from neo4j.exceptions import ServiceUnavailable
import time
import logging
import json # <-- ADD THIS LINE
# The other imports...
# Import the data model we will create next
# It's okay that it doesn't exist yet; this prepares the file.
from models import StructuredTriple
import requests # <-- ADD THIS LINE
# The other imports...

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
        Queries for facts.
        MODIFIED: Implements caching (Basal Ganglia) by checking Redis first.
        It also still reinforces the path (Amygdala) on a cache miss.
        """
        if not self.redis_client:
            logger.warning("Redis not available, bypassing cache.")
            return self._query_neo4j_and_reinforce(subject, relationship_type)

        # 1. Basal Ganglia: Check for a "habitual" thought (cache hit)
        cache_key = f"query:{subject}:{relationship_type}"
        try:
            cached_result = self.redis_client.get(cache_key)
            if cached_result:
                logger.info(f"Basal Ganglia: Cache hit for '{cache_key}'. Returning cached result.")
                return json.loads(cached_result) # Deserialize string back to list
        except Exception as e:
            logger.error(f"Redis cache read failed for key '{cache_key}': {e}")
            # Fall through to Neo4j if cache fails

        # 2. PFC/Hippocampus: If no cache hit, query the long-term store
        logger.info(f"Basal Ganglia: Cache miss for '{cache_key}'. Querying Neo4j...")
        results = self._query_neo4j_and_reinforce(subject, relationship_type)

        # 3. Basal Ganglia: After a successful query, form a new "habit" (populate cache)
        if results and self.redis_client:
            try:
                # Serialize list to a JSON string and set with an expiration (e.g., 1 hour)
                self.redis_client.set(cache_key, json.dumps(results), ex=3600)
                logger.info(f"Basal Ganglia: Cached result for '{cache_key}'.")
            except Exception as e:
                logger.error(f"Redis cache write failed for key '{cache_key}': {e}")
        
        return results

    # --- NEW METHOD: Hippocampus "Validation Check" Function ---
    def validate_fact_with_lve(self, triple: StructuredTriple) -> dict:
        """
        Gathers context from Neo4j and sends a request to the Rust LVE
        to validate a new fact before it's learned.
        """
        if not self.neo4j_driver:
            raise ServiceUnavailable("Cannot validate fact: Neo4j driver not available.")

        # 1. Gather existing relationships for the subject from our knowledge graph.
        # This provides the context for the LVE to check against.
        query = (
            "MATCH (s:Concept {name: $subject_name})-[r]->(o:Concept) "
            "RETURN type(r) as rel_type, o.name as target_name"
        )
        existing_relationships = []
        with self.neo4j_driver.session() as session:
            result_cursor = session.run(query, subject_name=triple.subject)
            existing_relationships = [
                {"rel_type": record["rel_type"], "target_name": record["target_name"]}
                for record in result_cursor
            ]
        
        # 2. Construct the request payload for the LVE service.
        lve_payload = {
            "subject_name": triple.subject,
            "existing_relationships": existing_relationships,
            "proposed_relationship": {
                "rel_type": "".join(filter(str.isalnum, triple.relationship.upper())),
                "target_name": triple.object
            }
        }
        
        # 3. Call the external Rust LVE service.
        # Note: In a real production system, this URL would be in a config file.
        lve_url = "http://logical_engine:8000/validate"
        logger.info(f"Hippocampus: Consulting LVE for fact: {lve_payload}")
        try:
            response = requests.post(lve_url, json=lve_payload, timeout=5)
            response.raise_for_status() # Raise an exception for bad status codes
            validation_result = response.json()
            logger.info(f"LVE responded: {validation_result}")
            return validation_result
        except requests.RequestException as e:
            logger.error(f"Could not connect to the LVE service: {e}")
            # Fail "open" or "closed"? Let's fail closed for safety.
            # If we can't validate, we assume it's invalid.
            return {"isValid": False, "reason": "Failed to connect to Logic Validation Engine."}

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
        Learns a new fact by creating nodes and a relationship in Neo4j.
        MODIFIED: Now sets/updates a 'significance' score.
        """
        if not self.neo4j_driver:
            raise Exception("Cannot learn fact: Neo4j driver not available.")

        relationship_type = "".join(filter(str.isalnum, triple.relationship.upper()))

        # MERGE finds or creates the full path.
        # ON CREATE SET initializes properties only for new relationships.
        # ON MATCH SET updates properties for existing relationships.
        query = (
            "MERGE (s:Concept {name: $subject_name}) "
            "MERGE (o:Concept {name: $object_name}) "
            "MERGE (s)-[r:" + relationship_type + "]->(o) "
            "ON CREATE SET r.significance = 1.0, r.last_accessed = timestamp() "
            "ON MATCH SET r.significance = r.significance + 0.1 " # Reinforce existing knowledge
            "RETURN type(r)"
        )

        with self.neo4j_driver.session() as session:
            result = session.run(
                query,
                subject_name=triple.subject,
                object_name=triple.object,
            )
            rel_type = result.single()[0] if result.peek() else "None"
            logger.info(
                f"Hippocampus learned/reinforced: ({triple.subject})-[{rel_type}]->({triple.object})"
            )
    def close(self):
        """Closes database connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("Neo4j connection closed.")
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis connection closed.")

    # --- NEW METHOD: PFC "Introspection" for Curiosity ---
    def find_knowledge_gap(self) -> Optional[str]:
        """
        Finds a concept in the knowledge graph that is poorly understood
        (i.e., has very few relationships) to trigger curiosity.
        This represents a form of PFC-driven introspection.
        """
        if not self.neo4j_driver:
            return None
        
        # A "leaf node" is a good candidate for a knowledge gap.
        # This query finds a concept with exactly one relationship.
        # It's a simple but effective way to find topics to expand on.
        query = (
            "MATCH (c:Concept) "
            "WITH c, size((c)--()) AS degree "
            "WHERE degree = 1 "
            "RETURN c.name AS topic "
            "LIMIT 1"
        )
        
        with self.neo4j_driver.session() as session:
            result = session.run(query).single()
            if result:
                topic = result["topic"]
                logger.info(f"PFC Introspection: Identified knowledge gap for topic '{topic}'.")
                return topic
        
        logger.info("PFC Introspection: No specific knowledge gaps found at this time.")
        return None

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
