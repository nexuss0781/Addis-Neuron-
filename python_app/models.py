import uuid
import time
from pydantic import BaseModel, Field
from typing import List # <-- ADD THIS IMPORT

class StructuredTriple(BaseModel):
    subject: str = Field(..., min_length=1, description="The entity the fact is about.")
    relationship: str = Field(..., min_length=1, description="The type of connection between the subject and object (e.g., IS_A, HAS_PROPERTY).")
    object: str = Field(..., min_length=1, description="The entity or attribute related to the subject.")

    def to_neuro_atom_write_plan(self, name_to_uuid_cache: dict) -> dict:
        """
        Creates an ExecutionPlan for writing this triple as a NeuroAtom.
        This is a temporary helper to centralize the creation logic.
        """
        subject_id = name_to_uuid_cache.setdefault(self.subject, str(uuid.uuid4()))
        object_id = name_to_uuid_cache.setdefault(self.object, str(uuid.uuid4()))
        
        relationship_value = self.relationship.upper()
        # Ensure the relationship type exists in our Enum
        if not hasattr(RelationshipType, relationship_value):
            relationship_value = "HAS_PROPERTY" # Default fallback
            
        new_atom_data = {
            "id": subject_id, "label": AtomType.Concept.value, "significance": 1.0,
            "access_timestamp": int(time.time()), "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": self.subject}}, "emotional_resonance": {},
            "embedded_relationships": [{
                "target_id": object_id,
                "rel_type": relationship_value,
                "strength": 1.0, "access_timestamp": int(time.time()),
            }]
        }
        # Another atom for the object, if it's new
        object_atom_data = {
            "id": object_id, "label": AtomType.Concept.value, "significance": 1.0,
            "access_timestamp": int(time.time()), "context_id": None, "state_flags": 0,
            "properties": {"name": {"String": self.object}}, "emotional_resonance": {},
            "embedded_relationships": []
        }
        
        return {
            "steps": [
                {"Write": new_atom_data},
                {"Write": object_atom_data},
            ]
        }


    class Config:
        json_schema_extra = {
            "example": {
                "subject": "Socrates",
                "relationship": "IS_A",
                "object": "Man"
            }
        }

class AtomType(str, Enum):
    Concept = "Concept"
    Word = "Word"
    MetaConcept = "MetaConcept"

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
