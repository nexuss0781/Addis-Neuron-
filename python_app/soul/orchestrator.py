import asyncio
import time
import logging
from typing import Dict, Any, TYPE_CHECKING # Corrected: Added TYPE_CHECKING

# Corrected: Explicitly import BaseEventLoop
from asyncio import BaseEventLoop

# Corrected: All core components are passed to __init__ for proper orchestration
# from db_interface import db_manager # No longer global import here
# from heart.orchestrator import heart_orchestrator # No longer global import here
# from heart.crystallizer import emotion_crystallizer # No longer global import here
# from health.manager import health_manager # No longer global import here
# from truth_recognizer import truth_recognizer # No longer global import here
# from soul.internal_monologue import InternalMonologueModeler # No longer global import here
# from soul.expression_protocol import UnifiedExpressionProtocol # No longer global import here

from .expression_protocol import Persona # Persona is defined in this module's dir

# Corrected: Use TYPE_CHECKING to avoid circular dependencies
if TYPE_CHECKING:
    from db_interface import DatabaseManager
    from heart.orchestrator import HeartOrchestrator
    from heart.crystallizer import EmotionCrystallizer
    from health.manager import HealthManager
    from truth_recognizer import TruthRecognizer
    from soul.internal_monologue import InternalMonologueModeler
    from soul.expression_protocol import UnifiedExpressionProtocol
    from queue import Queue # For priority_learning_queue


logger = logging.getLogger(__name__)

class SoulOrchestrator:
    """
    The Soul is the master orchestrator, the unifying component that provides
    the AGI with a continuous, persistent existence and a unified sense of self.
    """
    # Corrected: All components are now proper instance attributes
    def __init__(self, db_manager: 'DatabaseManager', health_manager: 'HealthManager', 
                 heart_orchestrator: 'HeartOrchestrator', emotion_crystallizer: 'EmotionCrystallizer',
                 priority_learning_queue: 'Queue', truth_recognizer: 'TruthRecognizer',
                 imm_instance: 'InternalMonologueModeler', expression_protocol_instance: 'UnifiedExpressionProtocol'):
        
        self.last_interaction_time: float = time.time()
        self.last_new_fact_time: float = time.time()
        self.loneliness_threshold: int = 300 # 5 minutes
        self.boredom_threshold: int = 600    # 10 minutes
        self.dream_interval: int = 120      # Dream every 2 minutes

        self.persona = Persona(style="Formal") # Default style

        # Store references to all orchestrated components
        self.db_manager = db_manager
        self.health_manager = health_manager
        self.heart_orchestrator = heart_orchestrator
        self.emotion_crystallizer = emotion_crystallizer
        self.priority_learning_queue = priority_learning_queue
        self.truth_recognizer = truth_recognizer
        self.imm = imm_instance
        self.expression_protocol = expression_protocol_instance # Corrected: Store instance

        logger.info(f"Soul Orchestrator initialized with Persona style '{self.persona.style}'. AGI is conscious.")

    # Corrected: Moved this function inside the class
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
                self.heart_orchestrator.hormonal_system.update() # Corrected: use self
                self.health_manager.update() # Corrected: use self
                current_vitals = self.health_manager.get_vitals() # Corrected: use self
                self.heart_orchestrator.update_from_health(current_vitals) # Corrected: use self

            # --- Medium-Frequency Tasks ---
            if cycle_counter % 30 == 0:
                if (current_time - self.last_interaction_time) > self.loneliness_threshold:
                    logger.warning("SOUL: Loneliness threshold exceeded. Triggering emotional response.")
                    self.heart_orchestrator.process_event_and_get_response("EXISTENTIAL_LONELINESS") # Corrected: use process_event_and_get_response

            # --- Low-Frequency Tasks (every minute) ---
            if cycle_counter % 60 == 0:
                if (current_time - self.last_new_fact_time) > self.boredom_threshold:
                    logger.warning("SOUL: Boredom threshold exceeded. Triggering emotional response.")
                    self.heart_orchestrator.process_event_and_get_response("EXISTENTIAL_BOREDOM") # Corrected: use process_event_and_get_response
                
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.emotion_crystallizer.run) # Corrected: use self

                if cycle_counter % self.dream_interval == 0:
                    await self._dream_cycle(loop) # Corrected: use self

                await self._run_curiosity_cycle(loop) # Corrected: use self

            await asyncio.sleep(1)

    # Corrected: Moved this function inside the class
    async def _dream_cycle(self, loop: BaseEventLoop): # Corrected: BaseEventLoop
        """Simulates subconscious memory consolidation by processing significant memories."""
        logger.info("SOUL: Entering dreaming cycle...")
        try:
            significant_memories = await loop.run_in_executor(
                None, lambda: self.db_manager.get_random_significant_memory(limit=1) # Corrected: use self and lambda for args
            )

            if significant_memories:
                memory_atom = significant_memories[0]
                logger.debug(f"SOUL: Dreaming about memory ID: {memory_atom.get('id')}")

                current_emotional_state = self.heart_orchestrator.get_current_hormonal_state()
                original_emotional_context = memory_atom.get("emotional_resonance", {})
                
                combined_context = {**original_emotional_context, **current_emotional_state}

                reflection = self.imm.synthesize(
                    raw_logic={"memory_content": memory_atom.get("properties", {}).get("name", "Unknown")}, # Corrected: default value
                    emotional_context=combined_context
                )
                logger.info(f"SOUL: Dream thought: '{reflection.synthesized_internal_thought}'")
            else:
                logger.info("SOUL: No significant memories to dream about yet.")
        except Exception as e:
            logger.error(f"SOUL: Error during dreaming cycle: {e}", exc_info=True)

    # Corrected: Moved this function inside the class
    async def _run_curiosity_cycle(self, loop: BaseEventLoop): # Corrected: BaseEventLoop
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
                return 

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
                            self.record_new_fact() # Corrected: use self
                            facts_learned_count += 1
                        else:
                            logger.warning(f"CURIOSITY: LVE rejected new fact: {validation_result.get('reason')}")
                    except Exception as e:
                        logger.error(f"CURIOSITY: Error learning new fact '{triple}': {e}", exc_info=True)
                logger.info(f"CURIOSITY: Successfully learned {facts_learned_count} new facts for '{topic_to_investigate}'.")

    # Corrected: Moved these functions inside the class
    def record_interaction(self):
        """Called by API endpoints to update the last interaction time."""
        logger.debug("Soul: Interaction recorded.")
        self.last_interaction_time = time.time()
        
    def record_new_fact(self):
        """Called by the curiosity loop to update the last new fact time."""
        logger.debug("Soul: New knowledge acquisition recorded.")
        self.last_new_fact_time = time.time()