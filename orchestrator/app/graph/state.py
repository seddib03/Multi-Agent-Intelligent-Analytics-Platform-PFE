from typing import Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum

#Definition of sectors

class SectorEnum(str, Enum):
    TRANSPORT = "Transport"
    FINANCE = "Finance"
    RETAIL = "Retail"
    MANUFACTURING = "Manufacturing"
    PUBLIC = "Public"
    UNKNOWN = "Unknown"

#Definition of intent

class IntentEnum(str, Enum):
    KPI_REQUEST = "kpi_request"
    PREDICTION = "prediction"
    EXPLANATION = "explanation"
    COMPARISON = "comparison"
    DASHBOARD = "dashboard"
    UNKNOWN = "unknown"

#Definition of routing

class RouteEnum(str, Enum):
    TRANSPORT_AGENT = "Transport_Sector_Agent"
    FINANCE_AGENT = "Finance_Sector_Agent"
    RETAIL_AGENT = "Retail_Sector_Agent"
    MANUFACTURING_AGENT = "Manufacturing_Sector_Agent"
    PUBLIC_AGENT = "Public_Sector_Agent"
    GENERIC_ML_AGENT = "Generic_Predictive_Agent"
    INSIGHT_AGENT = "Insight_Agent"
    CLARIFICATION = "Clarification_Needed"

#Orchestrator state

class OrchestratorState(BaseModel):
    #User input
    user_id: str = ""
    query_raw: str = ""
    session_id: str = ""

    #Sector detection result
    sector: SectorEnum = SectorEnum.UNKNOWN
    sector_confidence: float = 0.0
    kpi_mapping: list[str] = Field(default_factory=list)  
    domain_constraints: dict = Field(default_factory=dict)

    #NLQ Agent Result
    intent: IntentEnum = IntentEnum.UNKNOWN
    intent_confidence: float = 0.0
    entities: dict = Field(default_factory=dict)           
    query_structured: dict = Field(default_factory=dict)

    # Routing Decision
    route: Optional[RouteEnum] = None
    route_reason: str = ""                  
    fallback_route: Optional[RouteEnum] = None

    # Agent Result
    agent_response: dict = Field(default_factory=dict)
    agent_error: Optional[str] = None

    # final response
    final_response: str = ""
    response_format: Literal["text", "kpi", "chart", "table"] = "text"

    # Metadata
    errors: list[str] = Field(default_factory=list)
    processing_steps: list[str] = Field(default_factory=list)  
    needs_clarification: bool = False
    clarification_question: str = ""


