import json
import streamlit as st
import pandas as pd
import plotly.express as px


def load_dashboard_data(path="generated_dashboard_data.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_kpi_value(value):
    if isinstance(value, (int, float)):
        if value >= 1_000_000:
            return f"{value/1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value/1_000:.1f}K"
        else:
            return str(round(value, 2))
    return str(value)


def build_chart(chart):
    df = pd.DataFrame(chart["data"])

    if df.empty:
        st.warning(f"No data available for chart: {chart['title']}")
        return

    chart_type = chart["type"].lower()
    x = chart["x"]
    y = chart["y"]
    title = chart["title"]

    if chart_type == "line":
        fig = px.line(df, x=x, y=y, title=title, markers=True)

    elif chart_type == "bar" or chart_type == "column":
        fig = px.bar(df, x=x, y=y, title=title)

    elif chart_type == "pie":
        fig = px.pie(df, names=x, values=y, title=title)

    elif chart_type == "area":
        fig = px.area(df, x=x, y=y, title=title)

    else:
        st.warning(f"Unsupported chart type: {chart_type}")
        return

    st.plotly_chart(fig, use_container_width=True)


def main():
    st.set_page_config(page_title="Auto Generated Dashboard", layout="wide")

    dashboard_data = load_dashboard_data()

    st.title(dashboard_data.get("title", "Auto Generated Dashboard"))

    # Show selected template
    st.caption(f"Template selected: {dashboard_data.get('template', 'N/A')}")

    # KPI section
    st.subheader("Key Performance Indicators")
    kpis = dashboard_data.get("kpis", [])

    if kpis:
        cols = st.columns(len(kpis))
        for i, kpi in enumerate(kpis):
            with cols[i]:
                st.metric(
                    label=kpi["name"],
                    value=format_kpi_value(kpi["value"])
                )

    # Charts section
    st.subheader("Charts")
    charts = dashboard_data.get("charts", [])

    if len(charts) >= 1:
        build_chart(charts[0])

    if len(charts) > 1:
        cols = st.columns(2)
        for i, chart in enumerate(charts[1:3]):
            with cols[i]:
                build_chart(chart)

    if len(charts) > 3:
        for chart in charts[3:]:
            build_chart(chart)

    # Insights section
    insights = dashboard_data.get("insights", [])
    if insights:
        st.subheader("Insights")
        for insight in insights:
            st.markdown(f"- {insight}")


if __name__ == "__main__":
    main()
    