import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

import aio_pika
import stripe
from aio_pika import Message
from auth.auth import get_current_user_id
from crud import crud
from crud.crud import (create_ticket_stock, decrement_stock,
                       get_stock_by_price_id, get_stock_by_ticket_id,
                       get_stock_ticket_id_by_price_id, increment_stock,
                       update_ticket_stock)
from db.create_database import create_tables
from db.database import get_db
from fastapi import APIRouter, Depends, FastAPI, Request, status
from models.models import TicketStock
from starlette.responses import Response

router = APIRouter(
    tags=["Create checkout sessions"],

)
DOMAIN = os.getenv("DOMAIN")
stripe.api_key = os.getenv("STRIPE_API_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
expire_time = int(os.getenv("EXPIRE_TIME"))  # in seconds
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))


RABBITMQ_URL = os.environ.get("RABBITMQ_URL")
exchange = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global connection, channel, exchange, queue
    create_tables()
    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange("exchange", type=aio_pika.ExchangeType.TOPIC, durable=True)
    queue = await channel.declare_queue("TICKETS", durable=True)
    await queue.bind(exchange, routing_key="TICKETS")

    async def rabbitmq_listener():
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    print("Received message:", message.body)
                    # Process the message here
                    await process_message(message.body)
    
    # Run RabbitMQ listener in the background
    task = asyncio.create_task(rabbitmq_listener())
    yield
    # Cleanup
    await channel.close()
    await connection.close()
    # task.cancel()

@router.post('/create-checkout-session', status_code=status.HTTP_200_OK)
def create_checkout_session(price_id: str, quantity: int, user_id=Depends(get_current_user_id), db=Depends(get_db)):
    try:
        logger.info("user mapping")
        user_mapping = crud.create_user_mapping(db, user_id)
        logger.info(user_mapping)

        # Decrement stock function needs to be implemented here
        decrement_stock(db, price_id, quantity)

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # stripe.Price.retrieve(price_id) throws exception if price id not found
                    # stripe will retrieve the product associated with this price in checkout page sent in redirect
                    'price': stripe.Price.retrieve(price_id).id,
                    'quantity': quantity,
                },
            ],
            mode='payment',
            success_url=DOMAIN + '/checkout-success',
            cancel_url=DOMAIN + '/checkout-canceled',
            expires_at=int(time.time() + expire_time),
            client_reference_id=user_mapping.uuid,
        )
    except stripe.error.InvalidRequestError as e:
        logger.error("Invalid price ID: %s", e)
        increment_stock(db, price_id, quantity)
        return Response(status_code=status.HTTP_404_NOT_FOUND, content="Price id not found")
    except Exception as e:
        logger.error(e)
        increment_stock(db, price_id, quantity)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return {"checkout_url": checkout_session.url}


# webhooks - don't know why @app.webhooks is not working
@router.post("/webhooks/checkout")
async def webhooks(request: Request, db=Depends(get_db)):
    """
    When a new user subscribes to your service we'll send you a POST request with this
    data to the URL that you register for the event `new-subscription` in the dashboard.
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    event = None
    logger.info(payload)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error('Error verifying webhook signature: {}'.format(str(e)))
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    ticket = session.line_items.data[0]

    # Handle the event
    if event.type == "checkout.session.completed":
        logger.info('Checkout session completed')
        session = stripe.checkout.Session.retrieve(event.data.object.id, expand=['line_items'])
        logger.info(session)
        ticket_message_payload = {
            "event": event.type,
            "user_id": crud.get_user_mapping_by_uuid(db, session.client_reference_id).user_id,
            "ticket_id": get_stock_ticket_id_by_price_id(db, ticket.price.id),
            "quantity": ticket.quantity,
            "total_price": session.amount_total,
            "created_at": time.time(),
        }

        email_message_payload = {
            "user_name" : "????",   # get user info from user_auth.py
            "ticket_name" : stripe.Price.retrieve(ticket.price.id, expand=['product']).product.name,
            "ticket_price": session.amount_total,
            "ticket_id": get_stock_ticket_id_by_price_id(db, ticket.price.id),
            "to_email": "????",     # get user email from user_auth.py
        }
        
        logger.info(ticket_message_payload)
        await send_messages(ticket_message_payload, email_message_payload)

    elif event.type == "checkout.session.expired":
        logger.info('Checkout session expired')
        session = stripe.checkout.Session.retrieve(event.data.object.id, expand=['line_items'])
        price_id = ticket.price.id
        quantity = ticket.quantity
        increment_stock(db, price_id, quantity)

    else:
        logger.info('Unhandled event type {}'.format(event.type))

    return Response(status_code=status.HTTP_200_OK)

@router.get("/stock/{ticket_id}")
def get_stock(ticket_id: int, db=Depends(get_db)):
    try:
        stock = get_stock_by_ticket_id(db, ticket_id)
    except Exception as e:
        logger.error(e)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return stock


async def process_message(body):
    message = json.loads(body)
    event = message.get("event")
    if event == "ticket_created":
        ticket_id = message.get("ticket_id")
        stripe_price_id = message.get("stripe_price_id")
        stock = message.get("stock")
        if ticket_id and stripe_price_id and stock is not None:
            db = next(get_db())
            try:
                create_ticket_stock(db, ticket_id, stripe_price_id, stock)
                logger.info(f"TicketStock created: ticket_id={ticket_id}, stripe_price_id={stripe_price_id}, stock={stock}")
            finally:
                db.close()
    elif event == "ticket_stock_updated":
        ticket_id = message.get("ticket_id")
        stock = message.get("stock")
        if ticket_id and stock is not None:
            db = next(get_db())
            try:
                update_ticket_stock(db, ticket_id, stock)
                logger.info(f"TicketStock updated: ticket_id={ticket_id}, stock={stock}")
            finally:
                db.close()
    else:
        logger.info(f"Unhandled event: {event}")

async def send_messages(ticket_body, email_body):
    await exchange.publish(
        routing_key="TICKETS",
        message=Message(
            body=json.dumps(ticket_body).encode()
        ),
    )
    await exchange.publish(
        routing_key="EMAILS",
        message=Message(
            body=json.dumps(email_body).encode()
        ),
    )

# # get tickets stocks for testing purposes
# @router.get("/ticket-stocks")
# def get_ticket_stocks(db=Depends(get_db)):
#     ticket_stocks = db.query(TicketStock).all()
#     return ticket_stocks

