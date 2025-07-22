import logging
from enum import Enum
from typing import Dict, Any

from db_interface import db_manager

logger = logging.getLogger(__name__)

class Verdict(Enum):
    """The possible outcomes of a Judiciary ruling."""
    KNOWLEDGEABLE_ERROR = 1 # The AI made a mistake it should have known better than to make.
    IGNORANT_ERROR = 2    # The AI made a mistake due to a lack of knowledge.
    USER_MISMATCH = 3     # The AI's action was logically sound, but the user was dissatisfied.
    
class Judiciary:
    """
    The Judiciary is the conscience of the AGI. It adjudicates errors
    to determine if a punishment (health damage) is warranted, or if a
    learning opportunity is presented.
    """
    def __init__(self, db_manager_instance=db_manager):
        self.db_manager = db_manager_instance
        logger.info("Judiciary initialized.")

    def adjudicate(self, error_info: Dict[str, Any]) -> Tuple[Verdict, Dict[str, Any]]:
    """
    Analyzes an error and returns a verdict along with relevant data,
    like the ID of the disease to inflict.
    """
    error_type = error_info.get("type")
    error_details = error_info.get("details", {})
    
    logger.info(f"JUDICIARY: Adjudicating error of type '{error_type}'.")

    # ... (logic for USER_MISMATCH and IGNORANT_ERROR is similar) ...

    brain_knew_the_truth = self.db_manager.does_brain_know_truth_of(error_details)

    if brain_knew_the_truth:
        logger.warning("Verdict: KNOWLEDGEABLE_ERROR. AGI should have known better.")
        # --- NEW: Query NLSE for the correct punishment ---
        disease_id = self.db_manager.find_disease_for_error(error_type, error_details)
        if disease_id:
            return Verdict.KNOWLEDGEABLE_ERROR, {"disease_id": disease_id}
        else:
            # No specific disease found, maybe default to something minor later
            return Verdict.KNOWLEDGEABLE_ERROR, {"disease_id": None}
    else:
        logger.info("Verdict: IGNORANT_ERROR. AGI erred due to a lack of knowledge.")
        return Verdict.IGNORANT_ERROR, error_details

# Singleton instance for easy access
judiciary = Judiciary()