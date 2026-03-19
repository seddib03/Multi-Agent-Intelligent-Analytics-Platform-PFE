from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd

# Import de la logique métier originale
from dashboard_generator import generate_dashboard_data

app = FastAPI(title="Insight Agent API")

# Colonnes techniques à exclure
EXCLUDE_COLS = {
    "unnamed: 0", "unnamed:0", "id", "index", "row_id", "uuid"
}

# Colonnes numériques à forte valeur métier
HIGH_VALUE_NUMERIC_KEYWORDS = [
    "revenue", "sales", "amount", "price", "cost", "profit", "loss",
    "premium", "distance", "delay", "duration", "time_spent", "score",
    "age", "salary", "quantity", "volume", "rate"
]

# Colonnes numériques intéressantes mais secondaires
MEDIUM_VALUE_NUMERIC_KEYWORDS = [
    "count", "total", "avg", "mean", "minutes", "hours", "days", "year"
]

# Colonnes moins prioritaires
LOW_PRIORITY_NUMERIC_KEYWORDS = [
    "wifi", "comfort", "service", "cleanliness", "entertainment",
    "convenient", "booking", "location", "boarding", "checkin", "seat",
    "food", "baggage", "room"
]

# Colonnes catégorielles utiles
HIGH_VALUE_CATEGORY_KEYWORDS = [
    "status", "satisfaction", "class", "category", "segment", "gender",
    "customer", "client", "type", "region", "city", "country",
    "department", "product", "travel", "route"
]


# ── Schémas Pydantic ──────────────────────────────────────────────────────────
class SectorContext(BaseModel):
    sector: str
    context: Optional[str] = None
    recommended_kpis: Optional[List[str]] = []
    recommended_charts: Optional[List[str]] = []
    dashboard_focus: Optional[str] = None


class DashboardRequest(BaseModel):
    sector_context: SectorContext
    dataset_path: str
    metadata_path: Optional[str] = None
    user_query: Optional[str] = None


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Insight Agent API running"}


# ── Helpers fallback dynamique ────────────────────────────────────────────────
def _normalize_col_name(name: str) -> str:
    return name.lower().strip().replace(" ", "_")


def _is_excluded(col: str) -> bool:
    norm = _normalize_col_name(col)
    return norm in {c.replace(" ", "_") for c in EXCLUDE_COLS}


def _detect_date_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        col_lower = col.lower()

        looks_like_date = (
            "date" in col_lower
            or "day" in col_lower
            or "month" in col_lower
            or "year" in col_lower
            or col_lower.startswith("dt")
            or "timestamp" in col_lower
            or "created" in col_lower
            or "updated" in col_lower
            or "start" in col_lower
            or "end" in col_lower
        )

        if not looks_like_date:
            continue

        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > 0.7 * len(df):
                return col
        except Exception:
            continue

    return None


def _score_numeric_column(col: str, user_query: str = "") -> int:
    col_lower = col.lower()
    query_lower = user_query.lower() if user_query else ""
    score = 0

    if _is_excluded(col):
        return -999

    for kw in HIGH_VALUE_NUMERIC_KEYWORDS:
        if kw in col_lower:
            score += 10

    for kw in MEDIUM_VALUE_NUMERIC_KEYWORDS:
        if kw in col_lower:
            score += 4

    for kw in LOW_PRIORITY_NUMERIC_KEYWORDS:
        if kw in col_lower:
            score -= 3

    if query_lower and col_lower in query_lower:
        score += 15
    else:
        for token in col_lower.replace("/", " ").replace("_", " ").split():
            if token and token in query_lower:
                score += 4

    score += 2
    return score


def _score_category_column(col: str, user_query: str = "") -> int:
    col_lower = col.lower()
    query_lower = user_query.lower() if user_query else ""
    score = 0

    if _is_excluded(col):
        return -999

    for kw in HIGH_VALUE_CATEGORY_KEYWORDS:
        if kw in col_lower:
            score += 8

    if query_lower and col_lower in query_lower:
        score += 12
    else:
        for token in col_lower.replace("/", " ").replace("_", " ").split():
            if token and token in query_lower:
                score += 4

    return score


def _pick_count_column(df: pd.DataFrame) -> Optional[str]:
    preferred = [
        "id", "customer_id", "client_id", "order_id", "trip_id",
        "flight_id", "invoice_id", "num_contrat", "num_facture"
    ]
    normalized_map = {_normalize_col_name(c): c for c in df.columns}

    for p in preferred:
        if p in normalized_map:
            return normalized_map[p]

    for col in df.columns:
        if df[col].notna().sum() > 0:
            return col

    return None


