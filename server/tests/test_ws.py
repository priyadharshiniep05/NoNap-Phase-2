"""Tests for WebSocket real-time connection and role-filtered fan-out."""

import pytest
from server.app.realtime.connection_manager import manager


def test_ws_connection_rejected_without_token(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()


def test_ws_driver_connection_ack(client, driver_token, test_driver):
    with client.websocket_connect(f"/ws?token={driver_token}") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection_ack"
        assert ack["driver_id"] == test_driver.id
        assert "driver" in ack["message"]


def test_ws_ping_pong(client, driver_token):
    with client.websocket_connect(f"/ws?token={driver_token}") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection_ack"

        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
