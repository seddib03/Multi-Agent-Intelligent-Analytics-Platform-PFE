# DXC Intelligence Analytics Platform — Sprint 1

## Structure
```
sprint1/
├── agents/
│   ├── __init__.py
│   ├── context_sector_agent.py   ← ContextSectorAgent (LangGraph StateGraph)
│   └── nlq_agent.py              ← NLQAgent (LangGraph StateGraph)
├── api/
│   ├── __init__.py
│   ├── main.py                   ← FastAPI (4 endpoints)
│   └── schemas.py                ← Pydantic V2 schemas
├── config/
│   └── kpi_config.yaml           ← KPIs par secteur
├── tests/
│   ├── __init__.py
│   ├── test_sprint1.py           ← Tests agents LangGraph
│   └── test_api.py               ← Tests API FastAPI
├── .env.template
├── conftest.py
├── pytest.ini
└── requirements.txt
```

## Installation
```bash
pip install -r requirements.txt
cp .env.template .env
# Éditer .env et ajouter OPENROUTER_API_KEY
```

## Lancer l'API
```bash
uvicorn api.main:app --reload --port 8000
# Swagger : http://localhost:8000/docs
```

## Lancer les tests
```bash
pytest tests/ -v
pytest tests/test_sprint1.py -v
pytest tests/test_api.py -v
```
