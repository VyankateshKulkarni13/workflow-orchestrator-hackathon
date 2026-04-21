"""
redis_client.py
---------------
A simple singleton Redis client used by the engine to push tasks
onto the message queue for workers to pick up.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import redis.asyncio as aioredis

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Singleton async Redis client shared across the app
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)


async def enqueue_task(queue_name: str, payload: dict) -> None:
    """
    Push a task payload (JSON) to the left end of a Redis List.
    Workers use BRPOP to block and wait for tasks on the right end.
    This gives us a simple, reliable FIFO task queue per worker type.
    """
    await redis_client.lpush(queue_name, json.dumps(payload))
