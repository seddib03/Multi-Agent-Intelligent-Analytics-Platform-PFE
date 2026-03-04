from app.graph.state import OrchestratorState, RouteEnum
from app.mocks.transport_agent import mock_transport_agent
from app.mocks.finance_agent import mock_finance_agent
from app.mocks.generic_agent import mock_generic_agent
from app.mocks.insight_agent import mock_insight_agent
from app.mocks.clarification_agent import mock_clarification_agent


AGENT_REGISTRY = {
    RouteEnum.TRANSPORT_AGENT:      mock_transport_agent,
    RouteEnum.FINANCE_AGENT:        mock_finance_agent,
    RouteEnum.RETAIL_AGENT:         mock_finance_agent,       # Réutilise Finance pour l'instant
    RouteEnum.MANUFACTURING_AGENT:  mock_generic_agent,
    RouteEnum.PUBLIC_AGENT:         mock_generic_agent,
    RouteEnum.GENERIC_ML_AGENT:     mock_generic_agent,
    RouteEnum.INSIGHT_AGENT:        mock_insight_agent,
    RouteEnum.CLARIFICATION:        mock_clarification_agent,
}

def dispatch(state: OrchestratorState) -> dict:
    """
    Calls the appropriate mock agent based on the route decided by the orchestrator.
    """
    agent_fn = AGENT_REGISTRY.get(state.route, mock_clarification_agent)
    return agent_fn(state)