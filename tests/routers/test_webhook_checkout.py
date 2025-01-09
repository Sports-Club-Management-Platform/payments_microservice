import json
import logging
import time
from collections import namedtuple
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from aio_pika import Message
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import orm

from crud.crud import get_stock_ticket_id_by_price_id
from db.database import get_db
from main import app
from routers.checkout import webhook_secret

load_dotenv()
client = TestClient(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

StripeEventDataObject = namedtuple('StripeEventDataObject', ['id'])
StripeEventData = namedtuple('StripeEventData', ['object'])
StripeEvent = namedtuple('StripeEvent', ['type', 'data'])
UserMapping = namedtuple('UserMapping', ['uuid', 'user_id'])
Price = namedtuple('Price', ['id', 'product', 'unit_amount'])
LineItem = namedtuple('LineItem', ['price', 'quantity'])
LineItems = namedtuple('LineItems', ['data'])
Session = namedtuple('Session', ['line_items', 'client_reference_id'])

event_data_object = StripeEventDataObject(id="evt_123")
event_data = StripeEventData(object=event_data_object)
checkout_session_completed = StripeEvent(type="checkout.session.completed", data=event_data)
checkout_session_expired = StripeEvent(type="checkout.session.expired", data=event_data)
user_mapping = UserMapping(uuid="uuid_789", user_id="user_123")
price = Price(id="price_456", product="product_789", unit_amount=1)
line_item = LineItem(price=price, quantity=1)
line_items = LineItems(data=[line_item])
session = Session(line_items=line_items, client_reference_id=user_mapping.uuid)



@pytest.fixture(scope="module", autouse=True)
def mock_db():
    db = MagicMock(spec=orm.Session)
    app.dependency_overrides[get_db] = lambda: db
    yield db


def test_call_webhook_with_no_signature():
    response = client.post("/webhooks/checkout")
    assert response.status_code == 400


def test_call_webhook_with_invalid_signature():
    response = client.post("/webhooks/checkout", headers={"Stripe-Signature": "invalid"})
    assert response.status_code == 400


@patch("routers.checkout.stripe.Webhook.construct_event", side_effect=ValueError("Invalid payload"))
def test_webhook_checkout_with_value_error(webhook_construct_event_mock):
    response = client.post("/webhooks/checkout", headers={"Stripe-Signature": "valid"})
    assert response.status_code == 400
    webhook_construct_event_mock.assert_called_once_with(b"", "valid", webhook_secret)
    assert response.text == ""

@patch("routers.checkout.stripe.checkout.Session.retrieve", return_value=session)
@patch("routers.checkout.stripe.Webhook.construct_event", return_value=checkout_session_expired)
def test_webhook_checkout_expired_with_valid_signature(webhook_construct_event_mock, session_retrieve_mock):
    response = client.post("/webhooks/checkout", headers={"Stripe-Signature": "valid"})
    assert response.status_code == 200
    webhook_construct_event_mock.assert_called_once_with(b"", "valid", webhook_secret)
    session_retrieve_mock.assert_called_once_with(checkout_session_expired.data.object.id, expand=['line_items'])
    assert response.text == ""


@patch("routers.checkout.crud.get_user_mapping_by_uuid", return_value=user_mapping)
@patch("routers.checkout.stripe.checkout.Session.retrieve", return_value=session)
@patch("routers.checkout.stripe.Webhook.construct_event", return_value=checkout_session_completed)
@patch("routers.checkout.get_stock_ticket_id_by_price_id", return_value="ticket_123")
@patch("routers.checkout.datetime")
def test_webhook_checkout_completed_with_valid_signature(
        datetime_mock, get_stock_ticket_id_by_price_id_mock, webhook_construct_event_mock, session_retrieve_mock, get_user_mapping_by_uuid_mock, mock_db
):
    fixed_datetime = datetime(2025, 1, 9, 17, 0, 0)
    datetime_mock.now.return_value = fixed_datetime

    with patch("routers.checkout.exchange", MagicMock()) as exchange_mock:
        publish_mock = AsyncMock(return_value=None)
        exchange_mock.publish = publish_mock
        response = client.post("/webhooks/checkout", headers={"Stripe-Signature": "valid"})
        assert response.status_code == 200
        assert response.text == ""
        webhook_construct_event_mock.assert_called_once_with(b"", "valid", webhook_secret)
        session_retrieve_mock.assert_called_once_with(checkout_session_completed.data.object.id, expand=['line_items'])
        get_user_mapping_by_uuid_mock.assert_called_once_with(mock_db, user_mapping.uuid)
        get_stock_ticket_id_by_price_id_mock.assert_called_once_with(mock_db, session.line_items.data[0].price.id)
        assert publish_mock.call_count == 1
        _, kwargs = publish_mock.call_args
        assert kwargs.get('routing_key') == "payments.messages"
        assert kwargs.get('message').body == json.dumps({
            "event": checkout_session_completed.type,
            "user_id": user_mapping.user_id,
            "ticket_id": "ticket_123",
            "quantity": session.line_items.data[0].quantity,
            "unit_amount": session.line_items.data[0].price.unit_amount / 100,
            "created_at": str(fixed_datetime),
        }).encode()


