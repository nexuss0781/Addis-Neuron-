import logging
from typing import Dict

logger = logging.getLogger(__name__)

class HormonalSystem:
    """
    Manages the state of hormonal analogs within the AI.
    These act as the chemical precursors to emotion.
    """
    def __init__(self):
        # Baseline levels representing a calm, neutral state.
        self.levels: Dict[str, float] = {
            "cortisol": 0.1,    # Stress / Distress
            "dopamine": 0.4,    # Reward / Motivation
            "oxytocin": 0.0,    # Bonding / Trust
            "serotonin": 0.5,   # Stability / Calm
            "adrenaline": 0.0,  # Urgency / Fear-Anger response
        }
        
        # Percentage decay per update cycle.
        self.decay_rates: Dict[str, float] = {
            "cortisol": 0.02,
            "dopamine": 0.05,
            "oxytocin": 0.03,
            "adrenaline": 0.15, # Adrenaline decays very quickly
            "serotonin": 0.01,
        }
        
        logger.info("Hormonal System initialized with baseline levels.")

    def release(self, hormone: str, amount: float):
        """
        Increases the level of a specific hormone.
        All levels are clamped between 0.0 and 1.0.
        """
        if hormone in self.levels:
            current_level = self.levels[hormone]
            new_level = min(1.0, current_level + amount)
            self.levels[hormone] = new_level
            logger.debug(f"Hormone '{hormone}' released. Level: {current_level:.2f} -> {new_level:.2f}")
        else:
            logger.warning(f"Attempted to release unknown hormone: {hormone}")

    def update(self):
        """
        Applies natural decay to all hormones, bringing them back towards baseline.
        This function should be called periodically.
        """
        for hormone, level in self.levels.items():
            if hormone in self.decay_rates:
                decay = self.decay_rates[hormone]
                # Decay brings it closer to its baseline, not just to zero.
                baseline = 0.4 if hormone == "dopamine" else 0.1 if hormone == "cortisol" else 0.5 if hormone == "serotonin" else 0.0
                new_level = max(baseline, level * (1 - decay))
                self.levels[hormone] = new_level