import logging
import asyncio
import requests
from requests.exceptions import RequestException

from fastapi import FastAPI, HTTPException
from neo4j.exceptions import ServiceUnavailable
from prometheus_fastapi_instrumentator import Instrumentator

# Import our custom modules
from models import StructuredTriple, PlanRequest
from db_interface import db_manager
from cerebellum import cerebellum_formatter
from truth_recognizer import truth_recognizer


# --- 1. SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the main FastAPI application instance
app = FastAPI(title="Brain Orchestrator")

# Correctly instrument the app for Prometheus metrics BEFORE startup events
Instrumentator().instrument(app).expose(app)

# Define constants
LOGICAL_ENGINE_URL = "http://logical_engine:8000"


# --- 2. BACKGROUND TASKS (AUTONOMOUS PROCESSES) ---

async def forgetting_cycle():
    """Microglia: Periodically prunes weak memories."""
    while True:
        await asyncio.sleep(60) # Using 60s for testing
        logger.info("Microglia: Running periodic forgetting cycle.")
        try:
            db_manager.prune_weak_facts(significance_threshold=0.0)
        except Exception as e:
            logger.error(f"Forgetting cycle failed with an unexpected error: {e}")

async def curiosity_loop():
    """PFC: Proactively finds and fills knowledge gaps."""
    await asyncio.sleep(30) # Initial delay before first run
    while True:
        logger.info("CURIOSITY: Starting a new curiosity cycle.")
        topic_to_investigate = db_manager.find_knowledge_gap()

        if topic_to_investigate:
            new_triples = truth_recognizer.investigate(topic_to_investigate)
            if new_triples:
                logger.info(f"CURIOSITY: Found {len(new_triples)} new potential facts for '{topic_to_investigate}'.")
                facts_learned_count = 0
                for triple in new_triples:
                    try:
                        validation_result = db_manager.validate_fact_with_lve(triple)
                        if validation_result.get("is_valid", False):
                            db_manager.learn_fact(triple)
                            facts_learned_count += 1
                        else:
                             logger.warning(f"CURIOSITY: LVE rejected new fact: {validation_result.get('reason')}")
                    except Exception as e:
                        logger.error(f"CURIOSITY: Error while learning new fact '{triple}': {e}")
                logger.info(f"CURIOSITY: Successfully learned {facts_learned_count} new facts.")
        
        await asyncio.sleep(300) # Wait 5 minutes before next cycle


# --- 3. APP LIFECYCLE EVENTS ---

@app.on_event("startup")
async def startup_event():
    logger.info("Brain Orchestrator starting up...")
    # Launch all autonomous background tasks
    asyncio.create_task(forgetting_cycle())
    asyncio.create_task(curiosity_loop())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Brain Orchestrator shutting down...")
    db_manager.close()


# --- 4. API ENDPOINTS ---

@app.get("/health", summary="Check API health")
async def health_check():
    """Provides a basic health check of the API."""
    return {"api_status": "ok"}

@app.get("/test_integration", summary="Test full system connectivity")
async def test_integration():
    """Performs a full system smoke test."""
    logger.info("Performing full integration test...")
    db_status = db_manager.ping_databases()
    try:
        response = requests.get(f"{LOGICAL_ENGINE_URL}/health", timeout=5)
        response.raise_for_status()
        rust_service_status = response.json()
    except RequestException as e:
        raise HTTPException(status_code=503, detail=f"Failed to connect to logical_engine: {e}")

    return {
        "message": "Full system integration test successful!",
        "orchestrator_database_status": db_status,
        "logical_engine_status": rust_service_status,
    }

@app.post("/learn", status_code=201, summary="Teach the brain a new fact")
async def learn_fact_endpoint(triple: StructuredTriple):
    """Thalamus: Validates and learns a new structured fact."""
    try:
        validation_result = db_manager.validate_fact_with_lve(triple)
        if not validation_result.get("is_valid", False):
            raise HTTPException(status_code=409, detail=f"Fact is logically inconsistent. Reason: {validation_result.get('reason', 'Unknown')}")
        db_manager.learn_fact(triple)
        return {"message": "Fact validated and learned successfully", "fact": triple}
    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Database service is unavailable. Could not learn fact. Reason: {e}")
    except HTTPException as e:
        raise e # Re-raise known HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/query", summary="Ask the brain a question")
async def query_fact_endpoint(subject: str, relationship: str):
    """PFC & Cerebellum: Reasons over knowledge and formats a response."""
    try:
        results = db_manager.query_fact(subject=subject, relationship_type=relationship)
        formatted_response = cerebellum_formatter.format_query_results(subject, relationship, results)
        return {"query": {"subject": subject, "relationship": relationship}, "raw_results": results, "formatted_response": formatted_response}
    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Database service is unavailable. Could not query. Reason: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/plan", summary="Perform 'what-if' analysis")
async def plan_hypothetical_endpoint(request: PlanRequest):
    """PFC & HSM: Performs hypothetical reasoning."""
    try:
        context_data = db_manager.get_context_for_hsm(request.context_node_names)
        hsm_payload = {
            "base_nodes": context_data["base_nodes"],
            "base_relationships": context_data["base_relationships"],
            "hypothetical_relationships": [rel.dict() for rel in request.hypothetical_relationships],
            "query": request.query.dict()
        }
        logger.info(f"PFC: Consulting HSM with payload: {hsm_payload}")
        hsm_url = f"{LOGICAL_ENGINE_URL}/hypothesize"
        response = requests.post(hsm_url, json=hsm_payload, timeout=10)
        response.raise_for_status()
        return {"plan_result": response.json()}
    except (ServiceUnavailable, requests.RequestException) as e:
        raise HTTPException(status_code=503, detail=f"A dependent service is unavailable. Reason: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# 1. Pull latest changes

