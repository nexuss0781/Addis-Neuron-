from pydantic import BaseModel, Field

class StructuredTriple(BaseModel):
    """
    Represents a fundamental, structured fact to be learned by the brain.
    This is the output of the Thalamus and the input for the Hippocampus.
    
    Example: "Socrates is a man" -> {
        subject: "Socrates",
        relationship: "IS_A",
        object: "man"
    }
    """
    subject: str = Field(..., min_length=1, description="The entity the fact is about.")
    relationship: str = Field(..., min_length=1, description="The type of connection between the subject and object (e.g., IS_A, HAS_PROPERTY).")
    object: str = Field(..., min_length=1, description="The entity or attribute related to the subject.")

    class Config:
        # Pydantic V2 uses `json_schema_extra`
        json_schema_extra = {
            "example": {
                "subject": "Socrates",
                "relationship": "IS_A",
                "object": "Man"
            }
        }
