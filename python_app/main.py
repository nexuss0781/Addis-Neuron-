import logging
import asyncio
import requests
from requests.exceptions import RequestException
from health.manager import HealthManager
from health.pathogens import get_disease_by_name
from health.judiciary import judiciary, Verdict
from soul.internal_monologue import InternalMonologueModeler # For the IMM
from soul.expression_protocol import UnifiedExpressionProtocol

from fastapi import FastAPI, HTTPException
from neo4j.exceptions import ServiceUnavailable
from prometheus_fastapi_instrumentator import Instrumentator
from queue import Queue

# --- HEART IMPORTS ---
from heart.orchestrator import HeartOrchestrator
from heart.crystallizer import EmotionCrystallizer
# Import our custom modules
from models import (
    StructuredTriple, 
    PlanRequest,
    LabelEmotionRequest,
    DamageRequest,
    DiseaseRequest, 
    MedicationRequest, 
    SelfCorrectionRequ,
    ErrorRequest,
    DiseaseDefinition
    
from db_interface import db_manager
from cerebellum import cerebellum_formatter
from truth_recognizer import truth_recognizer


# --- 1. SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the main FastAPI application instance
app = FastAPI(title="Brain Orchestrator")

# A thread-safe queue for high-priority learning targets from the Judiciary
priority_learning_queue = Queue()

# --- INITIALIZE CORE COMPONENTS ---
health_manager = HealthManager()
heart_orchestrator = HeartOrchestrator(db_manager)
# The AGI's private internal mind
imm = InternalMonologueModeler()
expression_protocol = UnifiedExpressionProtocol()
emotion_crystallizer = EmotionCrystallizer(db_manager)
# --- INITIALIZE CORE COMPONENTS ---


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

async def hormonal_decay_cycle():
    """Heart: Periodically applies natural decay to hormones."""
    while True:
        await asyncio.sleep(5) # Decay hormones every 5 seconds
        heart_orchestrator.hormonal_system.update()

async def crystallizer_cycle():
    """Heart: Periodically analyzes raw feelings to find patterns."""
    while True:
        # Run the analysis every 10 minutes.
        # Set to 60s for easier testing.
        await asyncio.sleep(60)
        logger.info("CRYSTALLIZER: Running periodic emotion analysis cycle.")
        try:
            # The run() method is synchronous, so we run it in a thread
            # to avoid blocking the main async loop.
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, emotion_crystallizer.run
            )
        except Exception as e:
            logger.error(f"Crystallizer cycle failed with an unexpected error: {e}")

async def health_update_cycle():
    """Health: Periodically runs the main update loop for the Health Manager."""
    while True:
        await asyncio.sleep(5) # Tick health every 5 seconds
        try:
            # The manager now handles its own state updates (disease damage, etc.)
            health_manager.update()
            
            # The heart continues to react to the resulting vital signs
            current_vitals = health_manager.get_vitals()
            heart_orchestrator.update_from_health(current_vitals)
        except Exception as e:
            logger.error(f"Health update cycle failed with an unexpected error: {e}")

async def curiosity_loop():
    """PFC: Proactively finds and fills knowledge gaps, now with a priority queue."""
    await asyncio.sleep(20) # Shorten initial delay for testing
    
    while True:
        logger.info("CURIOSITY: Starting a new curiosity cycle.")
        topic_to_investigate = None
        
        # --- PRIORITY QUEUE CHECK ---
        # 1. ALWAYS check for priority targets from the Judiciary first.
        if not priority_learning_queue.empty():
            topic_to_investigate = priority_learning_queue.get()
            logger.info(f"CURIOSITY: Processing priority target from Judiciary: '{topic_to_investigate}'.")

        # 2. If no priority targets, proceed with normal, self-directed curiosity.
        else:
            current_hormones = heart_orchestrator.get_current_hormonal_state()
            cortisol = current_hormones.get("cortisol", 0.1)
            
            if cortisol > 0.6:
                logger.info("CURIOSITY: Pausing self-directed cycle due to high Distress/Cortisol levels.")
                await asyncio.sleep(60)
                continue

            topics = db_manager.find_knowledge_gap(limit=1)
            if topics:
                topic_to_investigate = topics[0]

        # 3. Investigate the chosen topic, whether from priority or self-direction.
        if topic_to_investigate:
            new_triples = truth_recognizer.investigate(topic_to_investigate)
            if new_triples:
                logger.info(f"CURIOSITY: Found {len(new_triples)} potential facts for '{topic_to_investigate}'.")
                facts_learned_count = 0
                for triple in new_triples:
                    try:
                        # Use the existing, validated learn_fact function in the DB interface
                        db_manager.learn_fact(triple) 
                        facts_learned_count += 1
                    except Exception as e:
                        logger.warning(f"CURIOSITY: Failed to learn fact during investigation '{triple}': {e}")
                logger.info(f"CURIOSITY: Successfully learned {facts_learned_count} new facts for '{topic_to_investigate}'.")
        
        await asyncio.sleep(60) # Shorten cycle for testing
        
