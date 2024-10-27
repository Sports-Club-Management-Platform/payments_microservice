import logging
import time

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from db.database import get_db
from main import app
from routers.checkout import webhook_secret

load_dotenv()
client = TestClient(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StripeEvent:
    def __init__(self, type):
        self.type = type

    def json(self):
        return self.data


checkout_session_completed = StripeEvent("checkout.session.completed")
checkout_session_expired = StripeEvent("checkout.session.expired")


@pytest.fixture(scope="module", autouse=True)
def mock_db():
    db = MagicMock(spec=Session)
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


@patch("routers.checkout.stripe.Webhook.construct_event", return_value=checkout_session_completed)
def test_webhook_checkout_completed_with_valid_signature(webhook_construct_event_mock):
    response = client.post("/webhooks/checkout", headers={"Stripe-Signature": "valid"})
    assert response.status_code == 200
    webhook_construct_event_mock.assert_called_once_with(b"", "valid", webhook_secret)
    assert response.text == ""


@patch("routers.checkout.stripe.Webhook.construct_event", return_value=checkout_session_expired)
def test_webhook_checkout_expired_with_valid_signature(webhook_construct_event_mock):
    response = client.post("/webhooks/checkout", headers={"Stripe-Signature": "valid"})
    assert response.status_code == 200
    webhook_construct_event_mock.assert_called_once_with(b"", "valid", webhook_secret)
    assert response.text == ""
