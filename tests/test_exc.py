import pytest

from sansio_jsonrpc import (
    JsonRpcApplicationError,
    JsonRpcError,
    JsonRpcException,
    JsonRpcParseError,
    JsonRpcReservedError,
)


def test_error():
    err = JsonRpcError(code=-32700, message="An error occurred")
    assert err.code == -32700
    assert err.message == "An error occurred"
    assert err.data is None
    assert (
        repr(err) == "JsonRpcError(code=-32700, message='An error occurred', data=None)"
    )

    err2 = JsonRpcError(code=-32700, message="An error occurred", data={"foo": "bar"})
    assert err2.code == -32700
    assert err2.message == "An error occurred"
    assert err2.data == {"foo": "bar"}


def test_error_to_json():
    err = JsonRpcError(code=-32700, message="An error occurred")
    assert err.to_json_dict() == {
        "code": -32700,
        "message": "An error occurred",
    }

    err2 = JsonRpcError(code=-32700, message="An error occurred", data={"foo": "bar"})
    assert err2.to_json_dict() == {
        "code": -32700,
        "message": "An error occurred",
        "data": {"foo": "bar"},
    }


def test_error_from_json():
    err = JsonRpcError.from_json_dict(
        {"code": -32700, "message": "An error occurred", "data": {"foo": "bar"},}
    )
    assert err.code == -32700
    assert err.message == "An error occurred"
    assert err.data == {"foo": "bar"}


def test_parse_exc():
    pe = JsonRpcParseError("Parse error")
    assert pe.code == -32700
    assert pe.message == "Parse error"
    assert pe.data is None
    assert (
        repr(pe) == "JsonRpcParseError<code=-32700, message='Parse error', data=None>"
    )


def test_parse_exc_data():
    pe = JsonRpcParseError("Parse error", {"foo": "bar"})
    assert pe.code == -32700
    assert pe.message == "Parse error"
    assert pe.data == {"foo": "bar"}
    assert (
        repr(pe) == "JsonRpcParseError<code=-32700, message='Parse error', "
        "data={'foo': 'bar'}>"
    )


def test_reserved_exc_from_error():
    """
    Given an error with a code from the reserved range, retrieve an appropriate
    exception instance for it.
    """
    err = JsonRpcError(code=-32700, message="Parse error")
    exc = JsonRpcException.exc_from_error(err)
    assert type(exc) is JsonRpcParseError
    assert exc.code == -32700
    assert exc.message == "Parse error"


def test_reserved_exc_from_error_generic():
    """
    Given an error with a code from the reserved range and no specific subclass, return
    a generic exception.
    """
    err = JsonRpcError(code=-32000, message="Generic error")
    exc = JsonRpcException.exc_from_error(err)
    assert type(exc) is JsonRpcReservedError
    assert exc.code == -32000
    assert exc.message == "Generic error"


def test_application_exc_from_error():
    """
    Given an error with a code from the unreserved range, retrieve an appropriate
    exception instance for it.
    """

    class MyAppError(JsonRpcApplicationError):
        ERROR_CODE = 1
        ERROR_MESSAGE = "Default message"

    err = JsonRpcError(code=1, message="Application error")
    exc = JsonRpcException.exc_from_error(err)
    assert type(exc) is MyAppError
    assert exc.code == 1
    assert exc.message == "Application error"


def test_reserved_error_must_use_reserved_code():
    with pytest.raises(RuntimeError):

        class MyReservedError(JsonRpcReservedError):
            ERROR_CODE = 1
            ERROR_MESSAGE = "Default message"


def test_application_error_must_use_unreserved_code():
    with pytest.raises(RuntimeError):

        class MyAppError(JsonRpcApplicationError):
            ERROR_CODE = -32768
            ERROR_MESSAGE = "Default message"