def _choose_aggregation_for_numeric(col: str) -> str:
    col_lower = col.lower()

    if any(k in col_lower for k in [
        "revenue", "sales", "amount", "price", "cost", "profit", "loss",
        "premium", "quantity", "volume"
    ]):
        return "SUM"

    if any(k in col_lower for k in [
        "count", "total", "num", "number"
    ]):
        return "COUNT"

    return "AVG"


def _build_dynamic_config(df: pd.DataFrame, sector_context: SectorContext, user_query: str = "") -> dict:
    numeric_candidates = []
    for col in df.select_dtypes(include="number").columns:
        if not _is_excluded(col):
            numeric_candidates.append((col, _score_numeric_column(col, user_query)))

    category_candidates = []
    for col in df.select_dtypes(include=["object", "category"]).columns:
        if not _is_excluded(col):
            category_candidates.append((col, _score_category_column(col, user_query)))

    numeric_candidates.sort(key=lambda x: x[1], reverse=True)
    category_candidates.sort(key=lambda x: x[1], reverse=True)

    numeric_cols = [col for col, score in numeric_candidates if score > -999][:6]
    category_cols = [col for col, score in category_candidates if score > -999][:6]

    date_col = _detect_date_column(df)
    count_col = _pick_count_column(df)

    kpis = []

    # 3 meilleurs KPI numériques
    for col in numeric_cols[:3]:
        kpis.append({
            "name": col,
            "column": col,
            "aggregation": _choose_aggregation_for_numeric(col),
            "format": "number",
            "unit": ""
        })

    # KPI count global
    if count_col:
        kpis.append({
            "name": "Total Records",
            "column": count_col,
            "aggregation": "COUNT",
            "format": "number",
            "unit": ""
        })

    # Compléter si besoin
    used_kpi_cols = {k["column"] for k in kpis}
    for col in numeric_cols[3:]:
        if len(kpis) >= 4:
            break
        if col not in used_kpi_cols:
            kpis.append({
                "name": col,
                "column": col,
                "aggregation": _choose_aggregation_for_numeric(col),
                "format": "number",
                "unit": ""
            })

    charts = []

    # Chart 1 : meilleure mesure par meilleure catégorie
    if category_cols and numeric_cols:
        first_num = numeric_cols[0]
        charts.append({
            "title": f"{first_num} par {category_cols[0]}",
            "type": "bar",
            "x": category_cols[0],
            "y": first_num,
            "aggregation": _choose_aggregation_for_numeric(first_num)
        })

    # Chart 2 : trend si vraie date, sinon autre bar chart pertinent
    if date_col and numeric_cols:
        first_num = numeric_cols[0]
        charts.append({
            "title": f"Evolution de {first_num}",
            "type": "line",
            "x": date_col,
            "y": first_num,
            "aggregation": _choose_aggregation_for_numeric(first_num)
        })
    elif len(category_cols) >= 2 and numeric_cols:
        first_num = numeric_cols[0]
        charts.append({
            "title": f"{first_num} par {category_cols[1]}",
            "type": "bar",
            "x": category_cols[1],
            "y": first_num,
            "aggregation": _choose_aggregation_for_numeric(first_num)
        })
    elif category_cols and len(numeric_cols) >= 2:
        second_num = numeric_cols[1]
        charts.append({
            "title": f"{second_num} par {category_cols[0]}",
            "type": "bar",
            "x": category_cols[0],
            "y": second_num,
            "aggregation": _choose_aggregation_for_numeric(second_num)
        })

    # Chart 3 : répartition
    if category_cols and count_col:
        charts.append({
            "title": f"Répartition par {category_cols[0]}",
            "type": "pie",
            "x": category_cols[0],
            "y": count_col,
            "aggregation": "COUNT"
        })

    return {"kpis": kpis, "charts": charts}


def _compute_kpi(df: pd.DataFrame, kpi: dict) -> dict:
    col = kpi["column"]
    agg = kpi["aggregation"].upper()

    if col not in df.columns:
        return {**kpi, "value": None}

    try:
        if agg == "SUM":
            value = df[col].sum()
        elif agg == "AVG":
            value = round(df[col].mean(), 2)
        elif agg == "COUNT":
            value = int(df[col].count())
        elif agg == "DISTINCTCOUNT":
            value = int(df[col].nunique())
        else:
            value = None

        if value is not None and hasattr(value, "item"):
            value = value.item()

    except Exception:
        value = None

    return {**kpi, "value": value}


