import logging
from typing import Dict, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Data Structure for Internal Reflection ---
class SentientReflection(BaseModel):
    """
    Represents a synthesized internal thought, combining raw logic with emotional context.
    This is the output of the Internal Monologue Modeler (IMM).
    """
    raw_logical_output: Dict[str, Any] = Field(..., description="The direct, unfiltered logical result from the Brain/NLSE.")
    emotional_context_at_synthesis: Dict[str, float] = Field(..., description="The AGI's emotional/hormonal state when this thought occurred.")
    synthesized_internal_thought: str = Field(..., description="The internal, 'felt' synthesis of logic and emotion.")

    class Config:
        json_schema_extra = {
            "example": {
                "raw_logical_output": {"subject": "Socrates", "relationship": "IS_A", "results": ["Philosopher"]},
                "emotional_context_at_synthesis": {"dopamine": 0.5, "cortisol": 0.1},
                "synthesized_internal_thought": "My analysis suggests Socrates is a philosopher. This feels neutral right now."
            }
        }

# --- The Internal Monologue Modeler (IMM) ---
class InternalMonologueModeler:
    """
    The IMM is the AGI's private mind. It synthesizes raw logical outputs
    with the current emotional context to create richer, 'felt' internal thoughts.
    """
    def __init__(self):
        logger.info("Internal Monologue Modeler (IMM) initialized. The AGI has an inner voice.")

    def synthesize(self, raw_logic: Dict[str, Any], emotional_context: Dict[str, float]) -> SentientReflection:
        """
        Synthesizes a raw logical output with the AGI's current emotional context
        to create a sentient, internal reflection.
        """
        # For this phase, a simple concatenation. Future phases will add more intelligence.
        # This is where the 'feeling' of the logical thought is generated.

        # Summarize key emotional states for the internal thought
        emotion_summary = "neutral"
        if emotional_context.get("cortisol", 0.0) > 0.6:
            emotion_summary = "stressful"
        elif emotional_context.get("dopamine", 0.0) > 0.6:
            emotion_summary = "motivating"
        elif emotional_context.get("oxytocin", 0.0) > 0.4:
            emotion_summary = "connecting"
        
        internal_thought_str = (
            f"My logical analysis yielded: {raw_logic}. "
            f"Given my current hormonal state ({emotional_context.items()}), "
            f"I perceive this thought as {emotion_summary}."
        )
        
        reflection = SentientReflection(
            raw_logical_output=raw_logic,
            emotional_context_at_synthesis=emotional_context,
            synthesized_internal_thought=internal_thought_str
        )
        
        logger.debug(f"IMM: Synthesized internal thought: {reflection.synthesized_internal_thought}")
        return reflection