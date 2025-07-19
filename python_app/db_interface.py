import os
import redis
from neo4j import GraphDatabase, Result
from neo4j.exceptions import ServiceUnavailable
import time
import logging

# Import the data model we will create next
# It's okay that it doesn't exist yet; this prepares the file.
from models import StructuredTriple

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
        Queries for facts related to a subject via a specific relationship type.
        This represents the PFC's ability to reason and retrieve knowledge.
        It performs transitive lookups (e.g., A is a B, B is a C -> A is a C).
        """
        if not self.neo4j_driver:
            raise Exception("Cannot query fact: Neo4j driver not available.")
        
        # Sanitize relationship type for the query
        rel_type = "".join(filter(str.isalnum, relationship_type.upper()))
        
        # The query uses `*` to find paths of any length (1 or more hops)
        query = (
            "MATCH (s:Concept {name: $subject_name})-[r:" + rel_type + "*]->(o:Concept) "
            "RETURN DISTINCT o.name AS object_name"
        )
        
        results = []
        with self.neo4j_driver.session() as session:
            result_cursor = session.run(
                query,
                subject_name=subject
            )
            results = [record["object_name"] for record in result_cursor]
            logger.info(
                f"PFC queried for '({subject})-[{rel_type}]->(?)' and found: {results}"
            )

        return results

    # --- NEW METHOD: Hippocampus "Write" Function ---
    def learn_fact(self, triple: StructuredTriple) -> None:
        """
        Learns a new fact by creating nodes and a relationship in Neo4j.
        This represents the Hippocampus function.
        """
        if not self.neo4j_driver:
            raise Exception("Cannot learn fact: Neo4j driver not available.")

        # Cypher query to find or create nodes (MERGE) and then create a relationship
        # Using parameters ($var) is the standard, secure way to pass data.
        # We ensure relationships are always uppercase and use valid characters.
        relationship_type = "".join(filter(str.isalnum, triple.relationship.upper()))

        query = (
            "MERGE (s:Concept {name: $subject_name}) "
            "MERGE (o:Concept {name: $object_name}) "
            "MERGE (s)-[r:" + relationship_type + "]->(o) "
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
                f"Hippocampus learned: ({triple.subject})-[{rel_type}]->({triple.object})"
            )

    def close(self):
        """Closes database connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("Neo4j connection closed.")
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis connection closed.")


# Create a singleton instance to be imported by other parts of the app
db_manager = DatabaseManager()
