from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal

Intent = Literal["analyze", "compare", "predict", "explain", "other"]

class NLQOutput(BaseModel):
    raw_question: str
    intent: Intent
    metric: Optional[str] = None
    timeframe: Optional[str] = None
    location: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float