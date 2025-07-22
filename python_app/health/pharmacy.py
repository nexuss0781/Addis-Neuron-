from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Callable, Dict, Any

# Use a TYPE_CHECKING block to avoid circular imports.
if TYPE_CHECKING:
    from .manager import HealthManager
    from .pathogens import Disease

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
    disease_name_to_cure = kwargs.get("disease_name")
    if not disease_name_to_cure:
        logger.error("PHARMACY: 'SelfCorrectionAntidote' requires a 'disease_name' to target.")
        return
        
    logger.info(f"PHARMACY: Administering 'SelfCorrectionAntidote' for '{disease_name_to_cure}'.")
    was_cured = manager.cure_disease(disease_name_to_cure)
    
    if was_cured:
        # Recover health after being cured
        manager.heal("neural_coherence", 0.25)
        # Trigger vaccination effect for permanent immunity boost
        manager.vaccinate(disease_name_to_cure)

# The central pharmacy registry.
# This makes the system easily extensible: just add a new entry here.
PHARMACY_REGISTRY: Dict[str, MedicationEffect] = {
    "DeveloperPraise": developer_praise,
    "SelfCorrectionAntidote": self_correction_antidote,
}

def get_medication(name: str) -> MedicationEffect | None:
    """A safe way to get a medication function from the registry."""
    return PHARMACY_REGISTRY.get(name)