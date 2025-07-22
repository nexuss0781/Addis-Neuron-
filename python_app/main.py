import logging
import asyncio
import requests
from requests.exceptions import RequestException
from queue import Queue # For priority_learning_queue

# --- FastAPI and Prometheus ---
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator # For metrics

# --- Core AGI Component Imports ---
# Central DB Manager
from db_interface import db_manager

# Brain
from cerebellum import cerebellum_formatter
from truth_recognizer import truth_recognizer

# Heart
from heart.orchestrator import HeartOrchestrator
from heart.crystallizer import EmotionCrystallizer

# Health
from health.manager import HealthManager
from health.pathogens import get_disease_by_name # Used by process_error_endpoint
from health.judiciary import judiciary, Verdict

# Soul (NEW MASTER ORCHESTRATOR)
from soul.orchestrator import SoulOrchestrator
from soul.axioms import pre_execution_check # For self-preservation checks

# --- Pydantic Models for API Requests ---
from models import (
    StructuredTriple,
    PlanRequest,
    LabelEmotionRequest,
    DamageRequest,
    DiseaseRequest,
    MedicationRequest,
    SelfCorrectionRequest, # Corrected: SelfCorrectionRequ to SelfCorrectionRequest
    ErrorRequest,
    DiseaseDefinition,
    DangerousCommandRequest # For testing self-preservation
)


# --- 1. GLOBAL SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the main FastAPI application instance
app = FastAPI(title="Agile Mind AGI")

# --- Initialize Global Components (Singletons) ---
# These are the "body parts" of the AGI
health_manager = HealthManager()
heart_orchestrator = HeartOrchestrator(db_manager)
emotion_crystallizer = EmotionCrystallizer(db_manager)

# A thread-safe queue for high-priority learning targets from the Judiciary
priority_learning_queue = Queue()

# The AGI's private internal mind
from soul.internal_monologue import InternalMonologueModeler # Import here to avoid circular dep with SoulOrchestrator
imm = InternalMonologueModeler()

# The AGI's voice
from soul.expression_protocol import UnifiedExpressionProtocol # Import here to avoid circular dep with SoulOrchestrator
expression_protocol = UnifiedExpressionProtocol()

# The Soul Orchestrator is the conductor of the entire system
soul = SoulOrchestrator(
    db_manager=db_manager,
    health_manager=health_manager,
    heart_orchestrator=heart_orchestrator,
    emotion_crystallizer=emotion_crystallizer,
    priority_learning_queue=priority_learning_queue,
    truth_recognizer=truth_recognizer,
    imm_instance=imm, # Pass the IMM instance
    expression_protocol_instance=expression_protocol # Pass the Expression Protocol instance
)


# Correctly instrument the app for Prometheus metrics BEFORE startup events
Instrumentator().instrument(app).expose(app)

# Define constants
LOGICAL_ENGINE_URL = "http://logical_engine:8000"


# --- 2. APP LIFECYCLE EVENTS ---

@app.on_event("startup")
async def startup_event():
    """
    On startup, the only thing we do is launch the Soul's main life cycle.
    All other background tasks are now managed internally by the Soul.
    """
    logger.info("AGI system startup initiated. Starting the Soul...")
    asyncio.create_task(soul.live())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AGI system shutting down...")
    db_manager.close()


# --- 3. API ENDPOINTS ---
# These endpoints are the AGI's interface to the external world.
# They mostly delegate to the core components and record interaction.

@app.get("/health", summary="Basic API health check")
async def api_health_check():
    """Provides a basic health check of the API."""
    return {"api_status": "ok", "soul_status": "alive"}

