from fastapi import FastAPI, HTTPException
import logging
import requests # Import requests library
from requests.exceptions import RequestException
from models import StructuredTriple # <-- ADD THIS LINE
from neo4j.exceptions import ServiceUnavailable # <-- ADD THIS LINE
import asyncio # <-- ADD THIS LINE
# The other imports like FastAPI, requests, logging should already be there
# The other imports like FastAPI, requests, logging should already be there
from models import StructuredTriple, PlanRequest # <-- UPDATE THIS LINE
from cerebellum import cerebellum_formatter # <-- ADD THIS LINE
# The other imports...
from db_interface import db_manager
from prometheus_fastapi_instrumentator import Instrumentator # <-- NEW IMPORT
from truth_recognizer import truth_recognizer # <-- ADD THIS LINE
# The other imports...


# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI application instance
app = FastAPI(title="Brain Orchestrator")

LOGICAL_ENGINE_URL = "http://logical_engine:8000"



async def forgetting_cycle():
    """
    The background task that periodically runs the Microglia's pruning function.
    """
    while True:
        # Wait for a set period, e.g., 1 hour. For testing, we can set it lower.
        # Using 60 seconds for demonstration purposes.
        await asyncio.sleep(60)
        logger.info("Microglia: Running periodic forgetting cycle.")
        try:
            db_manager.prune_weak_facts(significance_threshold=0.0)
        except Exception as e:
            # The function in db_manager already logs, but we can add more here if needed
            logger.error(f"Forgetting cycle failed with an unexpected error: {e}")

async def curiosity_loop():
    """
    The background task that represents the brain's curiosity. It finds
    knowledge gaps and tries to fill them by investigating topics online.
    """
    # Wait a moment on startup before the first run
    await asyncio.sleep(30)
    
    while True:
        logger.info("CURIOSITY: Starting a new curiosity cycle.")
        
        # 1. Introspect to find a knowledge gap
        topic_to_investigate = db_manager.find_knowledge_gap()

        if topic_to_investigate:
            # 2. Use the Truth Recognizer to investigate the topic
            new_triples = truth_recognizer.investigate(topic_to_investigate)

            if new_triples:
                logger.info(f"CURIOSITY: Found {len(new_triples)} new potential facts for '{topic_to_investigate}'. Attempting to learn.")
                
                # 3. Try to learn each new fact (this uses the existing /learn logic path)
                facts_learned_count = 0
                for triple in new_triples:
                    try:
                        # We are internally calling our own learning logic
                        validation_result = db_manager.validate_fact_with_lve(triple)
                        if validation_result.get("is_valid", False):
                            db_manager.learn_fact(triple)
                            facts_learned_count += 1
                        else:
                             logger.warning(f"CURIOSITY: LVE rejected new fact: {validation_result.get('reason')}")
                    except Exception as e:
                        logger.error(f"CURIOSITY: Error while learning new fact '{triple}': {e}")
                
                logger.info(f"CURIOSITY: Successfully learned {facts_learned_count} new facts.")
        
        # Wait a long time before the next cycle to avoid being too aggressive.
        # For testing, we can set this lower. Using 5 minutes for demonstration.
        await asyncio.sleep(300)

# --- NEW: Add this block right after the app is instantiated ---
@app.on_event("startup")
async def startup_event():
    # Expose default metrics like requests count, latency, etc.
    Instrumentator().instrument(app).expose(app)
    logger.info("Brain Orchestrator starting up...")
    
    # Launch background tasks
    asyncio.create_task(forgetting_cycle())
    asyncio.create_task(curiosity_loop()) # <-- ADD THIS LINE
    
@app.on_event("startup")
async def startup_event():
    logger.info("Brain Orchestrator starting up...")
    # Launch the forgetting cycle as a background task
    asyncio.create_task(forgetting_cycle())
    status = db_manager.ping_databases()
    logger.info(f"Initial DB Status on startup: {status}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Brain Orchestrator shutting down...")
    db_manager.close()


