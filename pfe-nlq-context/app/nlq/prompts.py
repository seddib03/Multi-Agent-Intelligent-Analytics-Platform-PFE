NLQ_SYSTEM = """
You are the NLQ Agent.
Convert the user question into a structured representation.
Do NOT generate SQL.
Focus on intent + entities (metric, timeframe, location, filters).
If unsure, set intent='other' and lower confidence.
"""

def nlq_user_prompt(question: str) -> str:
    return f"""User question:
{question}

Return only the structured fields."""