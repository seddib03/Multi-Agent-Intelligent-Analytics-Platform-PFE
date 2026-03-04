from app.context.sector_detector import SectorDetector

def test_sector_detector_retail(kpi_catalog):
    det = SectorDetector(kpi_catalog)
    sector, conf = det.detect("Total sales in 2023 in Casablanca", "sales")

    assert sector == "retail"
    assert conf >= 0.6

def test_sector_detector_finance(kpi_catalog):
    det = SectorDetector(kpi_catalog)
    sector, conf = det.detect("Predict default rate next quarter", "default rate")

    assert sector == "finance"
    assert conf >= 0.6

def test_sector_detector_transport(kpi_catalog):
    det = SectorDetector(kpi_catalog)
    sector, conf = det.detect("Average delay minutes in 2023 in Rabat", "delay")

    assert sector == "transport"
    assert conf >= 0.6

def test_sector_detector_unknown(kpi_catalog):
    det = SectorDetector(kpi_catalog)
    sector, conf = det.detect("What is the best color for a logo?", None)

    assert sector == "unknown"
    assert conf <= 0.4