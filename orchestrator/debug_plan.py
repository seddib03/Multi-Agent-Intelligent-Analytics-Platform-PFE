import httpx, asyncio, json

async def check():
    job_id = "44c3428a-0cab-4708-818d-2dce46b6055b"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"http://127.0.0.1:8001/jobs/{job_id}/plan")
        print(json.dumps(r.json(), indent=2))

asyncio.run(check())