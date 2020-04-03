import typing

JsonRpcId = typing.Union[int, float, str, None]
# Note that the union should contain JsonDict instead of dict, and JsonList instead of
# list, but recursive types are not currently supported in MyPy.
JsonPrimitive = typing.Union[int, float, str, dict, list, None]
JsonDict = typing.Dict[str, JsonPrimitive]
JsonList = typing.List[JsonPrimitive]
JsonRpcParams = typing.Union[JsonDict, JsonList]
