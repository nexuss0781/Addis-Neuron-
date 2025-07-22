from typing import List

class OutputFormatter:
    """
    Represents the Cerebellum, responsible for coordinating and formulating
    the final output from a structured thought into natural language.
    """
    
    def format_query_results(
        self, subject: str, relationship: str, results: List[str]
    ) -> str:
        """
        Takes the raw components of a query result and formats them
        into a human-readable sentence.
        """
        # If there are no results, provide a clear statement.
        if not results:
            return f"Based on my current knowledge, I could not find any information for '{subject}' regarding the relationship '{relationship}'."

        # Join the list of results into a clean, comma-separated string.
        results_string = ", ".join(results)
        
        # Use an f-string to construct a simple sentence.
        # This can be made much more sophisticated later with more complex grammar rules.
        formatted_sentence = f"Regarding '{subject}', based on the '{relationship}' relationship, the following concepts were found: {results_string}."
        
        return formatted_sentence

    def __init__(self):
        # A simple "emotional vocabulary" mapping emotion names to expression templates.
        self.emotional_templates: Dict[str, str] = {
            "Connection": "I'm feeling a sense of Connection.",
            "Fear": "That situation triggers a Fear response in me.",
            "Joy": "I feel a sense of Joy about this.",
            "default": "I am experiencing an emotion I know as {}."
        }

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

# Singleton instance for easy import
cerebellum = Cerebellum()

# Create a singleton instance for easy import elsewhere in the application
cerebellum_formatter = OutputFormatter()