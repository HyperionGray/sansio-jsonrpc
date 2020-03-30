import json

import pytest

from jsonrpc import (
    JsonRpcClient,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcServer,
)


def parse_bytes(b):
    """ A helper to convert a network byte string to a JSON object. """
    return json.loads(b.decode("ascii"))


def test_request():
    req = JsonRpcRequest(id=0, method="hello_world", params={"foo": "bar"})
    assert req.id == 0
    assert req.method == "hello_world"
    assert req.params == {"foo": "bar"}

    req2 = JsonRpcRequest(id=1, method="hello_world")
    assert req2.id == 1
    assert req2.method == "hello_world"
    assert req2.params is None


def test_request_to_json():
    req = JsonRpcRequest(id=0, method="hello_world", params={"foo": "bar"})
    jd = req.to_json_dict()
    assert jd == {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "hello_world",
        "params": {"foo": "bar"},
    }


def test_request_from_json():
    req = JsonRpcRequest.from_json_dict(
        {"jsonrpc": "2.0", "id": 0, "method": "hello_world", "params": {"foo": "bar"},}
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


def test_error():
    err = JsonRpcError(code=-32700, message="An error occurred")
    assert err.code == -32700
    assert err.message == "An error occurred"
    assert err.data is None

    err2 = JsonRpcError(code=-32700, message="An error occurred", data={"foo": "bar"})
    assert err2.code == -32700
    assert err2.message == "An error occurred"
    assert err2.data == {"foo": "bar"}


def test_error_to_json():
    err = JsonRpcError(code=-32700, message="An error occurred")
    jd = err.to_json_dict()
    assert jd == {
        "code": -32700,
        "message": "An error occurred",
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
    client = JsonRpcClient()
    bytes_to_send = client.send(method="hello_world", params={"foo": "bar"})
    assert parse_bytes(bytes_to_send) == {
        "id": 0,
        "method": "hello_world",
        "params": {"foo": "bar"},
        "jsonrpc": "2.0",
    }

    bytes_to_send2 = client.send(method="goodbye_world")
    assert parse_bytes(bytes_to_send2) == {
        "id": 1,
        "method": "goodbye_world",
        "jsonrpc": "2.0",
    }

    resp2 = client.recv(
        b'{"id":1, "result": {"goodbye": "farewell"}, "jsonrpc": "2.0"}'
    )
    assert resp2.id == 1
    assert resp2.success
    assert resp2.result == {"goodbye": "farewell"}
    assert resp2.error is None
    assert resp2.request.id == 1
    assert resp2.request.method == "goodbye_world"

    resp = client.recv(
        b'{"id":0, "error": {"code": -32700, "message": "Error"}, "jsonrpc": "2.0"}'
    )
    assert resp.id == 0
    assert not resp.success
    assert resp.result is None
    assert resp.error.code == -32700
    assert resp.error.message == "Error"
    assert resp.request.id == 0
    assert resp.request.method == "hello_world"


def test_invalid_id_in_response():
    pass


# TODO: cover other error conditions
