from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel

app = FastAPI()

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
