from app.core.config import settings
from app.nlq.schemas import NLQOutput
from .schemas import ContextOutput
from .prompts import CONTEXT_SYSTEM, context_user_prompt
from .resources_loader import load_yaml
from .kpi_mapper import KPIMapper
from .sector_detector import SectorDetector

ALLOWED_SECTORS = {"transport","finance","retail","manufacturing","public","unknown"}

def decide_execution(intent: str) -> str:
    if intent in ["analyze", "compare"]:
        return "sql"
    if intent == "predict":
        return "prediction"
    if intent == "explain":
        return "insight"
    return "unknown"

class ContextService:
    def __init__(self, llm):
        self.llm = llm
        self.kpi_catalog = load_yaml("sector_kpi_map.yaml")
        self.schema_registry = load_yaml("sector_schema_registry.yaml")

        self.sector_detector = SectorDetector(self.kpi_catalog)
        self.kpi_mapper = KPIMapper(self.kpi_catalog)

    def enrich(self, nlq: NLQOutput) -> ContextOutput:
        # 1) deterministic sector
        sector, sector_conf = self.sector_detector.detect(nlq.raw_question, nlq.metric)
        if sector not in ALLOWED_SECTORS:
            sector = "unknown"
            sector_conf = 0.3

        # 2) deterministic KPI mapping
        canonical_metric, kpi_conf, matched_alias = self.kpi_mapper.map_metric(sector, nlq.metric)

        execution_type = decide_execution(nlq.intent)

        # 3) Decide when to call LLM fallback
        need_llm = (
            sector == "unknown"
            or canonical_metric is None
        )

        if need_llm:
            # LLM fallback (your current approach)
            prompt = context_user_prompt(
                nlq_dict=nlq.model_dump(),
                kpi_catalog=self.kpi_catalog,
                schema_registry=self.schema_registry,
                schema_version=settings.schema_version,
            )
            data = self.llm.generate_pydantic(
                system=CONTEXT_SYSTEM,
                user=prompt,
                response_model=dict,
                temperature=0.0,
            )
            # guardrails
            data["intent"] = data.get("intent") or nlq.intent
            data["schema_version"] = settings.schema_version
            if "filters" not in data or data["filters"] is None:
                data["filters"] = nlq.filters or {}
            if "confidence" not in data:
                data["confidence"] = 0.6

            return ContextOutput(**data)

        # 4) Deterministic build (no LLM)
        # Build data_source from registry (simple: sector default_table)
        sec_reg = self.schema_registry.get("sectors", {}).get(sector, {})
        default_table = sec_reg.get("default_table")
        table_info = (sec_reg.get("tables", {}) or {}).get(default_table, {})
        columns_allowed = table_info.get("columns_allowed", [])

        data_source = None
        model_hint = None

        if execution_type == "sql":
            data_source = {
                "database": sec_reg.get("database"),
                "table": default_table,
                "columns_allowed": columns_allowed,
            }
        elif execution_type == "prediction":
            model_hint = {"target": canonical_metric, "horizon": nlq.timeframe or "unknown"}

        # confidence combined (pro)
        # NLQ confidence + sector_conf + kpi_conf
        conf = min(0.95, 0.4 * nlq.confidence + 0.3 * sector_conf + 0.3 * kpi_conf)

        return ContextOutput(
            intent=nlq.intent,
            sector=sector,
            canonical_metric=canonical_metric,
            execution_type=execution_type,
            data_source=data_source,
            model_hint=model_hint,
            filters=nlq.filters or {},
            schema_version=settings.schema_version,
            confidence=conf,
        )