def _prepare_chart(df: pd.DataFrame, chart: dict) -> dict:
    x = chart["x"]
    y = chart["y"]
    agg = chart["aggregation"].upper()

    if x not in df.columns or y not in df.columns:
        return {**chart, "data": [], "dataKeys": ["value"]}

    try:
        work_df = df.copy()

        if chart["type"].lower() == "line":
            x_lower = x.lower()
            looks_like_date = (
                "date" in x_lower
                or "day" in x_lower
                or "month" in x_lower
                or "year" in x_lower
                or x_lower.startswith("dt")
                or "timestamp" in x_lower
                or "created" in x_lower
                or "updated" in x_lower
                or "start" in x_lower
                or "end" in x_lower
            )

            if looks_like_date:
                try:
                    parsed = pd.to_datetime(work_df[x], errors="coerce")
                    if parsed.notna().sum() > 0.7 * len(work_df):
                        work_df[x] = parsed
                        work_df = work_df.dropna(subset=[x])
                except Exception:
                    pass

        if agg == "SUM":
            grouped = work_df.groupby(x, dropna=False)[y].sum().reset_index()
        elif agg == "AVG":
            grouped = work_df.groupby(x, dropna=False)[y].mean().reset_index()
        elif agg == "DISTINCTCOUNT":
            grouped = work_df.groupby(x, dropna=False)[y].nunique().reset_index()
        else:
            grouped = work_df.groupby(x, dropna=False)[y].count().reset_index()

        data = []
        for _, row in grouped.head(15).iterrows():
            x_value = row[x]
            y_value = row[y]

            if hasattr(x_value, "isoformat"):
                x_value = x_value.isoformat()
            else:
                x_value = str(x_value)

            data.append({
                "name": x_value,
                "value": round(float(y_value), 2)
            })

    except Exception:
        data = []

    return {**chart, "data": data, "dataKeys": ["value"]}


def _format_original_charts(charts_raw: list) -> list:
    formatted = []

    for c in charts_raw:
        formatted.append({
            "type": c.get("type", "bar"),
            "title": c.get("title", ""),
            "data": c.get("data", []),
            "dataKeys": c.get("dataKeys") or c.get("keys") or ["value"],
        })

    return formatted


# ── Endpoint principal ────────────────────────────────────────────────────────
@app.post("/generate-dashboard")
def generate_dashboard(request: DashboardRequest):
    try:
        df = pd.read_csv(request.dataset_path)
    except Exception as e:
        return {"status": "error", "detail": f"Cannot read CSV: {e}"}

    dashboard_mode = "specific" if request.user_query else "general"
    sector = (request.sector_context.sector or "").lower().strip()

    # Cas spécial assurance uniquement
    if sector == "insurance":
        try:
            dashboard_data = generate_dashboard_data(
                config_path="dashboard_config.json",
                dataset_path=request.dataset_path
            )

            kpis = dashboard_data.get("kpis", [])
            charts = _format_original_charts(dashboard_data.get("charts", []))
            insights = dashboard_data.get("insights", [
                f"{k.get('name', '')}: {k.get('value', '')}" for k in kpis
            ])

            return {
                "status": "success",
                "agent": "insight_agent_pipeline",
                "dashboard_mode": dashboard_mode,
                "sector": request.sector_context.sector,
                "template": dashboard_data.get("template", "config_based"),
                "title": request.sector_context.dashboard_focus or f"{request.sector_context.sector} Dashboard",
                "kpis": kpis,
                "charts": charts,
                "insights": insights,
                "source": "dashboard_config",
            }

        except Exception as e:
            print(f"[INFO] insurance config incompatible ({e}) → fallback dynamique", flush=True)

    # Tous les autres secteurs -> fallback dynamique direct
    config = _build_dynamic_config(df, request.sector_context, request.user_query or "")

    computed_kpis = [_compute_kpi(df, k) for k in config["kpis"]]
    kpis = [k for k in computed_kpis if k["value"] is not None]

    charts = [_prepare_chart(df, c) for c in config["charts"]]
    insights = [f"{k['name']} : {k['value']}".strip() for k in kpis]

    return {
        "status": "success",
        "agent": "insight_agent_pipeline",
        "dashboard_mode": dashboard_mode,
        "sector": request.sector_context.sector,
        "template": "dynamic_fallback",
        "title": request.sector_context.dashboard_focus or f"{request.sector_context.sector} Dashboard",
        "kpis": kpis,
        "charts": charts,
        "insights": insights,
        "source": "dynamic_fallback",
    }
    