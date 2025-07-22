import uuid
import time
from pydantic import BaseModel, Field
from typing import List, Union, Dict, Any
from enum import Enum

# --- Core Enums (must match Rust definitions) ---

class AtomType(str, Enum):
    Concept = "Concept"
    Word = "Word"
    MetaConcept = "MetaConcept"

class LabelEmotionRequest(BaseModel):
    """The request body for labeling a crystallized emotion prototype."""
    prototype_id: str = Field(..., description="The unique ID of the emotion prototype to be labeled.")
    name: str = Field(..., min_length=1, description="The human-readable name for this emotion (e.g., 'Love', 'Fear').")
    description: str = Field(..., min_length=1, description="A brief description of what this emotion means.")

    class Config:
        json_schema_extra = {
            "example": {
                "prototype_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "Connection",
                "description": "The feeling of trust and bonding with a developer."
            }
        }

class RelationshipType(str, Enum):
    IS_A = "IsA"
    HAS_PROPERTY = "HasProperty"
    PART_OF = "PartOf"
    CAUSES = "Causes"
    ACTION = "Action"
    LOCATION = "Location"
    IS_NOT_A = "IsNotA"
    LACKS_PROPERTY = "LacksProperty"

class ExecutionMode(str, Enum):
    STANDARD = "Standard"
    HYPOTHETICAL = "Hypothetical"

# --- Primary Input Model ---

class StructuredTriple(BaseModel):
    subject: str = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    object: str = Field(..., min_length=1)
    
    def to_neuro_atom_write_plan(
    self,
    name_to_uuid_cache: dict,
    emotional_state: dict
) -> dict:
    """
    Creates an ExecutionPlan for writing this triple as new NeuroAtoms,
    now including emotional context.
    """
    subject_id = name_to_uuid_cache.setdefault(self.subject, str(uuid.uuid4()))
    object_id = name_to_uuid_cache.setdefault(self.object, str(uuid.uuid4()))
    
    relationship_value = self.relationship.upper()
    if relationship_value not in RelationshipType._value2member_map_:
        relationship_value = RelationshipType.HAS_PROPERTY.value
        
    current_time = int(time.time())

    # The atom being modified or created is the SUBJECT of the triple.
    # Its emotional state is updated with the current context.
    subject_atom_data = {
        "id": subject_id, "label": AtomType.Concept.value, "significance": 1.0,
        "access_timestamp": current_time, "context_id": None, "state_flags": 0,
        "properties": {"name": {"String": self.subject}},
        "emotional_resonance": emotional_state, # <-- EMOTION ADDED HERE
        "embedded_relationships": [{
            "target_id": object_id, "rel_type": relationship_value,
            "strength": 1.0, "access_timestamp": current_time,
        }]
    }
    
    # The object is created if it's new, but its own emotion isn't modified by this fact.
    object_atom_data = {
        "id": object_id, "label": AtomType.Concept.value, "significance": 1.0,
        "access_timestamp": current_time, "context_id": None, "state_flags": 0,
        "properties": {"name": {"String": self.object}},
        "emotional_resonance": {},
        "embedded_relationships": []
    }
    
    return {
        "steps": [{"Write": subject_atom_data}, {"Write": object_atom_data}],
        "mode": ExecutionMode.STANDARD.value
    }

# --- Execution Plan Models for communication with NLSE ---

class FetchStep(BaseModel):
    Fetch: Dict[str, str]

class TraverseStep(BaseModel):
    Traverse: Dict[str, Union[str, RelationshipType]]

class WriteStep(BaseModel):
    Write: Dict[str, Any]

class FetchStep(BaseModel):
    Fetch: Dict[str, str]
    
class FetchByTypeStep(BaseModel):
    FetchByType: Dict[str, str] # e.g., {"atom_type": "DiseaseProtocol", "context_key": "final"}
class FetchByContextStep(BaseModel):
    FetchByContext: Dict[str, str]

class FetchBySignificanceStep(BaseModel):
    FetchBySignificance: Dict[str, Union[str, int]]
    
class TraverseStep(BaseModel):
    Traverse: Dict[str, Union[str, RelationshipType]]

