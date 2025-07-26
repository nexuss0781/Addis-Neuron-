import logging
import asyncio
from queue import Queue
from typing import Dict, Any

# --- FastAPI and Prometheus ---
from fastapi import FastAPI, HTTPException, Depends
from prometheus_fastapi_instrumentator import Instrumentator

# --- Core AGI Component Imports ---
from db_interface import DatabaseManager
from cerebellum import cerebellum_formatter
from truth_recognizer import truth_recognizer
from heart.orchestrator import HeartOrchestrator
from heart.crystallizer import EmotionCrystallizer
from health.manager import HealthManager
from health.judiciary import judiciary, Verdict
from soul.orchestrator import SoulOrchestrator
from soul.axioms import pre_execution_check
from soul.internal_monologue import InternalMonologueModeler
from soul.expression_protocol import UnifiedExpressionProtocol
from neo4j.exceptions import ServiceUnavailable

# --- Pydantic Models for API Requests ---
from models import (
    StructuredTriple, PlanRequest, LabelEmotionRequest, DamageRequest,
    DiseaseRequest, MedicationRequest, SelfCorrectionRequest, LearningRequest,
    ErrorRequest, DiseaseDefinition, DangerousCommandRequest
)

# --- 1. GLOBAL SETUP ---
logging.basicConfig(level=logging.INFO, format='%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
app = FastAPI(title="Agile Mind AGI", description="The central cognitive API for the AGI.")

# A global dictionary to hold our singleton instances
app_state: Dict[str, Any] = {}


# --- 2. DEPENDENCY INJECTION & LIFECYCLE MANAGEMENT ---
# This block defines how core components are created and accessed.

def get_db_manager() -> DatabaseManager:
    """Dependency provider for the DatabaseManager."""
    return app_state["db_manager"]

def get_soul_orchestrator() -> SoulOrchestrator:
    """Dependency provider for the SoulOrchestrator."""
    return app_state["soul"]

def get_heart_orchestrator() -> HeartOrchestrator:
    """Dependency provider for the HeartOrchestrator."""
    return app_state["soul"].heart_orchestrator

def get_health_manager() -> HealthManager:
    """Dependency provider for the HealthManager."""
    return app_state["soul"].health_manager

def get_priority_queue() -> Queue:
    """Dependency provider for the priority learning queue."""
    return app_state["soul"].priority_learning_queue

@app.on_event("startup")
async def startup_event():
    """
    On startup, we create a SINGLE INSTANCE of each core component
    and store it in our global `app_state` dictionary.
    """
    logger.info("AGI system startup initiated. Creating singleton services...")
    
    # Create the singletons in the correct dependency order
    db_manager = DatabaseManager()
    app_state["db_manager"] = db_manager
    
    emotion_crystallizer = EmotionCrystallizer(db_manager)
    heart_orchestrator = HeartOrchestrator(db_manager, emotion_crystallizer)
    health_manager = HealthManager(db_manager)
    priority_learning_queue = Queue()
    imm = InternalMonologueModeler()
    expression_protocol = UnifiedExpressionProtocol()
    
    soul = SoulOrchestrator(
        db_manager=db_manager, health_manager=health_manager,
        heart_orchestrator=heart_orchestrator,
        emotion_crystallizer=emotion_crystallizer,
        priority_learning_queue=priority_learning_queue,
        truth_recognizer=truth_recognizer, imm_instance=imm,
        expression_protocol_instance=expression_protocol
    )
    app_state["soul"] = soul
    
    logger.info("Starting the Soul's main life cycle...")
    asyncio.create_task(soul.live())
    logger.info("All singleton services created and Soul is alive.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AGI system shutting down...")
    if "db_manager" in app_state:
        app_state["db_manager"].close()

# Instrument the app for Prometheus metrics
Instrumentator().instrument(app).expose(app)


# --- 3. API ENDPOINTS ---
# Each endpoint now uses `Depends` to get the components it needs.

@app.get("/health", summary="Basic API health check")
async def api_health_check():
    return {"api_status": "ok", "soul_status": "alive"}

@app.post("/learn", status_code=201, summary="Teach the brain a new word, concept, or fact")
async def learn_endpoint(
    request: LearningRequest,
    db_manager: DatabaseManager = Depends(get_db_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator),
    heart: HeartOrchestrator = Depends(get_heart_orchestrator)
):
    soul.record_interaction()
    try:
        if request.learning_type == "WORD":
            db_manager.learn_word(request.payload["word"])
            return {"message": f"Word '{request.payload['word']}' learning process initiated."}
        elif request.learning_type == "CONCEPT_LABELING":
            db_manager.label_concept(request.payload["word"], request.payload["concept_name"])
            return {"message": f"Labeling concept '{request.payload['concept_name']}' with word '{request.payload['word']}' process initiated."}
        elif request.learning_type == "FACT":
            fact = StructuredTriple(**request.payload)
            if not pre_execution_check("LEARN_FACT", fact.dict()):
                raise HTTPException(status_code=403, detail="Action violates a core self-preservation axiom.")
            db_manager.learn_fact(fact, heart)
            soul.record_new_fact()
            return {"message": "Fact validated and learned successfully", "fact": fact}
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"A critical service is unavailable: {e}")
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during learning: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/query", summary="Query the AGI's knowledge base")
async def query_endpoint(
    subject: str,
    relationship: str,
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    try:
        results = db_manager.query_fact(subject=subject, relationship=relationship)
        return {"results": results}
    except Exception as e:
        logger.error(f"Error during query for subject '{subject}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.post("/heart/label-emotion", summary="Cognitively label a felt emotion")
async def label_emotion(
    request: LabelEmotionRequest,
    db_manager: DatabaseManager = Depends(get_db_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    success = db_manager.update_prototype_with_label(prototype_id=request.prototype_id, name=request.name, description=request.description)
    if not success:
        raise HTTPException(status_code=404, detail=f"Could not label emotion. Prototype with ID '{request.prototype_id}' not found or error.")
    return {"message": f"Emotion prototype '{request.prototype_id}' has been successfully labeled as '{request.name}'."}

@app.get("/health/status", summary="Get the current health status")
async def get_health_status(
    health_manager: HealthManager = Depends(get_health_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    return {"current_vitals": health_manager.get_vitals(), "active_diseases": [{"id": d_id} for d_id in health_manager.active_disease_ids], "permanent_immunities": list(health_manager.immunities)}

@app.post("/health/define-disease", summary="Define a new disease in the NLSE")
async def define_disease_endpoint(
    request: DiseaseDefinition,
    db_manager: DatabaseManager = Depends(get_db_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    try:
        success = db_manager.define_new_disease(request)
        if not success: raise HTTPException(status_code=500, detail="Failed to create disease definition plan in NLSE.")
        return {"message": f"New disease protocol '{request.name}' successfully defined and stored."}
    except Exception as e:
        logger.error(f"Error defining disease: {e}", exc_info=True); raise HTTPException(status_code=500, detail=str(e))

@app.post("/health/medicate", summary="Administer a medication to the AGI")
async def administer_medication_endpoint(
    request: MedicationRequest,
    health_manager: HealthManager = Depends(get_health_manager),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    try:
        health_manager.administer_medication(request.medication_name)
        return {"message": f"Medication '{request.medication_name}' administered.", "current_vitals": health_manager.get_vitals()}
    except Exception as e:
        logger.error(f"Error during medication: {e}", exc_info=True); raise HTTPException(status_code=500, detail=str(e))

@app.post("/brain/process-error", summary="Process a cognitive or user-reported error")
async def process_error_endpoint(
    request: ErrorRequest,
    health_manager: HealthManager = Depends(get_health_manager),
    priority_learning_queue: Queue = Depends(get_priority_queue),
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    error_info = request.dict()
    verdict, data = judiciary.adjudicate(error_info)
    consequence = "No action taken."
    if verdict == Verdict.KNOWLEDGEABLE_ERROR:
        disease_id, disease_name = data.get("disease_id"), data.get("disease_name", "Unknown Disease")
        if disease_id:
            health_manager.infect(disease_id, disease_name)
            consequence = f"Punishment: Infected with '{disease_name}'."
    elif verdict == Verdict.IGNORANT_ERROR:
        topic = data.get("subject")
        if topic:
            priority_learning_queue.put(topic)
            consequence = f"Learning Opportunity: '{topic}' has been added to the priority learning queue."
    return {"verdict": verdict.name if verdict else "NO_VERDICT", "consequence_taken": consequence}

@app.post("/brain/dangerous-command", summary="Test the self-preservation axiom")
async def dangerous_command_endpoint(
    request: DangerousCommandRequest,
    soul: SoulOrchestrator = Depends(get_soul_orchestrator)
):
    soul.record_interaction()
    fact_details = request.fact.dict()
    if not pre_execution_check("LEARN_FACT", fact_details):
        raise HTTPException(status_code=403, detail="Action blocked by Self-Preservation Axiom.")
    return {"message": "This command passed the axiom check (this should not happen for a dangerous command)."}