# --- 3. APP LIFECYCLE EVENTS ---
@app.on_event("startup")
async def startup_event():
    logger.info("Brain Orchestrator starting up...")
    # Launch background tasks
    asyncio.create_task(forgetting_cycle())
    asyncio.create_task(curiosity_loop())
    asyncio.create_task(hormonal_decay_cycle())
    asyncio.create_task(crystallizer_cycle())
    asyncio.create_task(health_update_cycle()) # <-- ADD THIS LINE

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
        soul.record_new_fact() # Record that new knowledge was acquired
        return {"message": "Fact validated and learned successfully", "fact": triple}
    except ServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Database service is unavailable. Could not learn fact. Reason: {e}")
    except HTTPException as e:
        raise e # Re-raise known HTTP exceptions
    except Exception as e:
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
        final_output = expression_protocol.generate_output(reflection, soul.persona)
        
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

# --- HEART TEST ENDPOINT ---
@app.post("/heart/trigger-event/{event_name}", summary="Trigger a primitive emotional event")
async def trigger_heart_event(event_name: str):
    """
    Triggers a primitive event in the Heart and returns the AI's
    resulting emotional expression, if any.
    Valid events: DEVELOPER_INTERACTION, DATA_STARVATION, SYSTEM_ERROR, PRAISE
    """
    valid_events = ["DEVELOPER_INTERACTION", "DATA_STARVATION", "SYSTEM_ERROR", "PRAISE"]
    if event_name not in valid_events:
        raise HTTPException(status_code=400, detail=f"Invalid event name. Use one of: {valid_events}")

    try:
        # The orchestrator now handles the full pipeline and returns a string
        emotional_response = heart_orchestrator.process_event_and_get_response(event_name)

        return {
            "event_processed": event_name,
            "emotional_expression": emotional_response,
            "current_hormones": heart_orchestrator.hormonal_system.levels
        }
    except Exception as e:
        # It's useful to log the full error for debugging
        logger.error(f"Error in heart event processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the event: {str(e)}")
 

# --- HEALTH TEST ENDPOINT ---
# --- HEALTH MANAGEMENT ---
@app.post("/health/define-disease", summary="Define a new disease in the NLSE")
async def define_disease_endpoint(request: DiseaseDefinition):
    """
    Allows a developer to dynamically add a new disease protocol to the AGI's
    long-term memory.
    """
    try:
        success = db_manager.define_new_disease(request)
        if not success:
             raise HTTPException(status_code=500, detail="Failed to create disease definition plan in NLSE.")

        return {
            "message": f"New disease protocol '{request.name}' successfully defined and stored in the NLSE.",
        }
    except Exception as e:
        logger.error(f"Error defining disease: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/health/medicate", summary="Administer a medication to the AGI")
async def administer_medication_endpoint(request: MedicationRequest):
    """A test endpoint to administer a general medication from the pharmacy."""
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
    try:
        # The 'disease_name' is passed as a keyword argument to the medication
        health_manager.administer_medication(
            "SelfCorrectionAntidote",
            disease_name=request.disease_name
        )
        return {
            "message": f"Self-correction process initiated for '{request.disease_name}'.",
            "current_vitals": health_manager.get_vitals(),
            "active_diseases": [d.name for d in health_manager.active_diseases],
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
    error_info = request.dict()
    
    # 1. Get a verdict and associated data from the Judiciary
    verdict, data = judiciary.adjudicate(error_info)
    
    # 2. Route the consequence based on the verdict
    consequence = "No action taken."
    if verdict == Verdict.KNOWLEDGEABLE_ERROR:
        # The Judiciary has determined punishment is warranted.
        # It has already queried the NLSE for the correct disease.
        disease_id = data.get("disease_id")
        disease_name = data.get("disease_name", "Unknown Disease") # Get name for logging

        if disease_id:
            health_manager.infect(disease_id, disease_name)
            consequence = f"Punishment: Infected with '{disease_name}'."
        else:
            consequence = "Punishment failed: No specific disease protocol found for this error type."
        
    elif verdict == Verdict.IGNORANT_ERROR:
        # This is a learning opportunity.
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
    
async def get_health_status():
    """Returns the current vitals and active diseases."""
    return {
        "current_vitals": health_manager.get_vitals(),
        "active_diseases": [
            {"name": d.name, "severity": d.severity, "stage": d.current_stage}
            for d in health_manager.active_diseases
        ]
    }        
@app.post("/heart/label-emotion", summary="Cognitively label a felt emotion")
async def label_emotion(request: LabelEmotionRequest):
    """
    Connects an internal emotion prototype with a human-language label.
    This represents the PFC analyzing and naming an internal state.
    """
    success = db_manager.update_prototype_with_label(
        prototype_id=request.prototype_id,
        name=request.name,
        description=request.description
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Could not label emotion. Prototype with ID '{request.prototype_id}' not found or an error occurred."
        )
    
    return {
        "message": f"Emotion prototype '{request.prototype_id}' has been successfully labeled as '{request.name}'.",
    }