# 🧠 Orchestrator — Multi-Agent Intelligent Analytics Platform

Central coordinator of the Multi-Agent Intelligent Analytics Platform (PFE).
Receives user queries, orchestrates the agent pipeline, and returns structured analytical responses.


## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agent Pipeline](#agent-pipeline)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the API](#running-the-api)
- [API Reference](#api-reference)
- [Routing Logic](#routing-logic)
- [Running Tests](#running-tests)
- [Integration with Other Agents](#integration-with-other-agents)


## Overview
The Orchestrator is the central brain of the platform. It receives a natural language query (optionally with a CSV dataset), runs it through a multi-step LangGraph pipeline, and dispatches it to the most appropriate specialized agent.

## Key responsibilities:

-Detect the business sector from the query (Transport, Finance, Retail, Manufacturing, Public)
-Classify the intent (KPI request, prediction, dashboard, anomaly, etc.)
-Prepare and validate the dataset via the Data Preparation Agent
-Route to the correct downstream agent (sector agent, Insight Agent, Generic ML Agent)
-Return a structured response to the UI

### External Agents (Microservices)

| Agent | Role | Port |
|------|------|------|
| Collègue 1 — NLQ + Context Agent | Sector detection + intent classification | 8000 |
| Collègue 2 — Data Preparation Agent | Dataset cleaning + profiling | 8001 |
| Collègue 3 — Insight Agent | Dashboard generation + KPI analysis | TBD |

## Agent Pipeline
The orchestrator runs a 5-node LangGraph pipeline on every request:
### Node 1 — sector_detection_node
Calls POST /detect-sector on the NLQ Agent.
Fills: state.sector, state.sector_confidence, state.kpi_mapping, state.routing_target.

## Node 2 — nlq_node
Calls POST /chat on the NLQ Agent with the full sector context.
Fills: state.intent, state.intent_confidence, state.requires_orchestrator, state.sub_agent.
If requires_orchestrator=True, the NLQ agent delegates routing back to the orchestrator.

## Node 3 — data_prep_node
If a CSV is provided, calls POST /prepare on the Data Preparation Agent.
Polls for job completion, then retrieves the data profile via GET /profiling-json.
Fills: state.data_profile, state.data_prep_quality, state.data_prep_paths.
Skipped automatically if no CSV is provided.

### Node 4 — routing_node
Applies 7-level routing logic to decide the target agent.
Fills: state.route, state.route_reason, state.fallback_route.
### Node 5 — dispatch_node + response_node
Calls the target agent and formats the final response.

## Project Structure
orchestrator/
├── app/
│   ├── clients/
│   │   ├── nlq_client.py          # HTTP client — Collègue 1 (/detect-sector, /chat)
│   │   ├── data_prep_client.py    # HTTP client — Collègue 2 (/prepare, /profiling-json)
│   │   └── insight_client.py      # HTTP client — Collègue 3 (à venir)
│   ├── graph/
│   │   ├── orchestrator.py        # LangGraph graph definition
│   │   ├── state.py               # OrchestratorState — Pydantic model
│   │   └── nodes/
│   │       ├── sector_detection_node.py
│   │       ├── nlq_node.py
│   │       ├── data_prep_node.py
│   │       ├── routing_node.py
│   │       ├── dispatch_node.py
│   │       └── response_node.py
│   ├── schemas/
│   │   └── input_schema.py        # UserQueryInput
│   ├── utils/
│   │   └── logger.py
│   └── main.py                    # FastAPI entrypoint
├── tests/
│   ├── test_routing.py
│   ├── test_data_prep_integration.py
│   └── test_real.py               # End-to-end manual tests
├── .env
├── .gitignore
├── pytest.ini
└── requirements.txt

## Installation
Prerequisites: Python 3.11, pip
bash# 1. Clone the repository
git clone https://github.com/seddib03/Multi-Agent-Intelligent-Analytics-Platform-PFE.git
cd Multi-Agent-Intelligent-Analytics-Platform-PFE/orchestrator

# 2. Create and activate virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

## requirements.txt (main dependencies):
fastapi
uvicorn
langgraph
langchain
pydantic>=2.0
httpx
python-dotenv
pytest
pytest-asyncio

## Configuration
Create a .env file at the root of orchestrator/:
# Collègue 1 — NLQ + Sector Detection Agent
NLQ_API_URL=http://127.0.0.1:8000

# Collègue 2 — Data Preparation Agent
DATA_PREP_API_URL=http://127.0.0.1:8001

# Collègue 3 — Insight Agent (à compléter)
INSIGHT_API_URL=http://127.0.0.1:8002

# General
APP_ENV=development
LOG_LEVEL=DEBUG

## Running the API
Make sure the other agents are running first, then:

uvicorn app.main:app --reload --port 8080
The orchestrator will be available at: http://localhost:8080
Swagger docs: http://localhost:8080/docs

## API Reference
#### POST /analyze
Main endpoint. Receives a user query and optional dataset, runs the full pipeline.
#### Request — multipart/form-data:
| Field     | Type        | Required | Description               |
| --------- | ----------- | -------- | ------------------------- |
| query_raw | string      | ✅        | Natural language question |
| dataset   | CSV file    | ❌        | Dataset                   |
| metadata  | JSON string | ❌        | Column description        |


## Example metadata:
json{
  "table_name": "insurance",
  "columns": [
    {"name": "Prime", "type": "float", "nullable": false},
    {"name": "datedeb", "type": "date", "nullable": false}
  ],
  "business_rules": ["Prime must be > 0"]
}

## Response — application/json:
json{
  "route": "Finance_Sector_Agent",
  "route_reason": "Niveau 0bis — NLQ routing: finance_agent | intent=prediction.",
  "final_response": "Le taux de sinistralité moyen est de 34.2%...",
  "response_format": "text",
  "needs_clarification": false,
  "clarification_question": "",
  "data_prep_quality": {
    "global": 87.5,
    "completeness": 92.0,
    "validity": 83.0
  },
  "data_prep_paths": {
    "silver": "s3://silver/finance/job_001/data.parquet"
  },
  "agent_response": {},
  "processing_steps": [
    "detect_sector → Finance (92%) | routing_target=finance_agent",
    "nlq_chat → intent=prediction | requires_orchestrator=True | sub_agent=sector_prediction",
    "data_prep_node → COMPLETED | 26383 rows | 15 columns",
    "routing_node → Finance_Sector_Agent",
    "dispatch_node → Finance_Sector_Agent"
  ],
  "errors": []
}

### Example with curl:
bashcurl -X POST http://localhost:8080/analyze \
  -F "query_raw=Analyse les primes d'assurance par région" \
  -F "dataset=@insurance.csv" \
  -F 'metadata={"table_name":"insurance","columns":[]}'
### Example without CSV:
bashcurl -X POST http://localhost:8080/analyze \
  -F "query_raw=Quels sont les KPIs du secteur transport ?"

## Routing Logic
The routing_node applies 7 priority levels to decide the target agent:
| Level   | Condition                | Route               |
| ------- | ------------------------ | ------------------- |
| 0       | routing_target ≥ 80%     | Direct agent        |
| 1       | Sector & intent unknown  | Clarification       |
| 2       | execution_type = insight | Insight Agent       |
| 3       | prediction               | Sector / Generic ML |
| 4       | sql                      | Sector / Generic ML |
| 5       | dashboard/comparison     | Insight Agent       |
| 6       | Known sector             | Sector agent        |
| Default | No rule                  | Clarification       |


## Routing targets:
| routing_target           | Agent               |
| ------------------------ | ------------------- |
| transport_agent          | Transport Agent     |
| finance_agent            | Finance Agent       |
| retail_agent             | Retail Agent        |
| manufacturing_agent      | Manufacturing Agent |
| public_agent             | Public Agent        |
| generic_predictive_agent | Generic ML Agent    |
| insight_agent            | Insight Agent       |


## Running Tests
# All tests
pytest tests/ -v

# Routing logic only (no external API needed)
pytest tests/test_routing.py -v

# Data prep integration (no external API needed — uses mocks)
pytest tests/test_data_prep_integration.py -v

# End-to-end real test (requires Collègue 1 API running on port 8000)
python tests/test_real.py

## Integration with Other Agents
### Collègue 1 — NLQ + Context Agent (port 8000)
The orchestrator calls two endpoints:

- POST /detect-sector — sends user_query, receives sector + confidence + routing_target
- POST /chat — sends user_id + question + sector_context + data_profile, receives intent + requires_orchestrator + sub_agent

When requires_orchestrator: true in the /chat response, the orchestrator takes control of routing using the routing_target and sub_agent fields.

### Collègue 2 — Data Preparation Agent (port 8001)
Called only when the user provides a CSV file.

POST /prepare — sends dataset + metadata, receives job_id
GET /jobs/{job_id}/status — polls until completed
GET /jobs/{job_id}/profiling-json — retrieves the data profile, which is then forwarded to Collègue 1's /chat

### Collègue 3 — Insight Agent (port TBD)
Called when route = Insight_Agent. Integration in progress.
Will receive: data_profile, sector, query_raw, kpi_mapping.

### Team
RoleResponsibilityCollègue 1NLQ Agent + Context/Sector Agent (port 8000)Collègue 2Data Preparation Agent (port 8001)Collègue 3Insight Agent + Dashboard GeneratorOrchestratorLangGraph pipeline + routing + API