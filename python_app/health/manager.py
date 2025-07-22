import logging
from typing import Dict, List, Set

from db_interface import db_manager

logger = logging.getLogger(__name__)

class HealthManager:
    """
    Acts as the single source of truth for the AGI's health.
    Manages vital signs and active diseases by querying the NLSE for protocols.
    """
    def __init__(self):
        """Initializes the AGI with a full set of vitals and no diseases."""
        self.vitals: Dict[str, float] = {
            "neural_coherence": 1.0,
            "system_integrity": 1.0,
            "cognitive_energy": 1.0,
            "immunity_level": 0.5,
        }
        self.active_disease_ids: List[str] = []
        self.immunities: Set[str] = set() # Stores names of diseases AGI is immune to
        logger.info("Health Manager (NLSE-Integrated) initialized.")

    def get_vitals(self) -> Dict[str, float]:
        """Returns a copy of the current vital signs."""
        return self.vitals.copy()
        
    def take_damage(self, vital_name: str, amount: float):
        """Inflicts damage on a specific vital sign."""
        if vital_name in self.vitals:
            current_level = self.vitals[vital_name]
            damage_amount = abs(amount)
            new_level = max(0.0, current_level - damage_amount)
            self.vitals[vital_name] = new_level
            logger.debug(f"HEALTH DAMAGE: '{vital_name}' decreased -> {new_level:.2f}")
        else:
            logger.error(f"Attempted to damage unknown vital: {vital_name}")

    def heal(self, vital_name: str, amount: float):
        """Restores health to a specific vital sign."""
        if vital_name in self.vitals:
            current_level = self.vitals[vital_name]
            heal_amount = abs(amount)
            new_level = min(1.0, current_level + heal_amount)
            self.vitals[vital_name] = new_level
            if heal_amount > 0.01:
                 logger.info(f"HEALTH RECOVERY: '{vital_name}' increased -> {new_level:.2f}")

    def infect(self, disease_id: str, disease_name: str):
        """Infects the AGI with a disease protocol by its ID, checking immunities."""
        # --- Check for permanent vaccination first ---
        if disease_name in self.immunities:
            logger.info(f"HEALTH DEFENSE: AGI is vaccinated against '{disease_name}'. Infection blocked.")
            return

        # Simple resistance check (can be enhanced by querying disease severity from NLSE)
        if disease_id not in self.active_disease_ids:
            self.active_disease_ids.append(disease_id)
            logger.warning(f"HEALTH ALERT: AGI has been infected with disease '{disease_name}' (ID: {disease_id}).")
        else:
            logger.info(f"HEALTH INFO: AGI is already suffering from disease '{disease_name}'.")

    def update(self):
        """
        The new update loop. It queries the NLSE for each active disease's
        protocol and applies its symptoms.
        """
        if not self.active_disease_ids:
            regen_bonus = 1 + self.vitals["immunity_level"]
            self.heal("cognitive_energy", 0.005 * regen_bonus)
            self.heal("neural_coherence", 0.001 * regen_bonus)
            return

        logger.info(f"Health update: AGI is suffering from {len(self.active_disease_ids)} disease(s).")
        
        # For each active disease, get its protocol and apply symptoms
        for disease_id in self.active_disease_ids:
            symptoms = db_manager.get_symptoms_for_disease(disease_id) # This method will be created
            if symptoms:
                for symptom in symptoms:
                    try:
                        # SUPER SIMPLIFIED formula parser for "-0.05 * stage" etc.
                        # A real version would use a safe math parsing library.
                        damage = float(symptom['effect_formula'].split('*')[0])
                        self.take_damage(symptom['target_vital'], abs(damage))
                    except Exception as e:
                        logger.error(f"Failed to apply symptom for disease {disease_id}: {e}")
            else:
                logger.error(f"Could not find symptoms for active disease ID {disease_id}")
    
    # We will need to refactor cure, vaccinate etc. to use IDs instead of names later
    # For now, we'll keep them as placeholders.
    def cure_disease(self, disease_id: str) -> bool:
        if disease_id in self.active_disease_ids:
            self.active_disease_ids.remove(disease_id)
            logger.warning(f"CURED: AGI has been cured of disease ID '{disease_id}'.")
            return True
        return False

    def vaccinate(self, disease_name: str):
         if disease_name not in self.immunities:
            self.immunities.add(disease_name)
            logger.info(f"VACCINATED: AGI is now permanently immune to '{disease_name}'.")