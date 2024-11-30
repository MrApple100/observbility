from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import Column, String, select
from sqlalchemy.ext.declarative import declarative_base
import uuid
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry, make_asgi_app
from starlette.responses import Response


from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


# Создание таблиц
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)



app = FastAPI(on_startup=[init_db])

reqistry = CollectorRegistry()
metrics_app = make_asgi_app(registry=reqistry)
app.mount("/metrics",metrics_app)

# Настройка трассировки
resource = Resource.create(attributes={"service.name": "service_b"})
tracer_provider = TracerProvider(resource=resource)
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,
)
tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# Инструментируем FastAPI
FastAPIInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Метрики
REQUEST_COUNT = Counter(
    "service_b_requests_total", "Количество запросов", ["method", "endpoint", "http_status"],registry=reqistry
)
REQUEST_LATENCY = Histogram(
    "service_b_request_latency_seconds", "Время обработки запросов", ["endpoint"],registry=reqistry
)

@app.middleware("http")
async def add_metrics_middleware(request: Request, call_next):
    endpoint = request.url.path
    method = request.method
    with REQUEST_LATENCY.labels(endpoint=endpoint).time():
        response = await call_next(request)
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, http_status=response.status_code).inc()
        return response




# Настройка базы данных
DATABASE_URL = "postgresql+asyncpg://user:password@db:5432/shortener"

Base = declarative_base()

class URLMapping(Base):
    __tablename__ = "url_mapping"
    short_id = Column(String(8), primary_key=True)
    url = Column(String, nullable=False)

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)


# Модели запросов
class ShortenRequest(BaseModel):
    url: str

@app.post("/shorten")
async def shorten_url(request: ShortenRequest):
    with tracer.start_as_current_span("service-b-process-request"):
        short_id = str(uuid.uuid4())[:8]
        async with async_session() as session:
            async with session.begin():
                mapping = URLMapping(short_id=short_id, url=request.url)
                session.add(mapping)
            await session.commit()
        return {"short_id": short_id, "url": request.url}

@app.get("/resolve/{short_id}")
async def resolve_url(short_id: str):
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(URLMapping).where(URLMapping.short_id == short_id))
            mapping = result.scalars().first()
            if not mapping:
                raise HTTPException(status_code=404, detail="Short ID not found")
            return {"short_id": short_id, "url": mapping.url}

@app.get("/health")
async def health():
    return {"status": "ok"}

