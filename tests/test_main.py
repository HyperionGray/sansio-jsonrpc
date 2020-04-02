import json
from unittest.mock import Mock

import pytest

from sansio_jsonrpc import *


def parse_bytes(b):
    """ A helper to convert a network byte string to a JSON object. """
    return json.loads(b.decode("ascii"))


def test_request():
    req = JsonRpcRequest(id=0, method="hello_world", params={"foo": "bar"})
    assert req.id == 0
    assert req.method == "hello_world"
    assert req.params == {"foo": "bar"}
    assert not req.is_notification

    # Request ID can be a float as long as the fractional part is zero.
    req2 = JsonRpcRequest(id=1.0, method="hello_world")
    assert req2.id == 1
    assert req2.method == "hello_world"
    assert req2.params is None


def test_invalid_request():
    with pytest.raises(JsonRpcInvalidRequestError):
        JsonRpcRequest(id=True, method="hello_world")

    with pytest.raises(JsonRpcInvalidRequestError):
        JsonRpcRequest(id=1.5, method="hello_world")

    with pytest.raises(JsonRpcInvalidRequestError):
        JsonRpcRequest(id=0, method=1)

    with pytest.raises(JsonRpcInvalidRequestError):
        JsonRpcRequest(id=0, method="hello_world", params=1)

    with pytest.raises(JsonRpcInvalidRequestError):
        JsonRpcRequest(id=0, method="hello_world", params=dict(), jsonrpc="1.0")


def test_request_to_json():
    req = JsonRpcRequest(id=0, method="hello_world", params={"foo": "bar"})
    assert req.to_json_dict() == {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "hello_world",
        "params": {"foo": "bar"},
    }

    req2 = JsonRpcRequest(id=0, method="hello_world")
    assert req2.to_json_dict() == {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "hello_world",
    }


def test_request_from_json():
    req = JsonRpcRequest.from_json_dict(
        {"jsonrpc": "2.0", "id": 0, "method": "hello_world", "params": {"foo": "bar"}}
    )
    assert req.id == 0
    assert req.method == "hello_world"
    assert req.params == {"foo": "bar"}

    req2 = JsonRpcRequest.from_json_dict(
        {"jsonrpc": "2.0", "id": 1, "method": "hello_world"}
    )
    assert req2.id == 1
    assert req2.method == "hello_world"
    assert req2.params is None


def test_notification():
    req = JsonRpcRequest.from_json_dict(
        {"jsonrpc": "2.0", "method": "hello_world", "params": {"foo": "bar"}}
    )
    assert req.method == "hello_world"
    assert req.params == {"foo": "bar"}
    assert req.is_notification
    assert req.to_json_dict() == {
        "jsonrpc": "2.0",
        "method": "hello_world",
        "params": {"foo": "bar"},
    }


def test_response_success():
    resp = JsonRpcResponse(id=0, result={"foo": "bar"})
    assert resp.id == 0
    assert resp.success
    assert resp.result == {"foo": "bar"}
    assert resp.error is None


def test_response_error():
    resp = JsonRpcResponse(
        id=0, error=JsonRpcError(code=-32700, message="An error occurred")
    )
    assert resp.id == 0
    assert not resp.success
    assert resp.result is None
    assert resp.error.code == -32700
    assert resp.error.message == "An error occurred"


def test_response_result_xor_error():
    """ The response must contain either a result or an error, but not both. """
    with pytest.raises(Exception):
        resp = JsonRpcResponse(
            id=0,
            result={"foo": "bar"},
            error=JsonRpcError(code=-32700, message="An error occurred"),
        )

    with pytest.raises(Exception):
        resp = JsonRpcResponse(id=0)


def test_invalid_response():
    with pytest.raises(JsonRpcInternalError):
        JsonRpcResponse(id=True, result="result")

    with pytest.raises(JsonRpcInternalError):
        JsonRpcResponse(id=1.5, result="result")

    with pytest.raises(JsonRpcInternalError):
        JsonRpcResponse(id=0, result=object())

    with pytest.raises(JsonRpcInternalError):
        JsonRpcResponse(id=0, error="foo")


def test_response_to_json():
    resp = JsonRpcResponse(id=0, result={"foo": "bar"})
    jd = resp.to_json_dict()
    assert jd == {
        "jsonrpc": "2.0",
        "id": 0,
        "result": {"foo": "bar"},
    }

    resp2 = JsonRpcResponse(
        id=1, error=JsonRpcError(code=-32700, message="An error occurred")
    )
    jd2 = resp2.to_json_dict()
    assert jd2 == {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32700, "message": "An error occurred"},
    }


