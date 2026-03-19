import httpx
import os
from dotenv import load_dotenv
from app.graph.state import (
    OrchestratorState, SectorEnum, IntentEnum, RouteEnum
)

load_dotenv()
NLQ_API_URL = os.getenv("NLQ_API_URL", "http://127.0.0.1:8000")

ROUTING_TARGET_MAP = {
    "transport_agent":          RouteEnum.TRANSPORT_AGENT,
    "finance_agent":            RouteEnum.FINANCE_AGENT,
    "retail_agent":             RouteEnum.RETAIL_AGENT,
    "manufacturing_agent":      RouteEnum.MANUFACTURING_AGENT,
    "public_agent":             RouteEnum.PUBLIC_AGENT,
    "generic_predictive_agent": RouteEnum.GENERIC_ML_AGENT,
    "insight_agent":            RouteEnum.INSIGHT_AGENT,
}


def _safe_parse_json(response: httpx.Response, endpoint: str) -> dict:
    """
    Parse JSON en sécurité.
    Lève ValueError avec message clair si : status != 200, body vide, ou non-JSON.
    """
    if response.status_code != 200:
        raise ValueError(
            f"[{endpoint}] HTTP {response.status_code} — "
            f"body: '{response.text[:300]}'"
        )
    if not response.text.strip():
        raise ValueError(
            f"[{endpoint}] Réponse vide — "
            f"le service NLQ est-il bien démarré sur {NLQ_API_URL} ?"
        )
    try:
        return response.json()
    except Exception as e:
        raise ValueError(
            f"[{endpoint}] Réponse non-JSON — "
            f"body: '{response.text[:300]}' | erreur: {e}"
        )


def _format_data_profile_for_nlq(state: OrchestratorState) -> dict | None:
    if not state.data_profile:
        return None

    columns_formatted = []
    for col in state.data_profile.get("numeric_columns", []):
        columns_formatted.append({"name": col, "type": "float", "sample_values": []})
    for col in state.data_profile.get("categorical_columns", []):
        columns_formatted.append({"name": col, "type": "string", "sample_values": []})

    already_added = (
        state.data_profile.get("numeric_columns", []) +
        state.data_profile.get("categorical_columns", [])
    )
    for col in state.data_profile.get("columns", []):
        if col not in already_added:
            columns_formatted.append({"name": col, "type": "unknown", "sample_values": []})

    return {
        "columns":   columns_formatted,
        "row_count": state.data_profile.get("row_count", 0)
    }


def _build_column_metadata(state: OrchestratorState) -> list:
    """
    Construit la liste column_metadata pour /detect-sector
    depuis state.metadata (fourni par l'utilisateur via /analyze).
 
    R2 — Remarque encadrant : column_metadata obligatoire pour
    une détection fiable du secteur.
    """
    column_metadata = []
 
    if not state.metadata:
        return column_metadata
 
    # state.metadata peut être un dict {"columns": [...]} ou une liste
    if isinstance(state.metadata, dict):
        columns = state.metadata.get("columns", [])
    elif isinstance(state.metadata, list):
        columns = state.metadata
    else:
        return column_metadata
 
    for col in columns:
        if not isinstance(col, dict):
            continue
        name = col.get("column_name", col.get("name", ""))
        if not name:
            continue
        column_metadata.append({
            "name":        name,
            "description": col.get("description", col.get("business_name", "")),
            "sample_values": []
        })
 
    return column_metadata

