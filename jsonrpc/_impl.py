from __future__ import annotations
from dataclasses import dataclass
import itertools
import json
import typing


# Note that the union should contain JsonDict instead of dict, and JsonList instead of
# list, but recursive types are not currently supported in MyPy.
JsonPrimitive = typing.Union[int, float, str, dict, list, None]
JsonDict = typing.Dict[str, JsonPrimitive]
JsonList = typing.List[JsonPrimitive]


@dataclass
class JsonRpcRequest:
    """ Represents a JSON RPC request. """

    id: typing.Union[int, str, None]
    method: str
    params: typing.Optional[JsonDict] = None
    jsonrpc: str = "2.0"

    def to_json_dict(self) -> JsonDict:
        """ Convert to a JSON dictionary. """
        dict_ = typing.cast(
            JsonDict, {"id": self.id, "method": self.method, "jsonrpc": self.jsonrpc,}
        )
        if self.params is not None:
            dict_["params"] = self.params
        return dict_

    @classmethod
    def from_json_dict(cls, json_dict: JsonDict) -> JsonRpcRequest:
        """ Create a new request from a JSON dictionary. """
        params: typing.Optional[JsonDict]
        if "params" in json_dict:
            params = typing.cast(JsonDict, json_dict["params"])
        else:
            params = None
        return cls(
            id=typing.cast(typing.Union[int, str, None], json_dict["id"]),
            method=typing.cast(str, json_dict["method"]),
            params=params,
            jsonrpc=typing.cast(str, json_dict["jsonrpc"]),
        )


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


@dataclass
class JsonRpcResponse:
    """ Represents a JSON RPC response. """

    id: typing.Union[int, str, None]
    jsonrpc: str = "2.0"
    result: typing.Optional[JsonPrimitive] = None
    error: typing.Optional[JsonRpcError] = None

    _request: typing.Optional[JsonRpcRequest] = None

    def __post_init__(self):
        """ Validate data model. """
        if (self.result is None) == (self.error is None):
            raise Exception()  # TODO what exception?? (update test)

    @property
    def request(self):
        return self._request

    @request.setter
    def request(self, value):
        self._request = value

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


class JsonRpcClient:
    """ Represents a JSON RPC client. """

    def __init__(self, json_dump=json.dumps, json_load=json.loads):
        """ Constructor """
        self._id_gen = itertools.count()
        self._json_dump = json_dump
        self._json_load = json_load
        self._pending_requests = dict()

    def send(self, method: str, params: JsonDict = None) -> bytes:
        """ Create a new command and return a network representation. """
        command_id = next(self._id_gen)
        req = JsonRpcRequest(id=command_id, method=method, params=params)
        self._pending_requests[command_id] = req
        return self._json_dump(req.to_json_dict()).encode("ascii")

    def recv(self, response_bytes: bytes) -> JsonRpcResponse:
        """ Receive a network representation and turn it into a JSON RPC response. """
        json_dict = typing.cast(
            JsonDict, self._json_load(response_bytes.decode("ascii"))
        )
        response = JsonRpcResponse.from_json_dict(json_dict)
        try:
            response.request = self._pending_requests.pop(response.id)
        except KeyError:
            raise Exception("invalid ID in response")  # TODO what exception to raise?
        return response


class JsonRpcServer:
    def __init__(self, json_dump=json.dumps, json_load=json.loads):
        pass
