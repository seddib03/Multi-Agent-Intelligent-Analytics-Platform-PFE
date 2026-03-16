from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd

app = FastAPI(title="Insight Agent API")

EXCLUDE_COLS = {"unnamed: 0", "id", "index", "unnamed:0"}

class SectorContext(BaseModel):
    sector: str
    context: Optional[str] = None
    recommended_kpis: Optional[List[str]] = []
    recommended_charts: Optional[List[str]] = []
    dashboard_focus: Optional[str] = None


class DashboardRequest(BaseModel):
    sector_context: SectorContext
    dataset_path: str
    metadata_path: str
    user_query: Optional[str] = None


@app.get("/")
def root():
    return {"message": "Insight Agent API running"}


def _build_dynamic_config(df: pd.DataFrame, sector_context: SectorContext, user_query: str = "") -> dict:
    # Filtrer les colonnes non pertinentes
    numeric_cols  = [c for c in df.select_dtypes(include="number").columns
                     if c.lower().replace(" ", "") not in EXCLUDE_COLS]
    category_cols = df.select_dtypes(include="object").columns.tolist()

    # Si une question spécifique mentionne une colonne → la prioriser
    query_lower = user_query.lower() if user_query else ""
    prioritized_num = []
    prioritized_cat = []
    for col in numeric_cols:
        if col.lower() in query_lower:
            prioritized_num.insert(0, col)
        else:
            prioritized_num.append(col)
    for col in category_cols:
        if col.lower() in query_lower:
            prioritized_cat.insert(0, col)
        else:
            prioritized_cat.append(col)

    numeric_cols  = prioritized_num[:5]
    category_cols = prioritized_cat

    kpis = []
    for col in numeric_cols[:4]:
        kpis.append({
            "name":        col,
            "column":      col,
            "aggregation": "AVG",
            "format":      "number",
            "unit":        "",
        })
    # Ajouter count pour colonnes catégorielles si question spécifique
    for col in category_cols[:1]:
        kpis.append({
            "name":        f"Nb {col}",
            "column":      col,
            "aggregation": "DISTINCTCOUNT",
            "format":      "number",
            "unit":        "",
        })

    charts = []
    if category_cols and numeric_cols:
        charts.append({
            "title":       f"{numeric_cols[0]} par {category_cols[0]}",
            "type":        "bar",
            "x":           category_cols[0],
            "y":           numeric_cols[0],
            "aggregation": "AVG",
        })
    if len(numeric_cols) >= 2:
        charts.append({
            "title":       f"Evolution de {numeric_cols[1]}",
            "type":        "line",
            "x":           numeric_cols[0],
            "y":           numeric_cols[1],
            "aggregation": "AVG",
        })
    if category_cols and numeric_cols:
        charts.append({
            "title":       f"Répartition par {category_cols[0]}",
            "type":        "pie",
            "x":           category_cols[0],
            "y":           numeric_cols[0],
            "aggregation": "COUNT",
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
    x   = chart["x"]
    y   = chart["y"]
    agg = chart["aggregation"].upper()
    if x not in df.columns or y not in df.columns:
        return {**chart, "data": [], "dataKeys": ["value"]}
    try:
        if agg == "SUM":
            grouped = df.groupby(x)[y].sum().reset_index()
        elif agg == "AVG":
            grouped = df.groupby(x)[y].mean().reset_index()
        else:
            grouped = df.groupby(x)[y].count().reset_index()
        grouped = grouped.head(15)
        data = [{"name": str(row[x]), "value": round(float(row[y]), 2)} for _, row in grouped.iterrows()]
    except Exception:
        data = []
    return {**chart, "data": data, "dataKeys": ["value"]}


@app.post("/generate-dashboard")
def generate_dashboard(request: DashboardRequest):
    try:
        df = pd.read_csv(request.dataset_path)
    except Exception as e:
        return {"status": "error", "detail": f"Cannot read CSV: {e}"}

    config = _build_dynamic_config(df, request.sector_context, request.user_query or "")

    kpis   = [_compute_kpi(df, k) for k in config["kpis"] if _compute_kpi(df, k)["value"] is not None]
    charts = [_prepare_chart(df, c) for c in config["charts"]]

    insights = [f"{k['name']} moyen : {k['value']} {k.get('unit','')}" for k in kpis]

    return {
        "status":         "success",
        "agent":          "insight_agent_pipeline",
        "dashboard_mode": "specific" if request.user_query else "general",
        "sector":         request.sector_context.sector,
        "template":       "dynamic",
        "title":          request.sector_context.dashboard_focus or f"{request.sector_context.sector} Dashboard",
        "kpis":           kpis,
        "charts":         charts,
        "insights":       insights,
    }