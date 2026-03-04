from app.context.kpi_mapper import KPIMapper

def test_kpi_mapper_exact_alias(kpi_catalog):
    mapper = KPIMapper(kpi_catalog)
    canonical, conf, alias = mapper.map_metric("retail", "sales")

    assert canonical == "total_sales_amount"
    assert conf >= 0.85
    assert alias is not None

def test_kpi_mapper_unknown_metric(kpi_catalog):
    mapper = KPIMapper(kpi_catalog)
    canonical, conf, alias = mapper.map_metric("retail", "random_metric_zzz")

    assert canonical is None
    assert conf <= 0.35
    assert alias is None

def test_kpi_mapper_missing_metric(kpi_catalog):
    mapper = KPIMapper(kpi_catalog)
    canonical, conf, alias = mapper.map_metric("retail", None)

    assert canonical is None
    assert conf == 0.0
    assert alias is None