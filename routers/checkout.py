import os
from fastapi import APIRouter, Depends, HTTPException, status
import stripe
from starlette.responses import RedirectResponse, Response
import logging

router = APIRouter(tags=["Create checkout sessions"])
DOMAIN = os.getenv("DOMAIN")
stripe.api_key = os.getenv("STRIPE_API_KEY")
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
        )
    except stripe.error.InvalidRequestError as e:
        logger.error(f"Invalid price ID: {price_id} - {e}")
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content=f"Price id {price_id} not found")
    except Exception as e:
        logger.error(e)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return RedirectResponse(checkout_session.url, status_code=303)
