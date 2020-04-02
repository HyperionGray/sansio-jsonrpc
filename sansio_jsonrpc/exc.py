from __future__ import annotations
from dataclasses import dataclass
import typing


from .types import JsonDict, JsonList, JsonPrimitive


@dataclass
class JsonRpcError:
    """ Represents an error in the JSON RPC protocol. """

    code: int
    message: str
    data: typing.Optional[JsonDict] = None

    def to_json_dict(self) -> JsonDict:
        """ Convert to a JSON dictionary. """
        dict_ = typing.cast(JsonDict, {"code": self.code, "message": self.message})
        if self.data is not None:
            dict_["data"] = self.data
        return dict_

    @classmethod
    def from_json_dict(cls, json_dict: JsonDict) -> JsonRpcError:
        """ Return a new response from a JSON dictionary. """
        return cls(
            code=typing.cast(int, json_dict["code"]),
            message=typing.cast(str, json_dict["message"]),
            data=typing.cast(typing.Optional[JsonDict], json_dict.get("data")),
        )

    def __repr__(self) -> str:
        """ Return string representation. """
        data = repr(self.data)
        message = repr(self.message)
        return f"JsonRpcError(code={self.code}, message={message}, data={data})"


class JsonRpcException(Exception):
    """
    A base class for JSON-RPC exceptions.

    This exception is never thrown by ``sansio-jsonrpc`` but since it is an ancestor for
    JSON-RPC exceptions, it is useful in `try/except` blocks as a catch-all. You
    generally should not instantiate this class yourself. Instead, use
    class:`JsonRpcApplicationException`, either directly or by creating your own
    subclass of it.
    """

    def __init__(self, error: JsonRpcError):
        """ Constructor. """
        self._error: JsonRpcError = error

    @property
    def code(self):
        """ The JSON-RPC error code. """
        return self._error.code

    @property
    def message(self):
        """ A JSON-RPC error message. """
        return self._error.message

    @property
    def data(self) -> typing.Optional[JsonDict]:
        """ Arbitrary data attached to the error. """
        return self._error.data

    def get_error(self) -> JsonRpcError:
        """ Return the error underlying this exception. """
        return self._error

    def __repr__(self):
        cls = self.__class__.__name__
        code = self._error.code
        data = repr(self._error.data)
        message = repr(self._error.message)
        return f"{cls}<code={code}, message={message}, data={data}>"

    @staticmethod
    def exc_from_error(error: JsonRpcError) -> JsonRpcException:
        """
        Create a new exception derived from the given error.

        When you receive an error response, you may want to raise a corresponding
        exception. This method finds an appropriate exception subclass that matches the
        error's numeric code and instantiates it. It uses some metaclass black magic so
        that it can even return custom subclasses you define in your own code!
        """
        exc: JsonRpcException
        if -32768 <= error.code <= -32000:
            exc = JsonRpcReservedError.exc_from_error(error)
        else:
            exc = JsonRpcApplicationError.exc_from_error(error)
        return exc


class JsonRpcReservedErrorMeta(type):
    """
    This metaclass builds a map of error codes to classes.

    This is used to find the right class to instantiate when an error response is
    received. It also enforces the requirement that reserved error codes must be in the
    range [-32768, -32000].
    """

    _error_classes: typing.Dict[int, type] = dict()

    def __init__(cls, name, bases, attrs):
        if cls.ERROR_CODE is not None and (
            cls.ERROR_CODE < -32768 or cls.ERROR_CODE > -32000
        ):
            raise RuntimeError(
                "Subclasses of JsonRpcReservedError must set ERROR_CODE in range "
                "[-32768, -32000]."
            )
        JsonRpcReservedErrorMeta._error_classes[cls.ERROR_CODE] = cls


