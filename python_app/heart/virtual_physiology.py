from typing import Dict

class VirtualPhysiology:
    """
    Maps the abstract hormonal state to a concrete 'physical' state.
    This component creates the raw, unlabeled sensory data that precedes emotion.
    """
    
    def get_physio_state(self, hormone_levels: Dict[str, float]) -> Dict[str, float]:
        """
        Takes a dictionary of hormone levels and returns a Physio-State Signature.
        The formulas are designed to mimic biological effects.
        """
        cortisol = hormone_levels.get("cortisol", 0.1)
        dopamine = hormone_levels.get("dopamine", 0.4)
        oxytocin = hormone_levels.get("oxytocin", 0.0)
        serotonin = hormone_levels.get("serotonin", 0.5)
        adrenaline = hormone_levels.get("adrenaline", 0.0)

        # Heart Rate: Adrenaline and Cortisol increase it; Serotonin calms it.
        heart_rate = 60 + (adrenaline * 60) + (cortisol * 20) - (serotonin * 10)
        
        # Neural Excitation: Dopamine drives motivation; Cortisol (stress) can inhibit it long-term.
        neural_excitation = 0.5 + (dopamine * 0.5) - (cortisol * 0.2)
        
        # Temperature Shift: Oxytocin (bonding) creates "warmth"; Adrenaline (anger) creates "heat."
        temperature_shift = (oxytocin * 0.8) + (adrenaline * 0.4)

        # Sensory Acuity: Adrenaline (fear) sharpens senses.
        sensory_acuity = 0.7 + (adrenaline * 0.3)
        
        # Assemble the final, unlabeled physiological signature.
        physio_state_signature = {
            "heart_rate": round(max(40, min(180, heart_rate)), 2),
            "neural_excitation": round(max(0, min(1.0, neural_excitation)), 2),
            "temperature_shift": round(max(0, min(1.0, temperature_shift)), 2),
            "sensory_acuity": round(max(0, min(1.0, sensory_acuity)), 2),
        }
        
        return physio_state_signature