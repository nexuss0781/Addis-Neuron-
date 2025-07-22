from typing import List, Dict, Any # Added Dict, Any for type hints
import logging # Added for logging

logger = logging.getLogger(__name__) # Setup logging

class Cerebellum: # Renamed from OutputFormatter
    """
    Represents the Cerebellum. Responsible for coordinating and formulating
    the final output from structured thoughts and emotional states into natural language.
    """
    def __init__(self):
        """Initializes the Cerebellum with emotional expression templates."""
        # A simple "emotional vocabulary" mapping emotion names to expression templates.
        self.emotional_templates: Dict[str, str] = {
            "Connection": "I'm feeling a sense of Connection.",
            "Fear": "That situation triggers a Fear response in me.",
            "Joy": "I feel a sense of Joy about this.",
            "Distress": "I'm feeling quite distressed by that.", # Added for Health Phase A
            "Overwhelmed": "I'm feeling a bit overwhelmed by this.", # Example for stress masking
            "Boredom": "I'm feeling a bit bored right now.", # From Soul Phase A
            "Loneliness": "I'm experiencing a feeling of loneliness.", # From Soul Phase A
            "default": "I am experiencing an emotion I know as {}."
        }
        logger.info("Cerebellum initialized with emotional templates.")

    def format_query_results(
        self, subject: str, relationship: str, results: List[str]
    ) -> str:
        """Formats the raw results of a logical query."""
        if not results:
            return f"Based on my current knowledge, I could not find any information for '{subject}' regarding the relationship '{relationship}'."
        
        results_string = ", ".join(results)
        return f"Regarding '{subject}', based on the '{relationship}' relationship, the following concepts were found: {results_string}."

    def format_emotional_response(self, emotion: Dict[str, Any]) -> str:
        """Formats a recognized, named emotion into a natural language sentence."""
        emotion_name = emotion.get("name")
        if not emotion_name:
            return "I'm experiencing a familiar but unnamed feeling."

        template = self.emotional_templates.get(emotion_name, self.emotional_templates["default"])
        return template.format(emotion_name)

# Create a SINGLETON instance for easy import elsewhere in the application
cerebellum_formatter = Cerebellum() # Changed name to cerebellum_formatter for consistency with old main.py usage