async def call_detect_sector(state: OrchestratorState):
    """
    Appelle POST /detect-sector.
    Retourne (state, suggested_route).
    En cas d'indisponibilité → bypass gracieux, pas de crash.
    """
    try:
        async with httpx.AsyncClient(timeout=130.0) as client:
            response = await client.post(
                f"{NLQ_API_URL}/detect-sector",
                json={"user_query": state.query_raw,
                      "column_metadata": column_metadata,
                      }
            )

        # ✅ Validation avant .json() — évite JSONDecodeError sur body vide
        sector_context = _safe_parse_json(response, "/detect-sector")

        try:
            state.sector = SectorEnum(
                sector_context.get("sector", "unknown").capitalize()
            )
        except ValueError:
            state.sector = SectorEnum.UNKNOWN

        state.sector_confidence = float(sector_context.get("confidence", 0.0))
        state.kpi_mapping       = sector_context.get("kpis", [])
        routing_target          = sector_context.get("routing_target", "")
        state.routing_target    = routing_target
        state.query_structured  = sector_context
        suggested_route         = ROUTING_TARGET_MAP.get(routing_target)

        state.processing_steps.append(
            f"detect_sector → sector={state.sector.value} "
            f"({state.sector_confidence:.0%}) | "
            f"routing_target={routing_target} |"
            f"columns_sent={len(column_metadata)}"
        )
        return state, suggested_route

    except httpx.ConnectError:
        state.errors.append(f"❌ NLQ /detect-sector non disponible à {NLQ_API_URL}")
        state.processing_steps.append("detect_sector → ERREUR connexion (service down)")
        return state, None

    except httpx.TimeoutException:
        state.errors.append("❌ NLQ /detect-sector timeout")
        state.processing_steps.append("detect_sector → ERREUR timeout")
        return state, None

    except ValueError as e:
        # ✅ Attrape body vide, non-JSON, HTTP != 200
        state.errors.append(f"❌ NLQ /detect-sector réponse invalide: {e}")
        state.processing_steps.append("detect_sector → ERREUR réponse invalide")
        return state, None

    except Exception as e:
        state.errors.append(f"❌ NLQ /detect-sector erreur inattendue: {type(e).__name__}: {e}")
        state.processing_steps.append("detect_sector → ERREUR inattendue")
        return state, None


async def call_nlq_chat(
    state: OrchestratorState,
    question: str,
    data_profile: dict = None
) -> OrchestratorState:
    try:
        payload = {
            "user_id":        state.user_id,
            "question":       question,
            "sector_context": state.query_structured,
        }
        nlq_profile = data_profile or _format_data_profile_for_nlq(state)
        if nlq_profile:
            payload["data_profile"] = nlq_profile

        async with httpx.AsyncClient(timeout=150.0) as client:
            response = await client.post(f"{NLQ_API_URL}/chat", json=payload)

        # ✅ Validation avant .json()
        chat_result = _safe_parse_json(response, "/chat")

        state.agent_response   = chat_result
        state.final_response   = chat_result.get("answer", "")
        state.canonical_metric = chat_result.get("kpi_referenced", "")

        intent_raw = chat_result.get("intent", "unknown")
        try:
            state.intent = IntentEnum(intent_raw.lower())
        except ValueError:
            state.intent = IntentEnum.UNKNOWN
        state.intent_confidence     = float(chat_result.get("confidence", 0.0))
        state.requires_orchestrator = chat_result.get("requires_orchestrator", False)
        state.sub_agent             = chat_result.get("sub_agent", "")

        if chat_result.get("routing_target"):
            state.routing_target = chat_result["routing_target"]

        suggested_chart       = chat_result.get("suggested_chart", "")
        state.response_format = "chart" if suggested_chart else "text"

        state.processing_steps.append(
            f"nlq_chat → intent={state.intent.value} | "
            f"requires_orchestrator={state.requires_orchestrator} | "
            f"sub_agent={state.sub_agent or 'none'} | "
            f"kpi={state.canonical_metric}"
        )

    except httpx.ConnectError:
        state.errors.append(f"❌ NLQ /chat non disponible à {NLQ_API_URL}")
        state.processing_steps.append("nlq_chat → ERREUR connexion")
    except httpx.TimeoutException:
        state.errors.append("❌ NLQ /chat timeout")
        state.processing_steps.append("nlq_chat → ERREUR timeout")
    except ValueError as e:
        state.errors.append(f"❌ NLQ /chat réponse invalide: {e}")
        state.processing_steps.append("nlq_chat → ERREUR réponse invalide")
    except Exception as e:
        state.errors.append(f"❌ NLQ /chat erreur inattendue: {type(e).__name__}: {e}")
        state.processing_steps.append("nlq_chat → ERREUR inattendue")

    return state


async def reset_nlq_session(user_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{NLQ_API_URL}/chat/reset",
                json={"user_id": user_id}
            )
        return _safe_parse_json(response, "/chat/reset")
    except Exception as e:
        return {"error": str(e)}