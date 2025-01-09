from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from crud.crud import (create_ticket_stock, create_user_mapping,
                       decrement_stock, get_stock_by_price_id,
                       get_stock_by_ticket_id, get_stock_ticket_id_by_price_id,
                       get_user_mapping_by_uuid, increment_stock,
                       update_ticket_stock)
from models.models import TicketStock, UserMapping


def test_create_user_mapping():
    mock_db = MagicMock(spec=Session)
    user_id = "user_123"

    result = create_user_mapping(mock_db, user_id)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    assert isinstance(result, UserMapping)
    assert result.user_id == user_id

def test_get_user_mapping_by_uuid():
    mock_db = MagicMock(spec=Session)
    uuid = "uuid_123"
    mock_db.query().filter().first.return_value = UserMapping(uuid=uuid, user_id="user_123")

    result = get_user_mapping_by_uuid(mock_db, uuid)

    assert isinstance(result, UserMapping)
    assert result.uuid == uuid

def test_create_ticket_stock():
    mock_db = MagicMock(spec=Session)
    ticket_id = 1
    stripe_price_id = "price_123"
    stock = 100

    result = create_ticket_stock(mock_db, ticket_id, stripe_price_id, stock)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    assert isinstance(result, TicketStock)
    assert result.ticket_id == ticket_id
    assert result.stripe_price_id == stripe_price_id
    assert result.stock == stock

def test_update_ticket_stock():
    mock_db = MagicMock(spec=Session)
    ticket_id = 1
    stock = 50
    mock_db.query().filter().first.return_value = TicketStock(ticket_id=ticket_id, stripe_price_id="price_123", stock=100)

    result = update_ticket_stock(mock_db, ticket_id, stock)

    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    assert isinstance(result, TicketStock)
    assert result.ticket_id == ticket_id
    assert result.stock == stock

def test_decrement_stock():
    mock_db = MagicMock(spec=Session)
    price_id = "price_123"
    quantity = 10
    mock_db.query().filter().first.return_value = TicketStock(ticket_id=1, stripe_price_id=price_id, stock=100)

    result = decrement_stock(mock_db, price_id, quantity)

    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    assert isinstance(result, TicketStock)
    assert result.stock == 90

def test_increment_stock():
    mock_db = MagicMock(spec=Session)
    price_id = "price_123"
    quantity = 10
    mock_db.query().filter().first.return_value = TicketStock(ticket_id=1, stripe_price_id=price_id, stock=100)

    result = increment_stock(mock_db, price_id, quantity)

    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    assert isinstance(result, TicketStock)
    assert result.stock == 110

def test_get_stock_by_ticket_id():
    mock_db = MagicMock(spec=Session)
    ticket_id = 1
    mock_db.query().filter().first.return_value = TicketStock(ticket_id=ticket_id, stripe_price_id="price_123", stock=100)

    result = get_stock_by_ticket_id(mock_db, ticket_id)

    assert isinstance(result, dict)
    assert result["stock"] == 100

def test_get_stock_by_price_id():
    mock_db = MagicMock(spec=Session)
    price_id = "price_123"
    mock_db.query().filter().first.return_value = TicketStock(ticket_id=1, stripe_price_id=price_id, stock=100)

    result = get_stock_by_price_id(mock_db, price_id)

    assert isinstance(result, dict)
    assert result["stock"] == 100

def test_get_stock_ticket_id_by_price_id():
    mock_db = MagicMock(spec=Session)
    price_id = "price_123"
    mock_db.query().filter().first.return_value = TicketStock(ticket_id=1, stripe_price_id=price_id, stock=100)

    result = get_stock_ticket_id_by_price_id(mock_db, price_id)

    assert result == 1