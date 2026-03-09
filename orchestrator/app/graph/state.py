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

# context Agent execution type

class ExecutionTypeEnum(str, Enum):
    SQL        = "sql"
    PREDICTION = "prediction"
    INSIGHT    = "insight"
    UNKNOWN    = "unknown"

# Data preparation for agent execution
class DataPrepStatusEnum(str, Enum):
    NOT_STARTED        = "not_started"
    RUNNING            = "running"
    WAITING_VALIDATION = "waiting_validation"  # Human-in-the-Loop
    COMPLETED          = "completed"
    FAILED             = "failed"

#Orchestrator state

class OrchestratorState(BaseModel):
    #User input
    user_id: str = ""
    query_raw: str = ""
    session_id: str = ""
    csv_path: str = ""
    metadata: dict = Field(default_factory=dict)

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

    # From context Agent
    canonical_metrics: str = ""
    execution_type: ExecutionTypeEnum = ExecutionTypeEnum.UNKNOWN
    data_source: dict = Field(default_factory=dict)
    metric_raw: str = ""
    timeframe: str = ""
    location: str = ""
    routing_target: str = ""

    # Data preparation job status
    data_prep_job_id: str = "" 
    # Unique job ID returned by POST /prepare
    # Used for all subsequent calls (/status, /validate, /profiling-json)
    data_prep_status: DataPrepStatusEnum = DataPrepStatusEnum.NOT_STARTED
    # Lifecycle: not_started → running → waiting_validation → completed
    data_prep_paths: dict = Field(default_factory=dict)
    # MinIO paths after cleaning
    # ex: {"silver": "s3://silver/transport/job_id/data.parquet",
    #       "gold":   "s3://gold/transport/job_id/"}

    data_prep_quality: dict = Field(default_factory=dict)
    # Scores qualité AVANT nettoyage
    # ex: {"global": 0.85, "completeness": 0.9, "validity": 0.8}

    data_prep_error: Optional[str] = None
    # Error message if pipeline fails
    data_profile: dict = Field(default_factory=dict)
    # Dataset profile retrieved via /profiling-json
    # Passed to NLQ Agent via POST /chat to generate precise SQL
    # ex: {"row_count": 500, "columns": ["flight_id", "delay_minutes"],
    #       "numeric_columns": [...], "quality_score": 85.0}


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