@app.get("/health")
async def health_check():
    """
    Provides a basic health check of the API.
    """
    return {"api_status": "ok"}


# NEW: The final validation endpoint for Phase 0
@app.get("/test_integration")
async def test_integration():
    """
    Performs a full system smoke test:
    1. Pings its own database connections (Neo4j, Redis).
    2. Makes an API call to the Rust logical_engine service.
    """
    logger.info("Performing full integration test...")
    
    # 1. Check local DB connections
    db_status = db_manager.ping_databases()
    
    # 2. Test connection to the Rust service
    rust_service_status = {}
    try:
        # The service name 'logical_engine' is used as the hostname,
        # thanks to Docker's internal DNS.
        response = requests.get(f"{LOGICAL_ENGINE_URL}/health", timeout=5)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        rust_service_status = response.json()
    except RequestException as e:
        logger.error(f"Could not connect to the Rust logical_engine: {e}")
        raise HTTPException(
            status_code=503, 
            detail={
                "error": "Failed to connect to logical_engine",
                "reason": str(e)
            }
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


    return {
        "message": "Full system integration test successful!",
        "orchestrator_database_status": db_status,
        "logical_engine_status": rust_service_status,
    }


# Future endpoints like /learn and /query will be added here
@app.post("/learn", status_code=201)
async def learn_fact(triple: StructuredTriple):
    """
    Receives a structured fact and commands the brain to learn it.
    This endpoint acts as the Thalamus.
    """
    try:
        db_manager.learn_fact(triple)
        return {
            "message": "Fact learned successfully",
            "fact": triple
        }
    except ServiceUnavailable as e:
        logger.error(f"DATABASE ERROR during learn: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database service is unavailable. Could not learn fact."
        )
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during learn: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.get("/query")
async def query_fact(subject: str, relationship: str):
    """
    Asks the brain a question.
    MODIFIED: The final result is now formatted by the Cerebellum.
    """
    try:
        # The db_manager call already handles caching and reinforcement
        results = db_manager.query_fact(subject=subject, relationship_type=relationship)
        
        # The Cerebellum now formulates the final response string
        formatted_response = cerebellum_formatter.format_query_results(
            subject, relationship, results
        )
        
        # The API returns the formatted sentence along with the raw data
        return {
            "query": {
                "subject": subject,
                "relationship": relationship
            },
            "raw_results": results,
            "formatted_response": formatted_response
        }
    except ServiceUnavailable as e:
        logger.error(f"DATABASE ERROR during query: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database service is unavailable. Could not perform query."
        )
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
        
@app.post("/plan")
async def plan_hypothetical(request: PlanRequest):
    """
    Allows the brain to perform "what-if" analysis.
    This endpoint represents the PFC using the HSM for strategic planning.
    """
    try:
        # 1. PFC gathers the current reality from the knowledge graph
        context_data = db_manager.get_context_for_hsm(request.context_node_names)

        # 2. Prepare the payload for the Rust HSM service
        hsm_payload = {
            "base_nodes": context_data["base_nodes"],
            "base_relationships": context_data["base_relationships"],
            "hypothetical_relationships": [rel.dict() for rel in request.hypothetical_relationships],
            "query": request.query.dict()
        }
        
        # 3. PFC consults the HSM with the combined model
        logger.info(f"PFC: Consulting HSM with payload: {hsm_payload}")
        hsm_url = f"{LOGICAL_ENGINE_URL}/hypothesize"
        response = requests.post(hsm_url, json=hsm_payload, timeout=10)
        response.raise_for_status()
        
        return {"plan_result": response.json()}

    except ServiceUnavailable as e:
        logger.error(f"DATABASE ERROR during planning: {e}")
        raise HTTPException(status_code=503, detail="Database service is unavailable for context gathering.")
    except requests.RequestException as e:
        logger.error(f"Could not connect to the HSM service: {e}")
        raise HTTPException(status_code=503, detail="Hypothetical State Modeler is unavailable.")
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during planning: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")