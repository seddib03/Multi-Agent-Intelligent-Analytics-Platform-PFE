import json
import pandas as pd


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_dataset(path):
    return pd.read_csv(path)


def compute_kpi(df, kpi):
    column = kpi["column"]
    aggregation = kpi["aggregation"].upper()

    if aggregation == "SUM":
        value = df[column].sum()

    elif aggregation == "AVG":
        value = round(df[column].mean(), 2)

    elif aggregation == "COUNT":
        value = df[column].count()

    elif aggregation == "DISTINCTCOUNT":
        value = df[column].nunique()

    else:
        value = None

    # Convert pandas/numpy value to native Python type
    if value is not None and hasattr(value, "item"):
        value = value.item()

    return value


def prepare_chart_data(df, chart):
    chart_type = chart["type"].lower()
    x = chart["x"]
    y = chart["y"]
    aggregation = chart["aggregation"].upper()

    if aggregation == "SUM":
        grouped = df.groupby(x)[y].sum().reset_index()

    elif aggregation == "AVG":
        grouped = df.groupby(x)[y].mean().reset_index()

    elif aggregation == "COUNT":
        grouped = df.groupby(x)[y].count().reset_index()

    elif aggregation == "DISTINCTCOUNT":
        grouped = df.groupby(x)[y].nunique().reset_index()

    else:
        grouped = None

    data_records = []

    if grouped is not None:
        for record in grouped.to_dict(orient="records"):
            clean_record = {}
            for key, value in record.items():
                if hasattr(value, "item"):
                    clean_record[key] = value.item()
                else:
                    clean_record[key] = value
            data_records.append(clean_record)

    return {
        "title": chart["title"],
        "type": chart_type,
        "x": x,
        "y": y,
        "aggregation": aggregation,
        "data": data_records
    }


def choose_template(config):
    kpi_count = len(config.get("kpis", []))
    chart_count = len(config.get("charts", []))
    chart_types = [chart.get("type", "").lower() for chart in config.get("charts", [])]

    has_trend_chart = "line" in chart_types or "area" in chart_types

    # Executive dashboard rule
    if kpi_count >= 3 and has_trend_chart and chart_count <= 3:
        return "templates/executive_dashboard.json"

    # Otherwise fallback to operational
    return "templates/operational_dashboard.json"


def generate_dashboard_data(config_path="dashboard_config.json", dataset_path="insurance_data.csv"):
    config = load_json(config_path)
    template_path = choose_template(config)
    template = load_json(template_path)
    df = load_dataset(dataset_path)

    # KPI computation
    computed_kpis = []
    for kpi in config.get("kpis", []):
        value = compute_kpi(df, kpi)
        computed_kpis.append({
            "name": kpi["name"],
            "column": kpi["column"],
            "aggregation": kpi["aggregation"],
            "value": value
        })

    # Chart preparation
    computed_charts = []
    for chart in config.get("charts", []):
        chart_data = prepare_chart_data(df, chart)
        computed_charts.append(chart_data)

    dashboard_data = {
        "template": template["template_name"],
        "title": config.get("dashboard_focus", "Auto Generated Dashboard"),
        "kpis": computed_kpis,
        "charts": computed_charts,
        "insights": config.get("insights", [])
    }

    return dashboard_data


def main():
    dashboard_data = generate_dashboard_data()

    with open("generated_dashboard_data.json", "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, indent=4, ensure_ascii=False)

    print("Dashboard data generated successfully.")
    print("Saved to generated_dashboard_data.json")


if __name__ == "__main__":
    main()
    