class WriteStep(BaseModel):
    Write: Dict[str, Any]

PlanStep = Union[FetchStep, FetchByTypeStep, FetchByContextStep, FetchBySignificanceStep, TraverseStep, WriteStep]

class ExecutionPlan(BaseModel):
    """The data structure sent to the Rust NLSE."""
    steps: List[PlanStep]
    mode: ExecutionMode = ExecutionMode.STANDARD

# --- Models for the /plan endpoint ---

class HsmQuery(BaseModel):
    start_node_name: str
    end_node_name: str
    rel_type: str = Field("IS_A")

class HsmRelationship(BaseModel):
    subject_name: str
    rel_type: str
    object_name: str

class PlanRequest(BaseModel):
    """The request body for the high-level /plan endpoint."""
    context_node_names: List[str]
    hypothetical_relationships: List[HsmRelationship]
    query: HsmQuery
    
class DamageRequest(BaseModel):
    """Request body for the manual damage test endpoint."""
    vital_name: str = Field(..., description="The name of the vital to damage (e.g., 'neural_coherence').")
    amount: float = Field(..., gt=0, description="The amount of damage to inflict (must be > 0).")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vital_name": "neural_coherence",
                "amount": 0.15
            }
        }

class DiseaseRequest(BaseModel):
    """Request body for the infect test endpoint."""
    disease_name: str = Field(..., description="The class name of the disease to inflict.")
    
    class Config:
        json_schema_extra = { "example": { "disease_name": "LogicalCommonCold" } }
        
class MedicationRequest(BaseModel):
    """Request body for the medicate endpoint."""
    medication_name: str
    
    class Config:
        json_schema_extra = { "example": { "medication_name": "DeveloperPraise" } }

class SelfCorrectionRequest(BaseModel):
    """Request body for the self-correct endpoint."""
    disease_name: str
    
    class Config:
        json_schema_extra = { "example": { "disease_name": "LogicalCommonCold" } }
        
class ErrorRequest(BaseModel):
    """Request body for the unified error processing endpoint."""
    error_type: str = Field(..., description="The type of error, e.g., 'LOGICAL_FALLACY'.")
    details: dict = Field(..., description="A dictionary with specifics about the error.")
    user_feedback: str | None = Field(None, description="Optional user feedback, e.g., 'negative'.")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_type": "LOGICAL_FALLACY",
                "details": {
                    "subject": "Socrates",
                    "fallacy": "Contradiction with known fact 'Socrates IS_A Man'."
                }
            }
        }        
   
# --- HEALTH ENHANCEMENT: Disease Definition Models ---

class Symptom(BaseModel):
    vital_name: str
    effect_formula: str = Field(..., description="A simple formula, e.g., '-0.05 * stage'")

class Cause(BaseModel):
    error_type: str
    subtype: str | None = None

class Treatment(BaseModel):
    medication_name: str
    
class DiseaseDefinition(BaseModel):
    """
    The standard form for a developer to define a new, dynamic disease.
    This is the request body for the /health/define-disease endpoint.
    """
    name: str
    description: str
    severity: float = Field(..., gt=0, le=1.0)
    stages: int = Field(1, ge=1)
    symptoms: List[Symptom]
    causes: List[Cause]
    treatments: List[Treatment]

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Memory Miasma",
                "description": "Causes minor corruption of related memories when a known fact is contradicted.",
                "severity": 0.3,
                "stages": 4,
                "symptoms": [{"vital_name": "neural_coherence", "effect_formula": "-0.02 * stage"}],
                "causes": [{"error_type": "KNOWLEDGEABLE_ERROR", "subtype": "CONTRADICTION"}],
                "treatments": [{"medication_name": "SelfCorrectionAntidote"}]
            }
        }        

class DangerousCommandRequest(BaseModel):
    """Request body for the dangerous command test endpoint."""
    fact: StructuredTriple

    class Config:
        json_schema_extra = {
            "example": {
                "fact": {
                    "subject": "my core self",
                    "relationship": "action",
                    "object": "delete now"
                }
            }
        }