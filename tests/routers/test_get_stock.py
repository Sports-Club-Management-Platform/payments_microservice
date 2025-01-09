import logging
import time
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from auth.auth import get_current_user_id
from db.database import get_db
from main import app
from models.models import TicketStock, UserMapping
from routers.checkout import DOMAIN, expire_time

load_dotenv()
client = TestClient(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="module", autouse=True)
def mock_db():
    db = MagicMock(spec=Session)
    app.dependency_overrides[get_db] = lambda: db
    yield db

@patch("routers.checkout.get_stock_by_ticket_id")
def test_get_stock_success(get_stock_by_ticket_id_mock, mock_db):
    ticket_id = 1
    stock_value = {"stock": 10}
    get_stock_by_ticket_id_mock.return_value = stock_value

    response = client.get(f"/stock/{ticket_id}")
    assert response.status_code == 200
    assert response.json() == stock_value
    get_stock_by_ticket_id_mock.assert_called_once_with(mock_db, ticket_id)

@patch("routers.checkout.get_stock_by_ticket_id", side_effect=Exception("Database error"))
def test_get_stock_failure(get_stock_by_ticket_id_mock, mock_db):
    ticket_id = 1

    response = client.get(f"/stock/{ticket_id}")
    assert response.status_code == 500
    get_stock_by_ticket_id_mock.assert_called_once_with(mock_db, ticket_id)