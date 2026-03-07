from pydantic import BaseModel, Field
# This module defines the input schema for the orchestrator app, including user query input and orchestrator state.
#User query input
class UserQueryInput(BaseModel):
    #what UI send to Orchestrator
    user_id: str = Field(..., description="Unique Identifier of user")
    session_id: str = Field(..., description="Session Id for memory")
    query: str = Field(..., min_length=1, description="The question in natural language")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "u_001",
                "session_id": "sess_abc123",
                "query": "Show me the transport KPIs in the last mouth"
                
            }
        }