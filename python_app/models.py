from pydantic import BaseModel, Field
from typing import List # <-- ADD THIS IMPORT

class StructuredTriple(BaseModel):
    subject: str = Field(..., min_length=1, description="The entity the fact is about.")
    relationship: str = Field(..., min_length=1, description="The type of connection between the subject and object (e.g., IS_A, HAS_PROPERTY).")
    object: str = Field(..., min_length=1, description="The entity or attribute related to the subject.")

    class Config:
        json_schema_extra = {
            "example": {
                "subject": "Socrates",
                "relationship": "IS_A",
                "object": "Man"
            }
        }

class HsmQuery(BaseModel):
    start_node_name: str
    end_node_name: str
    rel_type: str = Field("IS_A", description="The relationship type to check for a path.")

class HsmRelationship(BaseModel):
    subject_name: str
    rel_type: str
    object_name: str

class PlanRequest(BaseModel):
    context_node_names: List[str] = Field(..., description="A list of concept names to form the 'base reality'.")
    hypothetical_relationships: List[HsmRelationship] = Field(..., description="A list of 'what-if' facts to add to the model.")
    query: HsmQuery = Field(..., description="The query to run against the hypothetical model.")

    class Config:
        json_schema_extra = {
            "example": {
                "context_node_names": ["Socrates", "Man"],
                "hypothetical_relationships": [
                    {
                        "subject_name": "Man",
                        "rel_type": "IS_A",
                        "object_name": "Immortal"
                    }
                ],
                "query": {
                    "start_node_name": "Socrates",
                    "end_node_name": "Immortal",
                    "rel_type": "IS_A"
                }
            }
        }
