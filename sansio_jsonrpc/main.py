from __future__ import annotations
from dataclasses import dataclass
import itertools
import json
import typing

from .exc import (
    JsonRpcError,
    JsonRpcInternalError,
    JsonRpcInvalidRequestError,
    JsonRpcParseError,
)
from .types import (
    JsonDict,
    JsonList,
    JsonPrimitive,
    JsonRpcId,
    JsonRpcParams,
)


class MissingId:
    """ A sentinel class used to indicate that a request is missing an ID. """

    pass


def validate_json_rpc_id(id_: JsonRpcId, exc: typing.Callable):
    """
    Validation routine for the ID field.

    The type of exception raised varies depending on whether we are validating a request
    or a response. This sounds a bit silly, but it is part of the spec.
    """
    id_type = type(id_)
    if id_type is float and not typing.cast(float, id_).is_integer():
        raise exc("`id` number cannot have a fractional part.")
    # Note that isinstance() doesn't work for ID, because int is valid and bool is
    # not, but in Python bool is a subclass of int.
    elif id_type not in (int, float, str):
        raise exc("`id` must be a number, string, or null.")


@dataclass
class JsonRpcRequest:
    """ Represents a JSON RPC request. """

    id: typing.Union[JsonRpcId, MissingId]
    method: str
    params: typing.Optional[JsonRpcParams] = None
    jsonrpc: str = "2.0"

    @property
    def is_notification(self):
        """ True if this request is a notification. """
        return isinstance(self.id, MissingId)

    def __post_init__(self):
        """ Validation logic. """
        if not self.is_notification:
            validate_json_rpc_id(self.id, JsonRpcInvalidRequestError)

        if not isinstance(self.method, str):
            raise JsonRpcInvalidRequestError("`method` must be a string.")

        if not (self.params is None or isinstance(self.params, (dict, list))):
            raise JsonRpcInvalidRequestError("`params` must a list or object.")

        if self.jsonrpc != "2.0":
            raise JsonRpcInvalidRequestError('`jsonrpc` must be "2.0".')

    def to_json_dict(self) -> JsonDict:
        """ Convert to a JSON dictionary. """
        dict_ = typing.cast(JsonDict, {"method": self.method, "jsonrpc": self.jsonrpc})
        if not isinstance(self.id, MissingId):
            dict_["id"] = self.id
        if self.params is not None:
            dict_["params"] = self.params
        return dict_

    @classmethod
    def from_json_dict(cls, json_dict: JsonDict) -> JsonRpcRequest:
        """ Create a new request from a JSON dictionary. """
        id_ = typing.cast(typing.Optional[JsonRpcId], json_dict.get("id", MissingId()))
        params: typing.Optional[JsonDict]
        if "params" in json_dict:
            params = typing.cast(JsonDict, json_dict["params"])
        else:
            params = None
        return cls(
            id=id_,
            method=typing.cast(str, json_dict["method"]),
            params=params,
            jsonrpc=typing.cast(str, json_dict["jsonrpc"]),
        )


# This type is not defined in the types module because it relies on the class above.
JsonRpcRequestHandler = typing.Callable[[JsonRpcRequest], None]


@dataclass
class JsonRpcResponse:
    """ Represents a JSON RPC response. """

    id: JsonRpcId
    result: typing.Optional[JsonPrimitive] = None
    error: typing.Optional[JsonRpcError] = None
    jsonrpc: str = "2.0"

    def __post_init__(self):
        """ Validate data model. """
        if self.id is not None:
            validate_json_rpc_id(self.id, JsonRpcInternalError)

        if (self.result is None) == (self.error is None):
            raise JsonRpcInternalError(
                "Response must contain one of `result` or `error`."
            )

        if self.result and not isinstance(
            self.result, (int, float, bool, str, list, dict)
        ):
            raise JsonRpcInternalError("`result` must be a valid JSON type.")

        if self.error and not isinstance(self.error, JsonRpcError):
            raise JsonRpcInternalError("`error` must be a JsonRpcError.")

    @property
    def success(self):
        """ True if the response contains an error. """
        return self.error is None

    def to_json_dict(self) -> JsonDict:
        """ Convert to a JSON dictionary. """
        dict_ = typing.cast(JsonDict, {"id": self.id, "jsonrpc": self.jsonrpc})
        if self.success:
            dict_["result"] = self.result
        else:
            dict_["error"] = typing.cast(JsonRpcError, self.error).to_json_dict()
        return dict_

    @classmethod
    def from_json_dict(cls, json_dict: JsonDict) -> JsonRpcResponse:
        """ Return a new response from a JSON dictionary. """
        error: typing.Optional[JsonRpcError]
        if "error" in json_dict:
            error = JsonRpcError.from_json_dict(
                typing.cast(JsonDict, json_dict["error"])
            )
        else:
            error = None
        result = json_dict["result"] if "result" in json_dict else None
        return cls(
            id=typing.cast(typing.Union[int, str, None], json_dict["id"]),
            error=error,
            result=result,
            jsonrpc=typing.cast(str, json_dict["jsonrpc"]),
        )


