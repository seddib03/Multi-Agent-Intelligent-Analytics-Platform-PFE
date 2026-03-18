# app/utils/async_utils.py
import asyncio
import concurrent.futures

def run_async(coro, timeout=150):
    """Lance une coroutine async depuis un contexte synchrone (LangGraph node)."""
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result(timeout=timeout)