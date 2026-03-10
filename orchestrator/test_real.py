import asyncio
from app.graph.state import OrchestratorState
from app.clients.nlq_client import call_detect_sector

async def test():
    state = OrchestratorState(
        user_id='u_test',
        session_id='sess_test',
        query_raw='améliorer l experience des passagers de l aéroport'
    )
    result, route = await call_detect_sector(state)
    print('Secteur   :', result.sector.value)
    print('Confiance :', result.sector_confidence)
    print('KPIs      :', result.kpi_mapping)
    print('Route     :', route)
    print('Steps     :', result.processing_steps)

asyncio.run(test())