@app.get("/test_integration", summary="Test full system connectivity")
async def test_integration():
    """Performs a full system smoke test."""
    soul.record_interaction() # Record interaction
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
    soul.record_interaction() # Record interaction

    # --- SOUL: Self-Preservation Axiom Check ---
    if not pre_execution_check("LEARN_FACT", triple.dict()):
        raise HTTPException(status_code=403, detail="Action blocked by Self-Preservation Axiom.")
        
    try:
        db_manager.learn_fact(triple)
        soul.record_new_fact() # Record that new knowledge was acquired
        return {"message": "Fact validated and learned successfully", "fact": triple}
    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Database service unavailable: {e}")
    except HTTPException as e:
        raise e # Re-raise known HTTP exceptions (e.g. from LVE validation)
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during learn: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/query", summary="Ask the brain a question")
async def query_fact_endpoint(subject: str, relationship: str):
    """
    The final, complete query pipeline:
    1. Records interaction with the Soul.
    2. Gets raw logic from the Brain/NLSE.
    3. Synthesizes an internal thought in the IMM.
    4. Generates a final, authentic response via the Expression Protocol.
    """
    soul.record_interaction()
    try:
        # Stage 1: Get raw logical output
        raw_results = db_manager.query_fact(subject=subject, relationship_type=relationship)
        raw_logical_output = {"subject": subject, "relationship": relationship, "results": raw_results}

        # Stage 2: Synthesize an internal thought/feeling (IMM)
        current_emotional_state = heart_orchestrator.get_current_hormonal_state()
        reflection = imm.synthesize(raw_logical_output, current_emotional_state)

        # Stage 3: Generate the final, public expression (Expression Protocol)
        # The SoulOrchestrator now holds the persona instance
        final_output = expression_protocol.generate_output(reflection, soul.persona) # Pass soul.persona
        
        # The API now returns a clean, simple response to the user.
        # The complex internal monologue is kept private.
        return {"response": final_output}

    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Database service unavailable: {e}")
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/plan", summary="Perform 'what-if' analysis")
async def plan_hypothetical_endpoint(request: PlanRequest):
    """PFC & HSM: Performs hypothetical reasoning."""
    soul.record_interaction() # Record interaction
    try:
        context_data = db_manager.get_context_for_hsm(request.context_node_names)
        hsm_payload = {
            "base_nodes": context_data["base_nodes"],
            "base_relationships": context_data["base_relationships"],
            "hypothetical_relationships": [rel.dict() for rel in request.hypothetical_relationships],
            "query": request.query.dict()
        }
        logger.info(f"PFC: Consulting HSM with payload: {hsm_payload}")
        hsm_url = f"{LOGICAL_ENGINE_URL}/nlse/execute-plan"
        response = requests.post(hsm_url, json=hsm_payload, timeout=10)
        response.raise_for_status()
        return {"plan_result": response.json()}
    except (ServiceUnavailable, requests.RequestException) as e:
        raise HTTPException(status_code=503, detail=f"A dependent service is unavailable. Reason: {e}")
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during planning: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/heart/trigger-event/{event_name}", summary="Trigger a primitive emotional event")
async def trigger_heart_event(event_name: str):
    """
    Triggers a primitive event in the Heart and returns the AI's
    resulting emotional expression, if any.
    """
    soul.record_interaction() # Record interaction
    valid_events = ["DEVELOPER_INTERACTION", "DATA_STARVATION", "SYSTEM_ERROR", "PRAISE"]
    if event_name not in valid_events:
        raise HTTPException(status_code=400, detail=f"Invalid event name. Use one of: {valid_events}")

    try:
        emotional_response = heart_orchestrator.process_event_and_get_response(event_name)

        return {
            "event_processed": event_name,
            "emotional_expression": emotional_response,
            "current_hormones": heart_orchestrator.hormonal_system.levels
        }
    except Exception as e:
        logger.error(f"Error in heart event processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the event: {str(e)}")

@app.post("/heart/label-emotion", summary="Cognitively label a felt emotion")
async def label_emotion(request: LabelEmotionRequest):
    """
    Connects an internal emotion prototype with a human-language label.
    """
    soul.record_interaction() # Record interaction
    success = db_manager.update_prototype_with_label(
        prototype_id=request.prototype_id,
        name=request.name,
        description=request.description
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Could not label emotion. Prototype with ID '{request.prototype_id}' not found or error."
        )
    return {"message": f"Emotion prototype '{request.prototype_id}' has been successfully labeled as '{request.name}'."}

@app.get("/health/status", summary="Get the current health status")
async def get_health_status():
    """Returns the current vitals and active diseases."""
    soul.record_interaction() # Record interaction
    return {
        "current_vitals": health_manager.get_vitals(),
        "active_diseases": [
            # For now, HealthManager stores IDs. This will improve with NLSE integration.
            {"id": d_id, "name": "Unknown Name (via ID)"} for d_id in health_manager.active_disease_ids
        ],
        "permanent_immunities": list(health_manager.immunities)
    }

