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

# Create a singleton instance for easy import elsewhere in the application
cerebellum_formatter = OutputFormatter()