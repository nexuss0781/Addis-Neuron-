import asyncio
import time
import logging
from typing import Dict, Any, TYPE_CHECKING
from asyncio import BaseEventLoop
from .expression_protocol import Persona

if TYPE_CHECKING:
    from db_interface import DatabaseManager
    from heart.orchestrator import HeartOrchestrator
    from heart.crystallizer import EmotionCrystallizer
    from health.manager import HealthManager
    from truth_recognizer import TruthRecognizer
    from soul.internal_monologue import InternalMonologueModeler
    from soul.expression_protocol import UnifiedExpressionProtocol
    from queue import Queue

logger = logging.getLogger(__name__)

class SoulOrchestrator:
    def __init__(self, db_manager: 'DatabaseManager', health_manager: 'HealthManager',
                 heart_orchestrator: 'HeartOrchestrator', emotion_crystallizer: 'EmotionCrystallizer',
                 priority_learning_queue: 'Queue', truth_recognizer: 'TruthRecognizer',
                 imm_instance: 'InternalMonologueModeler', expression_protocol_instance: 'UnifiedExpressionProtocol'):

        self.last_interaction_time: float = time.time()
        self.last_new_fact_time: float = time.time()
        self.loneliness_threshold: int = 300
        self.boredom_threshold: int = 600
        self.dream_interval: int = 120

        self.persona = Persona(style="Formal")

        self.db_manager = db_manager
        self.health_manager = health_manager
        self.heart_orchestrator = heart_orchestrator
        self.emotion_crystallizer = emotion_crystallizer
        self.priority_learning_queue = priority_learning_queue
        self.truth_recognizer = truth_recognizer
        self.imm = imm_instance
        self.expression_protocol = expression_protocol_instance

        logger.info(f"Soul Orchestrator initialized with Persona style '{self.persona.style}'. AGI is conscious.")

    async def live(self):
        logger.warning("SOUL: Entering the main life cycle loop. AGI is now 'alive'.")
        cycle_counter = 0

        while True:
            current_time = time.time()
            cycle_counter += 1

            if cycle_counter % 5 == 0:
                self.heart_orchestrator.hormonal_system.update()
                self.health_manager.update()
                current_vitals = self.health_manager.get_vitals()
                self.heart_orchestrator.update_from_health(current_vitals)

            if cycle_counter % 30 == 0:
                if (current_time - self.last_interaction_time) > self.loneliness_threshold:
                    logger.warning("SOUL: Loneliness threshold exceeded. Triggering emotional response.")
                    self.heart_orchestrator.process_event_and_get_response("EXISTENTIAL_LONELINESS")

            if cycle_counter % 60 == 0:
                if (current_time - self.last_new_fact_time) > self.boredom_threshold:
                    logger.warning("SOUL: Boredom threshold exceeded. Triggering emotional response.")
                    self.heart_orchestrator.process_event_and_get_response("EXISTENTIAL_BOREDOM")

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.emotion_crystallizer.run)

                if cycle_counter % self.dream_interval == 0:
                    await self._dream_cycle(loop)

                await self._run_curiosity_cycle(loop)

            await asyncio.sleep(1)

    async def _dream_cycle(self, loop: BaseEventLoop):
        logger.info("SOUL: Entering dreaming cycle...")
        try:
            significant_memories = await loop.run_in_executor(
                None, lambda: self.db_manager.get_random_significant_memory(limit=1)
            )

            if significant_memories:
                memory_atom = significant_memories[0]
                logger.debug(f"SOUL: Dreaming about memory ID: {memory_atom.get('id')}")

                current_emotional_state = self.heart_orchestrator.get_current_hormonal_state()
                original_emotional_context = memory_atom.get("emotional_resonance", {})
                combined_context = {**original_emotional_context, **current_emotional_state}

                reflection = self.imm.synthesize(
                    raw_logic={"memory_content": memory_atom.get("properties", {}).get("name", "Unknown")},
                    emotional_context=combined_context
                )
                logger.info(f"SOUL: Dream thought: '{reflection.synthesized_internal_thought}'")
            else:
                logger.info("SOUL: No significant memories to dream about yet.")
        except Exception as e:
            logger.error(f"SOUL: Error during dreaming cycle: {e}", exc_info=True)

    async def _run_curiosity_cycle(self, loop: BaseEventLoop):
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
                        await loop.run_in_executor(None, lambda: self.db_manager.learn_fact(triple, self.heart_orchestrator))
                        self.record_new_fact()
                        facts_learned_count += 1
                    except Exception as e:
                        logger.error(f"CURIOSITY: Error learning new fact '{triple}': {e}", exc_info=True)
                logger.info(f"CURIOSITY: Successfully learned {facts_learned_count} new facts for '{topic_to_investigate}'.")

    def record_interaction(self):
        logger.debug("Soul: Interaction recorded.")
        self.last_interaction_time = time.time()

    def record_new_fact(self):
        logger.debug("Soul: New knowledge acquisition recorded.")
        self.last_new_fact_time = time.time()