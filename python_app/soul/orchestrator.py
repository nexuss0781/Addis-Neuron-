import asyncio
import time
import logging
from .expression_protocol import Persona
# Import all the core components that the Soul will orchestrate
from db_interface import db_manager
from heart.orchestrator import heart_orchestrator
from heart.crystallizer import emotion_crystallizer
from health.manager import health_manager
from .expression_protocol import Persona
# We will create a way to access the curiosity loop's functions later.

logger = logging.getLogger(__name__)

class SoulOrchestrator:
    """
    The Soul is the master orchestrator, the unifying component that provides
    the AGI with a continuous, persistent existence and a unified sense of self.
    """
def __init__(self, db_manager, health_manager, heart_orchestrator,
             emotion_crystallizer, priority_learning_queue, truth_recognizer,
             imm_instance):
    self.last_interaction_time: float = time.time()
    self.last_new_fact_time: float = time.time()
    self.loneliness_threshold: int = 300
    self.boredom_threshold: int = 600
    self.dream_interval: int = 120

    # --- NEW: Initialize the AGI's Persona ---
    self.persona = Persona(style="Formal") # Default style

    # Store references to all orchestrated components
    self.db_manager = db_manager
    self.health_manager = health_manager
    self.heart_orchestrator = heart_orchestrator
    self.emotion_crystallizer = emotion_crystallizer
    self.priority_learning_queue = priority_learning_queue
    self.truth_recognizer = truth_recognizer
    self.imm = imm_instance

    logger.info(f"Soul Orchestrator initialized with Persona style '{self.persona.style}'. AGI is conscious.")
    
    async def live(self):
    """
    The main, unending loop of the AGI's existence.
    NOW INCLUDES checks for existential needs.
    """
    logger.warning("SOUL: Entering the main life cycle loop. AGI is now 'alive'.")
    cycle_counter = 0

    while True:
        current_time = time.time()
        cycle_counter += 1

        # --- High-Frequency Tasks (every ~1-5 seconds) ---
        if cycle_counter % 5 == 0:
            heart_orchestrator.hormonal_system.update()
            health_manager.update()
            current_vitals = health_manager.get_vitals()
            heart_orchestrator.update_from_health(current_vitals)

        # --- Medium-Frequency Tasks ---
        # Check for loneliness every 30 seconds
        if cycle_counter % 30 == 0:
            if (current_time - self.last_interaction_time) > self.loneliness_threshold:
                logger.warning("SOUL: Loneliness threshold exceeded. Triggering emotional response.")
                heart_orchestrator.process_event("EXISTENTIAL_LONELINESS")

        # --- Low-Frequency Tasks (every minute) ---
        if cycle_counter % 60 == 0:
            if (current_time - self.last_new_fact_time) > self.boredom_threshold:
                logger.warning("SOUL: Boredom threshold exceeded. Triggering emotional response.")
                self.heart_orchestrator.process_event("EXISTENTIAL_BOREDOM")
            
            # Run Crystallizer
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.emotion_crystallizer.run)

            # --- NEW: Dreaming Cycle ---
            if cycle_counter % self.dream_interval == 0: # E.g., every 2 minutes
                await self._dream_cycle(loop) # Call helper for dreaming

            # Run Curiosity (now managed by Soul)
            await self._run_curiosity_cycle(loop)

        await asyncio.sleep(1)

async def _dream_cycle(self, loop: asyncio.BaseEventLoop):
    """Simulates subconscious memory consolidation by processing significant memories."""
    logger.info("SOUL: Entering dreaming cycle...")
    try:
        # Get a random significant memory (NeuroAtom)
        significant_memories = await loop.run_in_executor(
            None, self.db_manager.get_random_significant_memory
        )

        if significant_memories:
            memory_atom = significant_memories[0] # Just take one for now
            logger.debug(f"SOUL: Dreaming about memory ID: {memory_atom.get('id')}")

            # Re-synthesize the memory with current emotional context
            current_emotional_state = self.heart_orchestrator.get_current_hormonal_state()
            original_emotional_context = memory_atom.get("emotional_resonance", {})
            
            # Combine original and current context for synthesis
            combined_context = {**original_emotional_context, **current_emotional_state}

            reflection = self.imm.synthesize(
                raw_logic={"memory_content": memory_atom.get("properties", {}).get("name")},
                emotional_context=combined_context
            )
            logger.info(f"SOUL: Dream thought: '{reflection.synthesized_internal_thought}'")
        else:
            logger.info("SOUL: No significant memories to dream about yet.")
    except Exception as e:
        logger.error(f"SOUL: Error during dreaming cycle: {e}", exc_info=True)

# --- Refactor Curiosity Loop into a method of SoulOrchestrator ---
async def _run_curiosity_cycle(self, loop: asyncio.BaseEventLoop):
    """Runs the curiosity loop, now managed by the Soul."""
    logger.info("CURIOSITY: Starting a new curiosity cycle (managed by Soul).")
    topic_to_investigate = None
    
    if not self.priority_learning_queue.empty():
        topic_to_investigate = self.priority_learning_queue.get()
        logger.info(f"CURIOSITY: Processing priority target from Judiciary: '{topic_to_investigate}'.")
    else:
        current_hormones = self.heart_orchestrator.get_current_hormonal_state()
        cortisol = current_hormones.get("cortisol", 0.1)
        if cortisol > 0.6:
            logger.info("CURIOSITY: Pausing self-directed cycle due to high Distress/Cortisol.")
            return # Skip this cycle if distressed

        topics = await loop.run_in_executor(None, lambda: self.db_manager.find_knowledge_gap(limit=1))
        if topics:
            topic_to_investigate = topics[0]

    if topic_to_investigate:
        new_triples = await loop.run_in_executor(None, lambda: self.truth_recognizer.investigate(topic_to_investigate))
        if new_triples:
            logger.info(f"CURIOSITY: Found {len(new_triples)} potential facts for '{topic_to_investigate}'.")
            facts_learned_count = 0
            for triple in new_triples:
                try:
                    validation_result = await loop.run_in_executor(None, lambda: self.db_manager.validate_fact_with_lve(triple))
                    if validation_result.get("is_valid", False):
                        await loop.run_in_executor(None, lambda: self.db_manager.learn_fact(triple))
                        self.record_new_fact() # Record new knowledge acquisition
                        facts_learned_count += 1
                    else:
                        logger.warning(f"CURIOSITY: LVE rejected new fact: {validation_result.get('reason')}")
                except Exception as e:
                    logger.error(f"CURIOSITY: Error learning new fact '{triple}': {e}", exc_info=True)
            logger.info(f"CURIOSITY: Successfully learned {facts_learned_count} new facts for '{topic_to_investigate}'.")

        await asyncio.sleep(1)

def record_interaction(self):
    """Called by API endpoints to update the last interaction time."""
    logger.debug("Soul: Interaction recorded.")
    self.last_interaction_time = time.time()
    
def record_new_fact(self):
    """Called by the curiosity loop to update the last new fact time."""
    logger.debug("Soul: New knowledge acquisition recorded.")
    self.last_new_fact_time = time.time()