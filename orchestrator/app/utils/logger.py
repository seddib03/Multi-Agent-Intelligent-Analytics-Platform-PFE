import logging
import json
from datetime import datetime
# Logger setup for the orchestrator app

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

# global routing logger : shows the decisions

routing_logger = setup_logger("ORCHESTRATOR.ROUTING")


def log_routing_decision(
    query: str,
    sector: str,
    sector_confidence: float,
    intent: str,
    route: str,
    reason: str
):
    """formated log for each routing decision"""
    routing_logger.info(
        "\n" + "="*60 +
        f"\n QUERY     : {query}" +
        f"\n SECTOR    : {sector} (confidence: {sector_confidence:.0%})" +
        f"\n INTENT    : {intent}" +
        f"\n ROUTE     : {route}" +
        f"\n REASON    : {reason}" +
        "\n" + "="*60
    )