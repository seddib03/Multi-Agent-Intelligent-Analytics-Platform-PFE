import json
import os
import sys
import requests
from dotenv import load_dotenv
from dataset_profiler import profile_dataset

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")


# ----------------------------
# Metadata loader (list or dict)
# ----------------------------
def load_metadata(metadata_path: str | None) -> dict:
    """
    Accepts:
      - None -> {}
      - JSON dict -> returned as-is
      - JSON list (your format) -> converted to dict keyed by column_name
    """
    if not metadata_path:
        return {}

    with open(metadata_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # If already dict
    if isinstance(raw, dict):
        return raw

    # If list -> convert to dict
    if isinstance(raw, list):
        meta_dict = {}
        for item in raw:
            col = item.get("column_name")
            if not col:
                continue
            meta_dict[col] = {
                "business_name": item.get("business_name"),
                "type": item.get("type"),
                "nullable": item.get("nullable"),
                "identifier": item.get("identifier"),
                "format": item.get("format"),
                "enum": item.get("enum"),
                "min": item.get("min"),
                "max": item.get("max"),
                "description": item.get("description"),
            }
        return meta_dict

    return {}


# ----------------------------
# Helpers
# ----------------------------
def extract_available_columns(profile: dict) -> list[str]:
    cols = set()
    for key in ["numerical_columns", "categorical_columns", "datetime_columns"]:
        cols.update(profile.get(key, []))
    return sorted(cols)


def identifier_columns_from_metadata(metadata: dict) -> list[str]:
    ids = []
    for col, info in metadata.items():
        if isinstance(info, dict) and info.get("identifier") is True:
            ids.append(col)
    return ids


def build_prompt(profile: dict, sector: str, metadata: dict) -> str:
    available_cols = extract_available_columns(profile)
    id_cols = identifier_columns_from_metadata(metadata)

    return f"""
You are a Business Intelligence expert specialized in {sector} analytics.

Sector: {sector}

Dataset profile (structure inferred by profiler):
{json.dumps(profile, indent=2)}

Metadata (data dictionary / column meaning):
{json.dumps(metadata, indent=2)}

AVAILABLE COLUMNS (you MUST use only these):
{json.dumps(available_cols, indent=2)}

IMPORTANT RULES:
- Use ONLY columns present in AVAILABLE COLUMNS.
- Do NOT invent new columns, tables, or metrics.
- Allowed aggregations: SUM, AVG, COUNT, DISTINCTCOUNT.
- Prefer DISTINCTCOUNT for identifier columns when counting unique entities.
  Identifier columns detected from metadata: {id_cols}

OUTPUT FORMAT:
Return ONLY valid JSON with this exact schema:

{{
  "kpis": [
    {{"name": "", "column": "", "aggregation": ""}}
  ],
  "charts": [
    {{"type": "", "title": "", "x": "", "y": "", "aggregation": ""}}
  ],
  "insights": ["", ""]
}}

GUIDELINES:
- 4 KPIs maximum
- 3 charts maximum
- If a date column exists, include at least 1 trend chart (line) using it.
- Use categorical columns (gender, marital status, operation type) for bar/pie.
- Use numeric measures for y (premium, coverage days, counts).
""".strip()


def call_openrouter(prompt: str) -> str:
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY missing. Put it in .env")

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def clean_json_text(text: str) -> str:
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        candidate = max(parts, key=len).strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
        t = candidate
    return t.strip()


# ----------------------------
# Validation anti-hallucination
# ----------------------------
def validate_output(output: dict, profile: dict) -> dict:
    available_cols = set(extract_available_columns(profile))
    allowed_aggs = {"SUM", "AVG", "COUNT", "DISTINCTCOUNT"}
    allowed_chart_types = {"bar", "line", "pie", "histogram", "area", "scatter"}

    # Basic keys
    for key in ["kpis", "charts", "insights"]:
        if key not in output:
            raise ValueError(f"Missing key in LLM output: {key}")

    # KPIs validation
    for kpi in output.get("kpis", []):
        col = kpi.get("column")
        agg = (kpi.get("aggregation") or "").upper()
        if col not in available_cols:
            raise ValueError(f"Invalid KPI column: {col}")
        if agg not in allowed_aggs:
            raise ValueError(f"Invalid KPI aggregation: {agg}")
        kpi["aggregation"] = agg

    # Charts validation
    for ch in output.get("charts", []):
        ctype = (ch.get("type") or "").lower()
        x = ch.get("x")
        y = ch.get("y")
        agg = (ch.get("aggregation") or "").upper()

        if not ctype:
            raise ValueError("Chart type missing.")
        if ctype not in allowed_chart_types:
            # allow unknown types but not empty; keep it if you want strictness
            pass

        if x not in available_cols:
            raise ValueError(f"Invalid chart x column: {x}")
        if y not in available_cols:
            raise ValueError(f"Invalid chart y column: {y}")
        if agg not in allowed_aggs:
            raise ValueError(f"Invalid chart aggregation: {agg}")

        ch["aggregation"] = agg

        if not ch.get("title"):
            ch["title"] = f"{ctype.title()} of {y} by {x}"

    # Insights validation (ensure list of strings)
    ins = output.get("insights", [])
    if not isinstance(ins, list) or len(ins) == 0:
        raise ValueError("Insights must be a non-empty list.")
    output["insights"] = [str(i) for i in ins]

    return output


# ----------------------------
# Main generation pipeline
# ----------------------------
def generate_dashboard_config(dataset_path: str, sector: str, metadata_path: str | None) -> dict:
    profile = profile_dataset(dataset_path)
    metadata = load_metadata(metadata_path)

    prompt = build_prompt(profile, sector, metadata)
    raw = call_openrouter(prompt)
    cleaned = clean_json_text(raw)

    parsed = json.loads(cleaned)  # JSON parse validation
    validated = validate_output(parsed, profile)  # anti-hallucination checks

    return validated


def main():
    if len(sys.argv) < 3:
        print("Usage: python insight_agent.py <dataset.csv> <Sector> [metadata.json]")
        print("Example: python insight_agent.py insurance_data.csv Insurance metadata_insurance.json")
        sys.exit(1)

    dataset_path = sys.argv[1]
    sector = sys.argv[2]
    metadata_path = sys.argv[3] if len(sys.argv) >= 4 else None

    config = generate_dashboard_config(dataset_path, sector, metadata_path)

    print(json.dumps(config, indent=4, ensure_ascii=False))

    with open("dashboard_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    print("\n✅ Saved: dashboard_config.json")


if __name__ == "__main__":
    main()
    