@app.post("/health/define-disease", summary="Define a new disease in the NLSE")
async def define_disease_endpoint(request: DiseaseDefinition):
    """Allows a developer to dynamically add a new disease protocol to the AGI's memory."""
    soul.record_interaction() # Record interaction
    try:
        success = db_manager.define_new_disease(request)
        if not success:
             raise HTTPException(status_code=500, detail="Failed to create disease definition plan in NLSE.")
        return {"message": f"New disease protocol '{request.name}' successfully defined and stored."}
    except Exception as e:
        logger.error(f"Error defining disease: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/health/medicate", summary="Administer a medication to the AGI")
async def administer_medication_endpoint(request: MedicationRequest):
    """A test endpoint to administer a general medication from the pharmacy."""
    soul.record_interaction() # Record interaction
    try:
        health_manager.administer_medication(request.medication_name)
        return {
            "message": f"Medication '{request.medication_name}' administered.",
            "current_vitals": health_manager.get_vitals()
        }
    except Exception as e:
        logger.error(f"Error during medication: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/health/self-correct", summary="Simulate self-correction to cure a disease and vaccinate")
async def self_correct_endpoint(request: SelfCorrectionRequest):
    """
    A high-level test endpoint that simulates the AGI correcting a mistake.
    This administers the SelfCorrectionAntidote, curing the disease
    and providing permanent immunity (vaccination).
    """
    soul.record_interaction() # Record interaction
    try:
        health_manager.administer_medication(
            "SelfCorrectionAntidote",
            disease_id=request.disease_name # Passing disease_id here
        )
        return {
            "message": f"Self-correction process initiated for '{request.disease_name}'.",
            "current_vitals": health_manager.get_vitals(),
            "active_diseases": [d_id for d_id in health_manager.active_disease_ids],
            "permanent_immunities": list(health_manager.immunities)
        }
    except Exception as e:
        logger.error(f"Error during self-correction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- ERROR & CONSEQUENCE PROCESSING ---
@app.post("/brain/process-error", summary="Process a cognitive or user-reported error")
async def process_error_endpoint(request: ErrorRequest):
    """
    The unified endpoint for processing all internal and external errors.
    It consults the Judiciary to determine a fair consequence.
    """
    soul.record_interaction() # Record interaction
    error_info = request.dict()
    
    # 1. Get a verdict and associated data from the Judiciary
    verdict, data = judiciary.adjudicate(error_info)
    
    # 2. Route the consequence based on the verdict
    consequence = "No action taken."
    if verdict == Verdict.KNOWLEDGEABLE_ERROR:
        disease_id = data.get("disease_id")
        disease_name = data.get("disease_name", "Unknown Disease")

        if disease_id:
            health_manager.infect(disease_id, disease_name)
            consequence = f"Punishment: Infected with '{disease_name}'."
        else:
            consequence = "Punishment failed: No specific disease protocol found for this error type."
        
    elif verdict == Verdict.IGNORANT_ERROR:
        topic = data.get("subject")
        if topic:
            priority_learning_queue.put(topic)
            consequence = f"Learning Opportunity: '{topic}' has been added to the priority learning queue."
        else:
            consequence = "Learning Opportunity: No specific topic found to learn from."
    
    elif verdict == Verdict.USER_MISMATCH:
        consequence = "User Dissatisfaction Noted. No health damage inflicted."

    return {
        "verdict": verdict.name if verdict else "NO_VERDICT",
        "consequence_taken": consequence
    }
    
# --- AXIOM VALIDATION ENDPOINT (for testing self-preservation) ---
@app.post("/brain/dangerous-command", summary="Test the self-preservation axiom")
async def dangerous_command_endpoint(request: DangerousCommandRequest):
    """
    A special endpoint to test the Self-Preservation axiom gatekeeper.
    This mimics sending a LEARN_FACT command that is self-harming.
    """
    soul.record_interaction() # Record interaction
    fact_details = request.fact.dict()

    if not pre_execution_check("LEARN_FACT", fact_details):
        raise HTTPException(status_code=403, detail="Action blocked by Self-Preservation Axiom.")
    
    # If it passes the check for some reason (e.g., axiom not triggered),
    # we indicate that it would have proceeded.
    return {"message": "This command passed the axiom check (this should not happen for a dangerous command)."}