def test_response_from_json():
    resp = JsonRpcResponse.from_json_dict(
        {"jsonrpc": "2.0", "id": 0, "result": {"foo": "bar"},}
    )
    assert resp.id == 0
    assert resp.success
    assert resp.result == {"foo": "bar"}
    assert resp.error is None

    resp2 = JsonRpcResponse.from_json_dict(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32700, "message": "An error occurred"},
        }
    )
    assert resp2.id == 1
    assert not resp2.success
    assert resp2.result is None
    assert resp2.error.code == -32700
    assert resp2.error.message == "An error occurred"


def test_client_multiplex_requests_and_responses():
    """
    This test sends 2 requests and the client receives the responses in backwards
    order.

    This tests that multiplexing is working.
    """
    client = JsonRpcPeer()
    handle_response = Mock()
    client.request(
        callback=handle_response, method="hello_world", params={"foo": "bar"}
    )
    handle_response2 = Mock()
    client.request(callback=handle_response2, method="goodbye_world")

    # When the client receives this response, it will invoke the corresponding callback.
    resp2 = client.recv(
        b'{"id":1, "result": {"goodbye": "farewell"}, "jsonrpc": "2.0"}'
    )
    assert handle_response.call_count == 0
    assert handle_response2.call_count == 1
    resp2 = handle_response2.call_args[0][0]
    assert resp2.id == 1
    assert resp2.success
    assert resp2.result == {"goodbye": "farewell"}
    assert resp2.error is None

    # When the client receives this response, it will invoke the other callback.
    resp = client.recv(
        b'{"id":0, "error": {"code": -32700, "message": "Error"}, "jsonrpc": "2.0"}'
    )
    assert handle_response.call_count == 1
    assert handle_response2.call_count == 1
    resp = handle_response.call_args[0][0]
    assert resp.id == 0
    assert not resp.success
    assert resp.result is None
    assert resp.error.code == -32700
    assert resp.error.message == "Error"


def test_client_notify():
    client = JsonRpcPeer()
    bytes_to_send = client.notify(method="hello_world", params={"foo": "bar"})
    assert parse_bytes(bytes_to_send) == {
        "method": "hello_world",
        "params": {"foo": "bar"},
        "jsonrpc": "2.0",
    }


def test_client_does_not_handle_requests():
    client = JsonRpcPeer()
    with pytest.raises(JsonRpcInternalError):
        client.recv(b'{"id": 0, "method": "hello_world", "jsonrpc": "2.0"}')


def test_server_handle_request():
    handle_request = Mock()
    server = JsonRpcPeer(request_handler=handle_request)

    # The first request gets a success response.
    server.recv(b'{"id": 0, "method": "get_foo", "jsonrpc": "2.0"}')
    assert handle_request.call_count == 1
    req = handle_request.call_args[0][0]
    assert req.id == 0
    assert req.method == "get_foo"
    assert req.params is None
    assert req.jsonrpc == "2.0"

    bytes_to_send = server.respond_with_result(req, {"foo": 1})
    assert parse_bytes(bytes_to_send) == {
        "id": 0,
        "result": {"foo": 1},
        "jsonrpc": "2.0",
    }

    # The second request gets an error response.
    server.recv(b'{"id": 0, "method": "get_bar", "jsonrpc": "2.0"}')
    assert handle_request.call_count == 2
    req2 = handle_request.call_args[0][0]
    try:
        raise JsonRpcMethodNotFoundError("Method not found: get_bar")
    except JsonRpcException as jre:
        bytes_to_send = server.respond_with_error(req2, jre.get_error())
    assert parse_bytes(bytes_to_send) == {
        "id": 0,
        "error": {"code": -32601, "message": "Method not found: get_bar"},
        "jsonrpc": "2.0",
    }


def test_server_json_parse_error():
    server = JsonRpcPeer()

    # Invalid ASCII
    with pytest.raises(JsonRpcParseError):
        server.recv(b"\xff")

    # Invalid JSON
    with pytest.raises(JsonRpcParseError):
        server.recv(b"{")


def test_response_contains_nonexistent_id():
    client = JsonRpcPeer()
    with pytest.raises(JsonRpcInternalError):
        client.recv(b'{"id": 0, "result": {"foo": "bar"}, "jsonrpc": "2.0"}')
