from fastapi import FastAPI, HTTPException, Request
import httpx
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry, make_asgi_app
from starlette.responses import Response

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

app = FastAPI()

reqistry = CollectorRegistry()
metrics_app = make_asgi_app(registry=reqistry)
app.mount("/metrics",metrics_app)

# Настройка трассировки
resource = Resource.create(attributes={"service.name": "service_a"})
tracer_provider = TracerProvider(resource=resource)
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",  # Имя контейнера Jaeger
    agent_port=6831,
)
tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(tracer_provider)

# Инструментируем FastAPI и запросы
FastAPIInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Метрики
REQUEST_COUNT = Counter(
    "service_a_requests_total", "Количество запросов", ["method", "endpoint", "http_status"],registry=reqistry
)
REQUEST_LATENCY = Histogram(
    "service_a_request_latency_seconds", "Время обработки запросов", ["endpoint"],registry=reqistry
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
