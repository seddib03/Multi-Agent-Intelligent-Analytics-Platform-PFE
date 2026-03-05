from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal

Sector = Literal["transport", "finance", "retail", "manufacturing", "public", "unknown"]
ExecutionType = Literal["sql", "prediction", "insight", "unknown"]

class ContextOutput(BaseModel):
    intent: str
    sector: Sector
    canonical_metric: Optional[str] = None
    execution_type: ExecutionType
    data_source: Optional[Dict[str, Any]] = None
    model_hint: Optional[Dict[str, Any]] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    schema_version: str
    confidence: float