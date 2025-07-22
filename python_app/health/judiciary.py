import logging
from enum import Enum
from typing import Dict, Any, Tuple # Added Tuple import

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

    def adjudicate(self, error_info: Dict[str, Any]) -> Tuple[Verdict, Dict[str, Any]]: # Added self parameter
        """
        Analyzes an error and returns a verdict along with relevant data,
        like the ID of the disease to inflict.
        """
        error_type = error_info.get("type")
        error_details = error_info.get("details", {})
        
        logger.info(f"JUDICIARY: Adjudicating error of type '{error_type}'.")
        
        # Step 1: Handle User Mismatch first (if error is external only)
        if error_type is None and error_info.get("user_feedback") == "negative":
            logger.info("Verdict: USER_MISMATCH. No internal error, but user dissatisfied.")
            return Verdict.USER_MISMATCH, {} # No specific data needed for user mismatch

        # Step 2: Determine if the brain "knew better."
        # This is the crucial link to the Brain/NLSE.
        brain_knew_the_truth = self.db_manager.does_brain_know_truth_of(error_details)

        if brain_knew_the_truth:
            logger.warning("Verdict: KNOWLEDGEABLE_ERROR. The AGI should have known better.")
            # Query NLSE for the correct punishment
            disease_id, disease_name = self.db_manager.find_disease_for_error(error_type, error_details)
            if disease_id:
                return Verdict.KNOWLEDGEABLE_ERROR, {"disease_id": disease_id, "disease_name": disease_name}
            else:
                logger.error(f"JUDICIARY: No specific disease protocol found in NLSE for knowledgeable error type '{error_type}'.")
                return Verdict.KNOWLEDGEABLE_ERROR, {"disease_id": None, "disease_name": None}
        else:
            logger.info("Verdict: IGNORANT_ERROR. The AGI erred due to a lack of knowledge.")
            return Verdict.IGNORANT_ERROR, error_details # Pass details for learning target

# Singleton instance for easy access
judiciary = Judiciary()