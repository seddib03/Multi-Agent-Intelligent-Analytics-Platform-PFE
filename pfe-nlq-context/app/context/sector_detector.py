# app/context/sector_detector.py
from typing import Dict, Any, Optional, Tuple

def normalize(s: str) -> str:
    return " ".join(s.lower().strip().split())

class SectorDetector:
    """
    Deterministic sector detection from:
    - sector aliases
    - KPI aliases
    """
    def __init__(self, kpi_catalog: Dict[str, Any]):
        self.catalog = kpi_catalog

    def detect(self, question: str, metric: Optional[str]) -> Tuple[str, float]:
        q = normalize(question)
        m = normalize(metric) if metric else ""

        sectors = self.catalog.get("sectors", {})
        scores = {}

        for sector, info in sectors.items():
            score = 0
            # aliases
            for a in info.get("aliases", []):
                if normalize(a) in q:
                    score += 2

            # KPI aliases
            kpis = info.get("kpis", {})
            for canonical, aliases in kpis.items():
                if normalize(canonical) in q:
                    score += 2
                for al in aliases:
                    al_n = normalize(al)
                    if al_n in q:
                        score += 1
                    if m and al_n == m:
                        score += 2

            scores[sector] = score

        best = max(scores, key=scores.get) if scores else "unknown"
        best_score = scores.get(best, 0)

        if best_score == 0:
            return "unknown", 0.3

        conf = min(0.95, 0.55 + 0.08 * best_score)
        return best, conf