import json
import os


def load_dashboard_config(config_path="dashboard_config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_template(template_path):
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def main():
    config = load_dashboard_config("dashboard_config.json")
    selected_template_path = choose_template(config)
    selected_template = load_template(selected_template_path)

    print("Selected template:", selected_template["template_name"])
    print(json.dumps(selected_template, indent=4))


if __name__ == "__main__":
    main()
    