import asyncio
import json
import os
import logging
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from orchestrator import handle_chat, research_and_build
from agents.tools import init_redis

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress noisy session-termination warnings from Monday MCP (500 on DELETE is harmless)
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)

redis_client: redis.Redis = None


async def pipeline_consumer(redis_url: str) -> None:
    """Subscribe to pipeline:start and run research_and_build for each event."""
    sub = redis.from_url(redis_url, decode_responses=True)
    pubsub = sub.pubsub()
    await pubsub.subscribe("pipeline:start")
    logger.info("[Consumer] Subscribed to pipeline:start")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                logger.info(f"[Consumer] pipeline:start received for {data.get('email')}")
                asyncio.create_task(research_and_build(**data))
    finally:
        await sub.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    init_redis(redis_url)
    logger.info(f"Connected to Redis at {redis_url}")
    consumer_task = asyncio.create_task(pipeline_consumer(redis_url))
    yield
    consumer_task.cancel()
    await redis_client.aclose()


app = FastAPI(title="GTM AI Orchestrator", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not available")

    result = await handle_chat(
        redis_client=redis_client,
        session_id=request.session_id,
        message=request.message,
    )

    return result