class JsonRpcReservedError(JsonRpcException, metaclass=JsonRpcReservedErrorMeta):
    """
    An exception corresponding to the range of codes reserved by the spec.

    The error code must be in the range [-32768, -32000].
    """

    ERROR_CODE: int = -32000
    ERROR_MESSAGE: str = "JSON-RPC reserved error"

    def __init__(
        self,
        message: typing.Optional[str] = None,
        data: typing.Optional[JsonDict] = None,
    ):
        error = JsonRpcError(self.ERROR_CODE, message or self.ERROR_MESSAGE, data)
        super().__init__(error)

    @staticmethod
    def exc_from_error(error: JsonRpcError) -> JsonRpcReservedError:
        """
        Create a new reserved exception that corresponds to the error code.

        This first searches for a subclass that is registered with the given error code.
        If it does not find such a subclass, then it returns a ``JsonRpcReservedError``
        instead.
        """
        cls = JsonRpcReservedError._error_classes.get(error.code, JsonRpcReservedError)
        return cls(error.message, error.data)


class JsonRpcApplicationErrorMeta(type):
    """
    This metaclass builds a map of error codes to classes.

    This is used to find the right class to instantiate when an error response is
    received. It also enforces the requirement that application error codes must **not**
    be in the range [-32768, -32000].
    """

    _error_classes: typing.Dict[int, type] = dict()

    def __init__(cls, name, bases, attrs):
        if (
            cls.ERROR_CODE is not None
            and cls.ERROR_CODE >= -32768
            and cls.ERROR_CODE <= -32000
        ):
            raise RuntimeError(
                "Subclasses of JsonRpcReservedError must set ERROR_CODE outside the "
                " range [-32768, -32000]."
            )
        JsonRpcApplicationErrorMeta._error_classes[cls.ERROR_CODE] = cls


class JsonRpcApplicationError(JsonRpcException, metaclass=JsonRpcApplicationErrorMeta):
    """
    An exception corresponding to the unreserved range of error codes.

    The error code must **not** be in the range [-32768, -32000].
    """

    ERROR_CODE: int = -1
    ERROR_MESSAGE: str = "JSON-RPC"

    def __init__(
        self,
        message: typing.Optional[str] = None,
        *,
        data: typing.Optional[JsonDict] = None,
        code: typing.Optional[int] = None,
    ):
        error = JsonRpcError(
            code or self.ERROR_CODE, message or self.ERROR_MESSAGE, data
        )
        super().__init__(error)

    @staticmethod
    def exc_from_error(error: JsonRpcError) -> JsonRpcApplicationError:
        cls = JsonRpcApplicationError._error_classes.get(
            error.code, JsonRpcApplicationError
        )
        return cls(error.message, data=error.data)


class JsonRpcParseError(JsonRpcReservedError):
    """ Invalid JSON was received by the server. """

    ERROR_CODE = -32700
    ERROR_MESSAGE = "Invalid JSON was received by the server."


class JsonRpcInvalidRequestError(JsonRpcReservedError):
    """ The JSON sent is not a valid Request object. """

    ERROR_CODE = -32600
    ERROR_MESSAGE = "The JSON sent is not a valid Request object."


class JsonRpcMethodNotFoundError(JsonRpcReservedError):
    """
    The method does not exist / is not available.

    This exception is never thrown by ``sansio-jsonrpc``. It should be thrown in
    downstream libraries.
    """

    ERROR_CODE = -32601
    ERROR_MESSAGE = "The method does not exist / is not available."


class JsonRpcInvalidParamsError(JsonRpcReservedError):
    """
    Invalid method parameter(s).

    This exception is never thrown by ``sansio-jsonrpc``. It should be thrown in
    downstream libraries.
    """

    ERROR_CODE = -32602
    ERROR_MESSAGE = "Invalid method parameter(s)."


class JsonRpcInternalError(JsonRpcReservedError):
    """
    Internal JSON-RPC error.
    """

    ERROR_CODE = -32602
    ERROR_MESSAGE = "Internal JSON-RPC error."
