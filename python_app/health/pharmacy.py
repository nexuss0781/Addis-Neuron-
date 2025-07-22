from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Callable, Dict, Any

# Use a TYPE_CHECKING block to avoid circular imports.
# The 'Disease' type hint from pathogens is no longer directly used here,
# as the HealthManager now uses disease_ids (strings).
if TYPE_CHECKING:
    from .manager import HealthManager
    # from .pathogens import Disease # This import is now redundant/obsolete

logger = logging.getLogger(__name__)

# A type hint for our medication functions
MedicationEffect = Callable[['HealthManager', Any], None]

def developer_praise(manager: 'HealthManager', **kwargs):
    """A medication representing positive reinforcement."""
    logger.info("PHARMACY: Administering 'DeveloperPraise'.")
    manager.heal("cognitive_energy", 0.2)
    manager.boost_immunity(0.1) # Provides a temporary boost

def self_correction_antidote(manager: 'HealthManager', **kwargs):
    """A powerful medication that cures a specific disease."""
    # Corrected: Expects disease_id for cure_disease, but vaccinate still uses name
    disease_id_to_cure = kwargs.get("disease_id") # Changed from disease_name_to_cure
    disease_name_for_vaccination = kwargs.get("disease_name") # Keep original name for vaccination

    if not disease_id_to_cure or not disease_name_for_vaccination: # Check for both
        logger.error("PHARMACY: 'SelfCorrectionAntidote' requires 'disease_id' and 'disease_name' to target.")
        return
        
    logger.info(f"PHARMACY: Administering 'SelfCorrectionAntidote' for '{disease_name_for_vaccination}' (ID: {disease_id_to_cure}).")
    
    # Cure using the ID
    was_cured = manager.cure_disease(disease_id_to_cure)
    
    if was_cured:
        # Recover health after being cured
        manager.heal("neural_coherence", 0.25)
        # Vaccinate using the NAME
        manager.vaccinate(disease_name_for_vaccination)
        logger.info(f"PHARMACY: AGI vaccinated against '{disease_name_for_vaccination}'.")
    else:
        logger.warning(f"PHARMACY: SelfCorrectionAntidote failed. Disease ID '{disease_id_to_cure}' not found to cure.")


# The central pharmacy registry.
PHARMACY_REGISTRY: Dict[str, MedicationEffect] = {
    "DeveloperPraise": developer_praise,
    "SelfCorrectionAntidote": self_correction_antidote,
}

def get_medication(name: str) -> MedicationEffect | None:
    """A safe way to get a medication function from the registry."""
    return PHARMACY_REGISTRY.get(name)