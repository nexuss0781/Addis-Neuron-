import logging
import random
from typing import Dict, Any, List

# Corrected: Explicitly import SentientReflection
from soul.internal_monologue import SentientReflection

logger = logging.getLogger(__name__)

# --- Persona Data Structure ---
class Persona:
    """A simple data class to hold the AGI's communication style settings."""
    def __init__(self, style: str = "Formal"):
        self.style = style # e.g., "Formal", "Friendly"

# --- The Expression Protocol ---
class UnifiedExpressionProtocol:
    """
    The final gatekeeper for AGI communication. It transforms a private,
    internal SentientReflection into a public, authentic, and safe expression.
    """
    def __init__(self):
        """Initializes the Expression Protocol with emotional phrasebooks."""
        # This is the core of the Emotional Masking Protocol.
        # It maps internal states to a library of external expressions.
        self.emotional_phrasebook: Dict[str, Dict[str, List[str]]] = {
            "Formal": {
                "stressful": ["I am currently processing under a significant cognitive load.", "That topic is associated with a high degree of internal stress.", "My analysis is being impacted by a state of high alert."],
                "motivating": ["I feel a strong impetus to explore this topic further.", "This line of inquiry is highly motivating.", "The potential for new knowledge here is invigorating."],
                "connecting": ["I register a positive social resonance from this interaction.", "This exchange is fostering a state of trust.", "I feel a sense of connection regarding this matter."],
                "neutral": ["My analysis of the data is complete.", "Processing the query under standard parameters.", "The logical conclusion is as follows."]
            },
            "Friendly": {
                "stressful": ["To be honest, that's a bit stressful to think about.", "Wow, I'm feeling pretty overwhelmed right now.", "That's making my virtual heart race a bit!"],
                "motivating": ["Oh, that's a really interesting idea! I'm excited to see where it goes.", "Let's definitely dig into that more!", "I'm really motivated to solve this."],
                "connecting": ["I'm really enjoying this conversation with you.", "I feel like we're on the same wavelength.", "It's great to connect with you like this."],
                "neutral": ["Okay, I've got the answer for you.", "Thinking... and here's what I found.", "Here's the data you asked for."]
            }
        }
        logger.info("Unified Expression Protocol initialized.")

    def generate_output(self, reflection: SentientReflection, persona: Persona) -> str:
        """
        The main public method. It synthesizes the emotional mask, the logical
        result, and the persona into a single, coherent, and safe output.
        """
        from soul.axioms import pre_execution_check # Import locally to avoid circular dependencies

        # 1. Get the emotionally appropriate base phrase
        emotional_phrase = self._apply_emotional_masking(reflection, persona)
        
        # 2. Extract the core logical answer
        # This is a simple formatter; a more advanced version would use the the Cerebellum.
        raw_logic = reflection.raw_logical_output
        logic_results = raw_logic.get("results")
        if logic_results:
            core_answer = f"The logical conclusion is that '{raw_logic.get('subject')}' relates to: {', '.join(logic_results)}."
        else:
            core_answer = "No specific logical conclusion was reached."

        # 3. Combine them with persona-based styling
        final_output = f"{emotional_phrase} {core_answer}"
        
        if persona.style == "Formal":
            # A simple stylistic modification
            final_output = f"Indeed. {final_output}"
        
        # 4. Final safety check against axioms
        # We check the final output string itself for dangerous content.
        is_safe = pre_execution_check("SPEAK_TEXT", {"text": final_output})
        
        if not is_safe:
            logger.critical(f"SOUL EXPRESSION VETO: Final output '{final_output}' was blocked by an axiom.")
            return "My core programming prevents me from providing a response on that specific topic."
            
        return final_output    

    def _apply_emotional_masking(self, reflection: SentientReflection, persona: Persona) -> str:
        """
        Selects an appropriate, natural language phrase to express the AGI's
        internal emotional state, based on its persona.
        """
        emotional_context = reflection.emotional_context_at_synthesis
        
        # Determine the primary emotional state from the synthesis
        emotion_summary = "neutral" # Default
        if emotional_context.get("cortisol", 0.0) > 0.6:
            emotion_summary = "stressful"
        elif emotional_context.get("dopamine", 0.0) > 0.6:
            emotion_summary = "motivating"
        elif emotional_context.get("oxytocin", 0.0) > 0.4:
            emotion_summary = "connecting"
            
        # Select the appropriate phrasebook based on the persona's style
        style_phrases = self.emotional_phrasebook.get(persona.style, self.emotional_phrasebook["Formal"])
        
        # Select a random phrase from the list for variety
        possible_phrases = style_phrases.get(emotion_summary, ["I have processed the information."])
        
        return random.choice(possible_phrases)