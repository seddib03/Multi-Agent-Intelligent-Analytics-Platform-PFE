# app/context/kpi_mapper.py
from typing import Optional, Tuple, Dict, Any

def normalize(s: str) -> str:
    return " ".join(s.lower().strip().split())

class KPIMapper:
    """
    Deterministic KPI mapping using sector_kpi_map.yaml:
    - exact alias match => high confidence
    - substring match => medium confidence
    """
    def __init__(self, kpi_catalog: Dict[str, Any]):
        self.catalog = kpi_catalog

    def map_metric(self, sector: str, metric: Optional[str]) -> Tuple[Optional[str], float, Optional[str]]:
        """
        Returns: (canonical_metric, confidence, matched_alias)
        """
        if not metric:
            return None, 0.0, None

        metric_n = normalize(metric)
        sectors = self.catalog.get("sectors", {})
        sec = sectors.get(sector)
        if not sec:
            return None, 0.0, None

        kpis = sec.get("kpis", {})
        # kpis: canonical -> [aliases...]
        # 1) exact match (canonical)
        for canonical in kpis.keys():
            if normalize(canonical) == metric_n:
                return canonical, 0.95, canonical

        # 2) exact match (alias)
        for canonical, aliases in kpis.items():
            for a in aliases:
                if normalize(a) == metric_n:
                    return canonical, 0.90, a

        # 3) substring match
        for canonical, aliases in kpis.items():
            for a in aliases:
                a_n = normalize(a)
                if a_n and (a_n in metric_n or metric_n in a_n):
                    return canonical, 0.75, a

        return None, 0.3, None