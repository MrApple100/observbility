from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import Column, String, select
from sqlalchemy.ext.declarative import declarative_base
import uuid

# Настройка базы данных
DATABASE_URL = "postgresql+asyncpg://user:password@db:5432/shortener"

Base = declarative_base()

class URLMapping(Base):
    __tablename__ = "url_mapping"
    short_id = Column(String(8), primary_key=True)
    url = Column(String, nullable=False)

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Создание таблиц
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app = FastAPI(on_startup=[init_db])

# Модели запросов
class ShortenRequest(BaseModel):
    url: str

@app.post("/shorten")
async def shorten_url(request: ShortenRequest):
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

