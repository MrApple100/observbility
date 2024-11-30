from fastapi import FastAPI, HTTPException, Request
import httpx
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response






app = FastAPI()

# Метрики
REQUEST_COUNT = Counter(
    "service_a_requests_total", "Количество запросов", ["method", "endpoint", "http_status"]
)
REQUEST_LATENCY = Histogram(
    "service_a_request_latency_seconds", "Время обработки запросов", ["endpoint"]
)

@app.middleware("http")
async def add_metrics_middleware(request: Request, call_next):
    endpoint = request.url.path
    method = request.method
    with REQUEST_LATENCY.labels(endpoint=endpoint).time():
        response = await call_next(request)
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=response.status_code).inc()
        return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")

class ShortenRequest(BaseModel):
    url: str

@app.post("/shorten")
async def shorten_url(request: ShortenRequest):
    async with httpx.AsyncClient() as client:
        response = await client.post("http://service_b:8001/shorten", json={"url": request.url})
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()

@app.get("/resolve/{short_id}")
async def resolve_url(short_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://service_b:8001/resolve/{short_id}")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()
