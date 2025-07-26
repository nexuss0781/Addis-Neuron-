import time
import logging
from typing import Dict, List, Set # Corrected: Added Set

from db_interface import db_manager

logger = logging.getLogger(__name__)

class HealthManager:
    """
    Acts as the single source of truth for the AGI's health.
    Manages vital signs and active diseases by querying the NLSE for protocols.
    """
    def __init__(self, db_manager: 'DatabaseManager'):
        """
        Initializes the Health Manager, which tracks the AGI's vitals and diseases.
        """
        # --- THE UNDENIABLE FIX ---
        # Store the db_manager instance.
        self.db_manager = db_manager
        # --- END FIX ---

        self.logger = logging.getLogger(__name__)
        self.vitals: Dict[str, float] = {
            "neural_coherence": 1.0,
            "system_integrity": 1.0,
            "cognitive_energy": 1.0,
            "immunity_level": 0.5
        }
        self.active_disease_ids: Set[str] = set()
        self.immunities: Set[str] = set()
        self.last_update_time: float = time.time()
        self.logger.info(f"Health Manager (NLSE-Integrated) initialized. Vitals: {self.vitals}")

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

    def infect(self, disease_id: str, disease_name: str): # Corrected: Parameter order
        """Infects the AGI with a disease protocol by its ID, checking immunities."""
        # Check for permanent vaccination first
        if disease_name in self.immunities:
            logger.info(f"HEALTH DEFENSE: AGI is vaccinated against '{disease_name}'. Infection blocked.")
            return # Added explicit return

        # Simple resistance check (can be enhanced by querying disease severity from NLSE)
        # Note: 'disease' is not available here, as it's now an ID/name.
        # This part needs to query NLSE for disease severity based on disease_id/name if needed.
        # For now, resistance is simplified or removed from this check.
        # Leaving out the random.random() < resistance_chance part for now,
        # as it requires disease severity from NLSE, which is a later integration step.

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
            symptoms = db_manager.get_symptoms_for_disease(disease_id)
            if symptoms:
                for symptom in symptoms:
                    try:
                        # SUPER SIMPLIFIED formula parser for "-0.05 * stage" etc.
                        damage = float(symptom['effect_formula'].split('*')[0])
                        self.take_damage(symptom['target_vital'], abs(damage))
                    except Exception as e:
                        logger.error(f"Failed to apply symptom for disease {disease_id}: {e}")
            else:
                logger.error(f"Could not find symptoms for active disease ID {disease_id}")
    
    # Corrected: Refactor cure, vaccinate to use IDs/names as planned
    def cure_disease(self, disease_id: str) -> bool:
        """Removes a disease from the active list."""
        initial_count = len(self.active_disease_ids)
        # Use a list comprehension to filter out the disease by ID
        self.active_disease_ids = [d for d in self.active_disease_ids if d != disease_id]
        
        if len(self.active_disease_ids) < initial_count:
            logger.warning(f"CURED: AGI has been cured of disease ID '{disease_id}'.")
            return True
        else:
            logger.warning(f"CURE FAILED: Disease ID '{disease_id}' not found in active diseases.")
            return False

    def vaccinate(self, disease_name: str): # Parameter remains disease_name for lookup in immunities set
         if disease_name not in self.immunities:
            self.immunities.add(disease_name)
            logger.info(f"VACCINATED: AGI is now permanently immune to '{disease_name}'.")

    def administer_medication(self, medication_name: str, **kwargs):
        """
        Looks up and applies the effect of a given medication from the Pharmacy.
        """
        from .pharmacy import get_medication # Import locally to avoid circular dependencies
        
        medication_effect = get_medication(medication_name)
        if medication_effect:
            # Pass self (HealthManager) and kwargs to the medication function
            medication_effect(self, **kwargs)
        else:
            logger.error(f"Attempted to administer unknown medication: '{medication_name}'")