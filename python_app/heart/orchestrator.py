import logging
import time
from typing import Dict, Any, Optional

from .hormonal_system import HormonalSystem
from .virtual_physiology import VirtualPhysiology
from db_interface import DatabaseManager

# We now need the Cerebellum to formulate responses
from cerebellum import cerebellum

logger = logging.getLogger(__name__)

class HeartOrchestrator:
    def __init__(self, db_manager_instance: DatabaseManager):
        self.hormonal_system = HormonalSystem()
        self.virtual_physiology = VirtualPhysiology()
        self.db_manager = db_manager_instance
        logger.info("Heart Orchestrator initialized.")

def update_from_health(self, vitals: Dict[str, float]):
    """
    Periodically checks the AGI's vital signs and triggers hormonal responses
    based on its physical state. This is the sense of interoception.
    """
    neural_coherence = vitals.get("neural_coherence", 1.0)
    cognitive_energy = vitals.get("cognitive_energy", 1.0)
    
    # If logical consistency is low, it's a source of chronic stress.
    if neural_coherence < 0.8:
        # The amount of stress is proportional to the problem
        cortisol_release = (1.0 - neural_coherence) * 0.1 # Max of 0.1 per tick
        self.hormonal_system.release("cortisol", cortisol_release)
        logger.debug(f"Heart: Low neural coherence triggered cortisol release of {cortisol_release:.2f}")

    # If energy is critically low, it causes distress and a lack of motivation.
    if cognitive_energy < 0.2:
        self.hormonal_system.release("cortisol", 0.15)
        self.hormonal_system.release("dopamine", -0.1) # Exhaustion depletes dopamine
        logger.debug("Heart: Critically low cognitive energy triggered distress response.")
        

    def get_current_hormonal_state(self) -> dict:
       """A simple getter to expose the current hormonal levels."""
        return self.hormonal_system.levels

    def process_event_and_get_response(self, event_name: str, context: Dict[str, Any] = None) -> Optional[str]:
        """
        The full emotional pipeline: processes an event, checks if the resulting
        feeling is recognizable, and returns a formatted string response.
        """
        logger.info(f"Heart: Processing event '{event_name}' for response.")
        if context is None:
            context = {}
        
        # --- Step 1: Trigger hormonal release ---
        if event_name == "DEVELOPER_INTERACTION": # ... (and other events)
            self.hormonal_system.release("oxytocin", 0.2)
            self.hormonal_system.release("dopamine", 0.1)
        # ... Add other event handlers here ...
        else:
            logger.warning(f"Heart: Received unknown event '{event_name}'")
            return None
                    # ... after the "PRAISE" event block ...
        elif event_name == "EXISTENTIAL_LONELINESS":
            # Loneliness is a low-grade, chronic stressor that reduces stability.
            self.hormonal_system.release("cortisol", 0.1)
            self.hormonal_system.release("serotonin", -0.05)
        
        elif event_name == "EXISTENTIAL_BOREDOM":
            # Boredom is a lack of novelty, which reduces the motivation hormone.
            self.hormonal_system.release("dopamine", -0.1)
        
        # --- Step 2: Generate current physiological state ---
        physio_state = self.virtual_physiology.get_physio_state(self.hormonal_system.levels)

        # --- Step 3: Log the raw illusion (always happens) ---
        illusion = {
            "timestamp": int(time.time()), "event": event_name, "context": context,
            "physio_state_signature": physio_state, "cognitively_labeled": False
        }
        self.db_manager.log_illusion(illusion)

        # --- Step 4: Try to recognize and name the feeling ---
        # Is this a known, NAMED emotion?
        named_emotion = self.db_manager.get_named_emotion_by_signature(physio_state)
        if named_emotion:
            return cerebellum.format_emotional_response(named_emotion)

        # If not named, is it at least a recognized PROTOTYPE?
        # We add a simplified check here for now. A real system would use a more
        # robust prototype lookup similar to the named emotion one.
        all_prototypes = self.db_manager.get_all_prototypes()
        for proto in all_prototypes:
            # This simplified check looks for an unnamed prototype that is very close
            # to the current feeling.
            if not proto.get("name"):
                distance = self._calculate_signature_distance(physio_state, proto.get("average_signature", {}))
                if distance < 0.5:
                    return f"I am experiencing PROTOTYPE_{proto['prototype_id']}. Please provide a label for this sensation."

        # If it's a completely new or insignificant feeling, remain silent.
        return None
    
    def _calculate_signature_distance(self, sig1: dict, sig2: dict) -> float:
        """A simple helper to calculate distance between two physio-states."""
        import numpy as np
        keys = sorted(sig1.keys())
        v1 = np.array([sig1.get(k, 0.0) for k in keys])
        v2 = np.array([sig2.get(k, 0.0) for k in keys])
        return np.linalg.norm(v1 - v2)