from fastapi import FastAPI, HTTPException
import logging
import requests # Import requests library
from requests.exceptions import RequestException
from models import StructuredTriple # <-- ADD THIS LINE
from neo4j.exceptions import ServiceUnavailable # <-- ADD THIS LINE
# The other imports like FastAPI, requests, logging should already be there
from db_interface import db_manager

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI application instance
app = FastAPI(title="Brain Orchestrator")

LOGICAL_ENGINE_URL = "http://logical_engine:8000"


@app.on_event("startup")
async def startup_event():
    logger.info("Brain Orchestrator starting up...")
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
    Asks the brain a question by querying for relationships.
    This endpoint acts as the interface to the Prefrontal Cortex.
    Example: /query?subject=Socrates&relationship=IS_A
    """
    try:
        results = db_manager.query_fact(subject=subject, relationship_type=relationship)
        if not results:
            return {"message": "No information found for this query."}
        return {"subject": subject, "relationship": relationship, "results": results}
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


