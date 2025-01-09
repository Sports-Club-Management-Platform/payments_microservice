import json
import logging
import time
from unittest.mock import MagicMock, patch

import pytest
import stripe
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from auth.auth import get_current_user_id
from db.database import get_db
from main import app
from models.models import TicketStock, UserMapping
from routers.checkout import DOMAIN, expire_time, process_message

load_dotenv()
client = TestClient(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
user_mapping = UserMapping(uuid="123", user_id="456")


@pytest.fixture(scope="module", autouse=True)
def mock_db():
    db = MagicMock(spec=Session)
    app.dependency_overrides[get_db] = lambda: db
    yield db


@pytest.fixture(scope="module", autouse=True)
def mock_auth():
    auth = MagicMock()
    app.dependency_overrides[get_current_user_id] = lambda: auth
    yield auth


@patch("routers.checkout.stripe.checkout.Session.create")
def test_create_checkout_session_with_invalid_price_id(stripe_checkout_session_mock, mock_db):
    invalid_price_id = "pr_123"
    valid_quantity = "1"

    db_ticket_stock = MagicMock(spec=TicketStock)
    db_ticket_stock.stock = 100
    mock_db.query.return_value.filter.return_value.first.return_value = db_ticket_stock

    response = client.post(
        f"/create-checkout-session?price_id={invalid_price_id}&quantity={valid_quantity}",
        allow_redirects=False
    )
    assert response.status_code == 404
    assert response.text == f"Price id not found"
    assert stripe_checkout_session_mock.call_count == 0


@patch("routers.checkout.stripe.checkout.Session.create")
def test_create_checkout_session_with_invalid_quantity(stripe_checkout_session_mock):
    valid_price_id = "price_1QBvVfJo4ha2Zj4nO3F0YLFr"
    invalid_quantity = "invalid"
    response = client.post(
        f"/create-checkout-session?price_id={valid_price_id}&quantity={invalid_quantity}",
        allow_redirects=False
    )
    assert response.status_code == 422
    assert stripe_checkout_session_mock.call_count == 0


@patch("routers.checkout.crud.create_user_mapping", return_value=user_mapping)
@patch("routers.checkout.time.time", return_value=time.time())
@patch("routers.checkout.stripe.checkout.Session.create", wraps=stripe.checkout.Session.create)
def test_create_checkout_session_with_valid_price_id_and_quantity(stripe_checkout_session, time_mock,
                                                                  user_mapping_mock, mock_db):
    valid_price_id = "price_1QBvVfJo4ha2Zj4nO3F0YLFr"
    valid_quantity = "2"

    db_ticket_stock = MagicMock(spec=TicketStock)
    db_ticket_stock.stock = 100
    mock_db.query.return_value.filter.return_value.first.return_value = db_ticket_stock

    response = client.post(
        f"/create-checkout-session?price_id={valid_price_id}&quantity={valid_quantity}",
        allow_redirects=False
    )
    assert response.status_code == 200
    stripe_checkout_session.assert_called_once_with(
        line_items=[
            {
                'price': valid_price_id,
                'quantity': int(valid_quantity),
            },
        ],
        mode='payment',
        success_url=DOMAIN + '/checkout-success',
        cancel_url=DOMAIN + '/checkout-canceled',
        expires_at=int(time_mock.return_value + expire_time),
        client_reference_id=user_mapping.uuid,
    )
    assert response.json()["checkout_url"].startswith("https://checkout.stripe.com/c/pay/cs_test_")


@patch("routers.checkout.stripe.checkout.Session.create", side_effect=Exception("Stripe error"))
def test_create_checkout_session_with_exception(stripe_checkout_session_mock):
    valid_price_id = "price_1QBvVfJo4ha2Zj4nO3F0YLFr"
    valid_quantity = "2"
    response = client.post(
        f"/create-checkout-session?price_id={valid_price_id}&quantity={valid_quantity}",
        allow_redirects=False
    )
    logger.info(stripe_checkout_session_mock.call_count)
    assert response.status_code == 500
    assert stripe_checkout_session_mock.call_count == 1

@patch("routers.checkout.create_ticket_stock")
@patch("routers.checkout.get_db")
@pytest.mark.asyncio
async def test_process_message_ticket_created(get_db_mock, create_ticket_stock_mock, mock_db):
    get_db_mock.return_value = iter([mock_db])
    message = {
        "event": "ticket_created",
        "ticket_id": 1,
        "stripe_price_id": "price_123",
        "stock": 100
    }
    body = json.dumps(message)
    
    await process_message(body)
    
    create_ticket_stock_mock.assert_called_once_with(mock_db, 1, "price_123", 100)

@patch("routers.checkout.update_ticket_stock")
@patch("routers.checkout.get_db")
@pytest.mark.asyncio
async def test_process_message_ticket_stock_updated(get_db_mock, update_ticket_stock_mock, mock_db):
    get_db_mock.return_value = iter([mock_db])
    message = {
        "event": "ticket_stock_updated",
        "ticket_id": 1,
        "stock": 50
    }
    body = json.dumps(message)
    
    await process_message(body)
    
    update_ticket_stock_mock.assert_called_once_with(mock_db, 1, 50)

@patch("routers.checkout.logger.info")
@pytest.mark.asyncio
async def test_process_message_unhandled_event(logger_info_mock):
    message = {
        "event": "unhandled_event",
    }
    body = json.dumps(message)
    
    await process_message(body)
    
    logger_info_mock.assert_called_with("Unhandled event: unhandled_event")
