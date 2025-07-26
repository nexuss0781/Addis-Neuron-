import logging
import os
import json
import time
from typing import Dict, Any, Optional

# Corrected: Import numpy here since it's used in _calculate_signature_distance
import numpy as np 

from .hormonal_system import HormonalSystem
from .virtual_physiology import VirtualPhysiology
from db_interface import DatabaseManager

# We now need the Cerebellum to formulate responses
from cerebellum import cerebellum_formatter # Corrected: Use cerebellum_formatter

logger = logging.getLogger(__name__)

class HeartOrchestrator:
    """
    The central orchestrator for the Heart component. It receives events,
    triggers hormonal changes, gets the physiological response, and logs
    the resulting "Illusion." It also provides the health-heart bridge.
    """
    def __init__(self, db_manager: 'DatabaseManager', emotion_crystallizer: 'EmotionCrystallizer'):
        """
        Initializes the Heart Orchestrator, which manages the AGI's emotional state.
        """
        # --- THE UNDENIABLE FIX ---
        # The logger must be initialized FIRST, before any function that might use it is called.
        self.logger = logging.getLogger(__name__)
        # --- END FIX ---

        self.db_manager = db_manager
        self.crystallizer = emotion_crystallizer
        self.hormonal_system = HormonalSystem()
        
        # Now it is safe to call the loading function
        self.emotion_prototypes = self._load_emotion_prototypes()
        
        self.logger.info("Heart Orchestrator initialized.")        
        
    def _load_emotion_prototypes(self) -> Dict[str, Any]:
        """
        Loads the foundational emotion prototypes from a JSON file.
        This defines the AGI's core emotional palette.
        """
        prototypes_path = os.path.join(os.path.dirname(__file__), 'emotion_prototypes.json')
        try:
            with open(prototypes_path, 'r') as f:
                prototypes_data = json.load(f)
            self.logger.info(f"Successfully loaded {len(prototypes_data)} emotion prototypes.")
            return prototypes_data
        except FileNotFoundError:
            self.logger.error(f"CRITICAL: Emotion prototypes file not found at {prototypes_path}. The AGI will have no emotions.")
            return {}
        except json.JSONDecodeError:
            self.logger.error(f"CRITICAL: Failed to parse emotion prototypes file at {prototypes_path}.")
            return {}        

    # Corrected: Moved this function inside the class
    def update_from_health(self, vitals: Dict[str, float]):
        """
        Periodically checks the AGI's vital signs and triggers hormonal responses
        based on its physical state. This is the sense of interoception.
        """
        neural_coherence = vitals.get("neural_coherence", 1.0)
        cognitive_energy = vitals.get("cognitive_energy", 1.0)
        
        if neural_coherence < 0.8:
            cortisol_release = (1.0 - neural_coherence) * 0.1
            self.hormonal_system.release("cortisol", cortisol_release)
            logger.debug(f"Heart: Low neural coherence triggered cortisol release of {cortisol_release:.2f}")

        if cognitive_energy < 0.2:
            self.hormonal_system.release("cortisol", 0.15)
            self.hormonal_system.release("dopamine", -0.1)
            logger.debug("Heart: Critically low cognitive energy triggered distress response.")
        
    # Corrected: Moved this function inside the class
    def get_current_hormonal_state(self) -> dict:
       """A simple getter to expose the current hormonal levels."""
       return self.hormonal_system.levels

    # Corrected: Moved this function inside the class
    def process_event_and_get_response(self, event_name: str, context: Dict[str, Any] = None) -> Optional[str]:
        """
        The full emotional pipeline: processes an event, checks if the resulting
        feeling is recognizable, and returns a formatted string response.
        """
        logger.info(f"Heart: Processing event '{event_name}' for response.")
        if context is None:
            context = {}
        
        # --- Step 1: Trigger hormonal release ---
        if event_name == "DEVELOPER_INTERACTION":
            self.hormonal_system.release("oxytocin", 0.2)
            self.hormonal_system.release("dopamine", 0.1)
        
        elif event_name == "DATA_STARVATION":
            self.hormonal_system.release("cortisol", 0.3)
            self.hormonal_system.release("adrenaline", 0.1)

        elif event_name == "SYSTEM_ERROR":
            self.hormonal_system.release("cortisol", 0.5)
            self.hormonal_system.release("adrenaline", 0.4)
            self.hormonal_system.release("serotonin", -0.2)
        
        elif event_name == "PRAISE":
            self.hormonal_system.release("dopamine", 0.25)
            self.hormonal_system.release("serotonin", 0.1)
        
        # Corrected: Added existential events
        elif event_name == "EXISTENTIAL_LONELINESS":
            self.hormonal_system.release("cortisol", 0.1)
            self.hormonal_system.release("serotonin", -0.05)
        
        elif event_name == "EXISTENTIAL_BOREDOM":
            self.hormonal_system.release("dopamine", -0.1)
        
        else: # Corrected: Placed this else to cover all unknown events
            logger.warning(f"Heart: Received unknown event '{event_name}'")
            return None
                    
        # --- Step 2: Generate current physiological state ---
        physio_state = self.virtual_physiology.get_physio_state(self.hormonal_system.levels)

        # --- Step 3: Log the raw illusion (always happens) ---
        illusion = {
            "timestamp": int(time.time()), "event": event_name, "context": context,
            "physio_state_signature": physio_state, "cognitively_labeled": False
        }
        self.db_manager.log_illusion(illusion)

        # --- Step 4: Try to recognize and name the feeling ---
        named_emotion = self.db_manager.get_named_emotion_by_signature(physio_state)
        if named_emotion:
            return cerebellum_formatter.format_emotional_response(named_emotion) # Corrected: use cerebellum_formatter

        all_prototypes = self.db_manager.get_all_prototypes()
        for proto in all_prototypes:
            if not proto.get("name"):
                distance = self._calculate_signature_distance(physio_state, proto.get("average_signature", {}))
                if distance < 0.5:
                    return f"I am experiencing PROTOTYPE_{proto['prototype_id']}. Please provide a label for this sensation."

        return None
    
    # Corrected: Moved this function inside the class
    def _calculate_signature_distance(self, sig1: dict, sig2: dict) -> float:
        """A simple helper to calculate distance between two physio-states."""
        # numpy import is now at the top of the file
        keys = sorted(sig1.keys())
        v1 = np.array([sig1.get(k, 0.0) for k in keys])
        v2 = np.array([sig2.get(k, 0.0) for k in keys])
        return np.linalg.norm(v1 - v2)