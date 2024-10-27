from contextlib import asynccontextmanager
import aio_pika
import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette import status

import models
from db.create_database import create_tables
from db.database import engine
from routers import checkout


RABBITMQ_URL = os.environ.get("RABBITMQ_URL")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()

    async def rabbitmq_listener():
        queue = await channel.declare_queue("your_queue_name", durable=True)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    print("Received message:", message.body)
                    # Process the message here

    # Run RabbitMQ listener in the background
    task = asyncio.create_task(rabbitmq_listener())
    yield
    # Cleanup
    await channel.close()
    await connection.close()
    task.cancel()


app = FastAPI(
    lifespan=lifespan,
    title="ClubSync Payments_Microservice API",
    version="0.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "ClubSync",
    },
    servers=[{"url": "http://localhost:8000", "description": "Local server"}],
    webhooks={"new-subscription": {"url": "/webhooks/new-subscription"}},
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["healthcheck"],
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
)
def get_health():
    return {"status": "ok"}


app.include_router(checkout.router, tags=["Client"])
