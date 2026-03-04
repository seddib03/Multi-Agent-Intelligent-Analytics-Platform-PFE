# app/core/request_id.py
import time
import uuid
from fastapi import Request

def new_request_id() -> str:
    return uuid.uuid4().hex[:12]

def now_ms() -> int:
    return int(time.time() * 1000)