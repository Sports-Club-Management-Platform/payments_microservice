import logging
import time

import pytest
import stripe
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from auth.auth import get_current_user_id
from db.database import get_db
from main import app
from models.models import UserMapping
from routers.checkout import DOMAIN, expire_time
from auth.auth import jwks, get_current_user
from auth.JWTBearer import JWTAuthorizationCredentials, JWTBearer
from routers.checkout import auth

load_dotenv()
client = TestClient(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
user_mapping = UserMapping(uuid="123", user_id="456")

@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[auth] = lambda: JWTAuthorizationCredentials(
        jwt_token="token",
        header={"kid": "some_kid"},
        claims={"sub": "user_id"},
        signature="signature",
        message="message",
    )
    yield
    app.dependency_overrides.pop(auth, None)  # Cleanup after each test

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
def test_create_checkout_session_with_invalid_price_id(stripe_checkout_session_mock):
    app.dependency_overrides[auth] = lambda: JWTAuthorizationCredentials(
        jwt_token="token",
        header={"kid": "some_kid"},
        claims={"sub": "user_id"},
        signature="signature",
        message="message",
    )
    headers = {"Authorization": "Bearer token"}
    invalid_price_id = "pr_123"
    valid_quantity = "1"
    response = client.post(
        f"/create-checkout-session?price_id={invalid_price_id}&quantity={valid_quantity}",
        allow_redirects=False, headers=headers
    )
    assert response.status_code == 404
    assert response.text == f"Price id not found"
    assert stripe_checkout_session_mock.call_count == 0


@patch("routers.checkout.stripe.checkout.Session.create")
def test_create_checkout_session_with_invalid_quantity(stripe_checkout_session_mock):
    app.dependency_overrides[auth] = lambda: JWTAuthorizationCredentials(
        jwt_token="token",
        header={"kid": "some_kid"},
        claims={"sub": "user_id"},
        signature="signature",
        message="message",
    )
    headers = {"Authorization": "Bearer token"}
    valid_price_id = "price_1QBvVfJo4ha2Zj4nO3F0YLFr"
    invalid_quantity = "invalid"
    response = client.post(
        f"/create-checkout-session?price_id={valid_price_id}&quantity={invalid_quantity}",
        allow_redirects=False, headers=headers
    )
    assert response.status_code == 422
    assert stripe_checkout_session_mock.call_count == 0


@patch("routers.checkout.crud.create_user_mapping", return_value=user_mapping)
@patch("routers.checkout.time.time", return_value=time.time())
@patch("routers.checkout.stripe.checkout.Session.create", wraps=stripe.checkout.Session.create)
def test_create_checkout_session_with_valid_price_id_and_quantity(stripe_checkout_session, time_mock,
                                                                  user_mapping_mock):
    app.dependency_overrides[auth] = lambda: JWTAuthorizationCredentials(
        jwt_token="token",
        header={"kid": "some_kid"},
        claims={"sub": "user_id"},
        signature="signature",
        message="message",
    )
    headers = {"Authorization": "Bearer token"}
    valid_price_id = "price_1QBvVfJo4ha2Zj4nO3F0YLFr"
    valid_quantity = "2"
    response = client.post(
        f"/create-checkout-session?price_id={valid_price_id}&quantity={valid_quantity}",
        allow_redirects=False, headers=headers
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
    app.dependency_overrides[auth] = lambda: JWTAuthorizationCredentials(
        jwt_token="token",
        header={"kid": "some_kid"},
        claims={"sub": "user_id"},
        signature="signature",
        message="message",
    )
    headers = {"Authorization": "Bearer token"}

    valid_price_id = "price_1QBvVfJo4ha2Zj4nO3F0YLFr"
    valid_quantity = "2"
    response = client.post(
        f"/create-checkout-session?price_id={valid_price_id}&quantity={valid_quantity}",
        allow_redirects=False, headers=headers
    )
    logger.info(stripe_checkout_session_mock.call_count)
    assert response.status_code == 500
    assert stripe_checkout_session_mock.call_count == 1
