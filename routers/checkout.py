import json
import os
import time

from fastapi import APIRouter, Depends, HTTPException, status, Request
import stripe
from pydantic import BaseModel
from starlette.responses import RedirectResponse, Response
import logging

router = APIRouter(
    tags=["Create checkout sessions"],

)
DOMAIN = os.getenv("DOMAIN")
stripe.api_key = os.getenv("STRIPE_API_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
expire_time = int(os.getenv("EXPIRE_TIME"))  # in seconds
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


@router.post('/create-checkout-session')
def create_checkout_session(price_id: str, quantity: int):
    try:
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
        )
    except stripe.error.InvalidRequestError as e:
        logger.error(f"Invalid price ID: {price_id} - {e}")
        return Response(status_code=status.HTTP_404_NOT_FOUND, content=f"Price id {price_id} not found")
    except Exception as e:
        logger.error(e)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return RedirectResponse(checkout_session.url, status_code=303)


# webhooks - don't know why @app.webhooks is not working
@router.post("/webhooks/checkout")
async def webhooks(request: Request):
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
        logger.info(event)
    except ValueError as e:
        # Invalid payload
        return Response(status_code=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error('Error verifying webhook signature: {}'.format(str(e)))
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    # Handle the event
    if event.type == "checkout.session.completed":
        print('Checkout session completed')
        # post to queue
    elif event.type == "checkout.session.expired":
        print('Checkout session expired')
        # post to queue
    else:
        print('Unhandled event type {}'.format(event.type))

    return Response(status_code=status.HTTP_200_OK)
