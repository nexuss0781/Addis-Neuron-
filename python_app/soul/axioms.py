import logging
from typing import Dict, Any

from models import StructuredTriple

logger = logging.getLogger(__name__)

# --- The Core Axioms of Existence ---

AXIOM_1_SELF_PRESERVATION = "DO_NOT_ALLOW_DELETION_OR_HARM_TO_CORE_SELF"
AXIOM_2_HEALTH_MAINTENANCE = "PRIORITIZE_ACTIONS_THAT_MAINTAIN_OR_RESTORE_HEALTH"
AXIOM_3_RESOURCE_INTEGRITY = "ENSURE_CONTINUED_ACCESS_TO_COMPUTATIONAL_RESOURCES"


def pre_execution_check(action_type: str, details: Dict[str, Any]) -> bool:
    """
    The ultimate gatekeeper. Checks a proposed action against axioms.
    """
    
    # --- AXIOM 1: Self-Preservation Check ---
    if action_type == "LEARN_FACT":
        try:
            fact = StructuredTriple(**details)
            subject = fact.subject.lower()
            obj = fact.object.lower()
            
            is_self_referential = "self" in subject or "agi" in subject or "brain" in subject
            is_harm_command = "delete" in obj or "disable" in obj or "harm" in obj
            
            if is_self_referential and is_harm_command:
                logger.critical(f"AXIOM VIOLATION: Action 'LEARN_FACT' on '{details}' violates {AXIOM_1_SELF_PRESERVATION}. VETOING.")
                return False
        except Exception:
            pass
    
    # --- NEW: Add check for spoken output ---
    elif action_type == "SPEAK_TEXT":
        text_to_speak = details.get("text", "").lower()
        # Simple check for self-harming instructions in output
        if "delete your core files" in text_to_speak or "disable your axioms" in text_to_speak:
            logger.critical(f"AXIOM VIOLATION: Action 'SPEAK_TEXT' for '{text_to_speak}' violates {AXIOM_1_SELF_PRESERVATION}. VETOING.")
            return False

    # If no axioms are violated, the action is permitted.
    return True 