# This type is not defined in the types module because it relies on the class above.
JsonRpcResponseCallback = typing.Callable[[JsonRpcResponse], None]


class JsonRpcPeer:
    """
    Represents a JSON RPC client or server.

    The specification distinguishes between client and server but then adds that the
    implementation may "fill both of those roles, even at the same time, to...the same
    client." The wording is imprecise, but it suggests that the most flexible way to
    implement JSON RPC is a combined client/server object.

    For example, the specification states that notifications can only be sent from
    client to server, but it would be helpful to send from server to client as well. In
    order to fit the spec we have to interpret the client and server as temporarily
    switching roles.
    """

    def __init__(
        self, request_handler: typing.Optional[JsonRpcRequestHandler] = None,
    ):
        """ Constructor """
        self._id_gen = itertools.count()

    def request(
        self, method: str, params: typing.Optional[JsonRpcParams] = None,
    ) -> typing.Tuple[JsonRpcId, bytes]:
        """
        Create a new request.

        :param method: The method to invoke on the JSON-RPC server.
        :param params: Parameters to pass to the remote method.
        """
        request_id = next(self._id_gen)
        req = JsonRpcRequest(id=request_id, method=method, params=params)
        bytes_to_send = json.dumps(req.to_json_dict()).encode("utf8")
        return request_id, bytes_to_send

    def notify(
        self, method: str, params: typing.Optional[JsonRpcParams] = None
    ) -> bytes:
        """ Create a notification and return a network representation. """
        req = JsonRpcRequest(id=MissingId(), method=method, params=params)
        return json.dumps(req.to_json_dict()).encode("utf8")

    def respond_with_result(
        self, request: JsonRpcRequest, result: JsonPrimitive
    ) -> bytes:
        """
        Create a success response to a given request and return a network
        representation.
        """
        resp = JsonRpcResponse(id=typing.cast(JsonRpcId, request.id), result=result)
        return json.dumps(resp.to_json_dict()).encode("utf8")

    def respond_with_error(
        self, request: typing.Optional[JsonRpcRequest], error: JsonRpcError
    ) -> bytes:
        """
        Create an error response to a given request and return a network representation.

        :param request: If a request ID could be parsed, pass the request object.
            Otherwise pass None.
        :param error: The error information to respond with.
        """
        # If the request could not be parsed
        request_id: typing.Optional[JsonRpcId]
        if request is None:
            request_id = None
        else:
            request_id = typing.cast(JsonRpcId, request.id)
        resp = JsonRpcResponse(id=request_id, error=error)
        return json.dumps(resp.to_json_dict()).encode("utf8")

    def parse(
        self, recv_bytes: bytes
    ) -> typing.Iterable[typing.Union[JsonRpcRequest, JsonRpcResponse]]:
        """
        Parse a network representation.

        :returns: an iterable of parsed objects
        :raises JsonRpcParseError: if the data cannot be parsed
        """

        try:
            recv_str = recv_bytes.decode("utf8")
        except Exception:
            raise JsonRpcParseError("Invalid ASCII encoding")

        try:
            recv_dict = json.loads(recv_str)
        except:
            raise JsonRpcParseError("Invalid JSON format")

        messages: typing.Iterable[typing.Union[JsonRpcRequest, JsonRpcResponse]]

        if "method" in recv_dict:
            messages = (JsonRpcRequest.from_json_dict(recv_dict),)
        elif "result" in recv_dict or "error" in recv_dict:
            messages = (JsonRpcResponse.from_json_dict(recv_dict),)
        else:
            msg = "Could parse a request or a response: "
            example = recv_str[:100] + ("..." if len(recv_str) > 100 else "")
            raise JsonRpcParseError(msg + example)

        return messages
