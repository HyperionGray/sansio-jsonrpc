# JSON-RPC v2.0 Sans I/O

[![PyPI](https://img.shields.io/pypi/v/sansio-jsonrpc.svg?style=flat-square)](https://pypi.org/project/sansio-jsonrpc/)
![Python Versions](https://img.shields.io/pypi/pyversions/sansio-jsonrpc.svg?style=flat-square)
![MIT License](https://img.shields.io/github/license/HyperionGray/sansio-jsonrpc.svg?style=flat-square)
[![Build Status](https://img.shields.io/travis/com/HyperionGray/sansio-jsonrpc.svg?style=flat-square&branch=master)](https://travis-ci.com/HyperionGray/sansio-jsonrpc)
[![codecov](https://codecov.io/gh/HyperionGray/sansio-jsonrpc/branch/master/graph/badge.svg)](https://codecov.io/gh/HyperionGray/sansio-jsonrpc)

This project provides [a Sans I/O](https://sans-io.readthedocs.io/) implementation of
[JSON-RPC v 2.0](https://www.jsonrpc.org/specification). This means that the library
handles all of the encoding, decoding, framing, and logic required by the protocol
specification, but it does not implement any I/O (input or output). In order to use this
library, you need to either to use a downstream project that wraps I/O around this
project or else write your own I/O wrapper.

## Client Example

This example illustrates what the library does and how it needs to be integrated into
an I/O framework of your choosing.

```python
from sansio_jsonrpc import JsonRpcPeer, JsonRpcParseError, JsonRpcException

client = JsonRpcPeer()
request_id, bytes_to_send = client.request(
    method='open_vault_door',
    args={'employee': 'Mark', 'pin': 1234},
)
```

First, we instantiate the client. We call the `request` method to create a new JSON-RPC
request and convert it into a `bytes` representation that is suitable for sending to the
server. The method also returns a `request_id`, which is a hashable value that can be
used to correlate any future response back to the request that initiated it.

```python
connection.send(bytes_to_send)
received_bytes = connection.recv()
```

Remember, this is a Sans I/O library, so it does not do any networking itself. It is the
caller's responsibility to transfer data to and from the remote machine. This block
shows a hypothetical I/O framework being used to send the pending request and receive
the response as `bytes`, but this can be implemented with any I/O framework of your
choosing.

```python
try:
    messages = client.parse(received_bytes)
except JsonRpcParseError as pe:
    print('Exception while parsing response', pe)
```

In this block, we feed the data received from the remote machine into the client
object's `parse()` method. This method parses the incoming data and returns an iterable
containing messages sent by the server. (In the current implementation, the iterable
always contains exactly 1 message, but the API is designed this way to allow for future
enhancements such as a streaming JSON parser that can return 0-n messages after parsing
each chunk of data.)

```python
for response in messages:
    assert isinstance(response, JsonRpcResponse)
    print('received a response:', response.id)
    if response.is_success:
        print('success:', response.result)
    else:
        print('error:', response.error)
        exc = JsonRpcException.exc_from_error(response.error)
```

Finally, we iterate over the messages. In the case of a client, these messages will
always be `JsonRpcReponse` objects, which contain either result or error information.
The `response.id` field should match the `request_id` obtained earlier.

If you want an error response to raise an exception, you can call
`JsonRpcException.exc_from_error(...)` and it will construct an exception for you. The
exception system is described in a separate section below. Of course, be careful where
you throw the exception, since throwing an exception while reading multiple responses
will result in the rest of the responses being ignored. In a concurrent system, you
probably want to raise the exception to the code path that called `request()`.

In a concurrent system, you will also want to multiplex requests and responses on the
same connection. This library does not implement multiplexing itself because
multiplexing with appropriate flow control (see "Back Pressure" below) is going to
depend on the transport and I/O framework you are using.

## Server Example

This example shows how to receive a JSON-RPC request and dispatch a response.

```python
from sansio_jsonrpc import (
    JsonRpcPeer,
    JsonRpcException,
    JsonRpcParseError,
    JsonRpcMethodNotFoundError,
)

server = JsonRpcPeer()
```

This example starts out the same way as the client: instantiating a `JsonRpcPeer`
object. Note that the client and server implementation are actually in the same class!

This might be surprising at first but it is the most flexible way to implement JSON-RPC.
For example, the specification says that a notification is a special type of request,
and a request can only be sent from client to server. But there are scenarios where it
would be useful to have the server send notifications to the client, e.g. a
publish/subscribe system. The specification says that:

> One implementation of this specification could easily fill both of those roles, even
> at the same time, to other different clients or the same client.

This is why the library implements both roles in a single class. The choice to name the
object `server` is just a convention to help us remember what's going on.

```python
received_bytes = connection.recv()
```

This block shows the hypothetical I/O framework again. As a server, we just want to wait
for a client to send us something.

```python
try:
    messages = server.parse(received_bytes)
except JsonRpcParseError as pe:
    bytes_to_send = server.respond_with_error(request=None, error=pe.get_error())
    connection.send(bytes_to_send)
    return
```

Next, we want to parse the incoming data. If a parse error is raised here, then we
should send back a response and we should not iterate over the messages, because
`messages` was not actually returned!. Because we were unable to parse a request, we set
`request=None` in the response.

```
for request in messages:
    assert isinstance(request, JsonRpcRequest)

    try:
        # Handle request here and send a response.
        result = handle_request(request)
        bytes_to_send = server.respond_with_result(request=request, result=result)
    except JsonRpcException as jre:
        bytes_to_send = server.respond_with_error(request=request, error=pe.get_error())

    connection.send(bytes_to_send)
```

Next, we iterate over the received messages. For a server, each message should be a
`JsonRpcRequest`. The implementation of `handle_request(...)` is up to you! You should
handle each request by returning a result. The `respond_with_result(...)` method
produces an appropriate JSON-RPC response, which you should then send to the client.

If an error occurs in your handler, you should raise one of the built-in exceptions or a
custom subclass of `JsonRpcApplicationError`. For example, if you don't have a handler
for a given method, you should raise `JsonRpcMethodNotFoundError`. Exceptions are
described more fully below.

## Exceptions

The exception system in this library is designed to make error-handling as Pythonic as
possible, abstracting over the details of the JSON-RPC protocol as much as possible. All
exceptions in this module inherit from `JsonRpcException`, so this is a good choice for
a catch-all exception handler. All exceptions have an error code and a message.
Exceptions can also optionally have a `data` field which can be set to any valid JSON
data type.

There are also specialized errors in the library that correspond to specific JSON-RPC
error codes in the specification. For example, if you receive data that cannot be
decoded into a valid JSON-RPC request, the specification calls for a -32700 error, and
this library raises a `JsonRpcParseError` to make it easy to catch this specific
condition. If the server sends

The specification also allows you to define your own error codes. There are

Exceptions are used in two ways in this library. First of all, the library itself can
raise exceptions. For example in `recv()`, it can raise `JsonRpcParseError` as described
above. The second usage is that the remote peer might send you a response that contains
an error object. In this case, you may want to convert that error into an exception so
you can raise it.

The static method `JsonRpcException.exc_from_error(...)` converts an error into an
exception. This method automatically selects the appropriate subclass of
`JsonRpcException`. For example, if the remote peer sent you error code -32700, this
method converts that into a `JsonRpcParseError`. Some error codes are reserved for
implementations to define their own error codes, e.g. -32099 is reserved in the
specification but not assigned any meaning. If the remote peer sends this error code,
then this method will raise `JsonRpcReservedError`.

The specification also has unreserved error codes that are available for defining
application-specific errors. You can use these in your own code in two different ways.
The first approach is to catch/raise `JsonRpcApplicationError` and set/check the error
code to your application-defined value. The second approach is to create your own
subclass of `JsonRpcApplicationError`. Here's an example:

```python
from sansio_jsonrpc import JsonRpcApplicationError


class MyApplicationError1(JsonRpcApplicationError):
    ERROR_CODE = 1
    ERROR_MESSAGE = "My application error type 1"


class MyApplicationError2(JsonRpcApplicationError):
    ERROR_CODE = 2
    ERROR_MESSAGE = "My application error type 2"
```

The `JsonRpcException.exc_from_error(...)` method will automatically select the
appropriate subclass. For example if the server sends error code 1, then the method will
return a `MyApplicationError1` instance, even though that class is defined in _your
code_! The library uses some metaclass black magic to make this work.

## Back Pressure

As a SANS I/O library, this package does not implement any sort of flow control. If the
peer is sending you data faster than you can handle it, and you keep reading it, then
your process's memory usage will continually grow until it runs out of memory or the
kernel terminates it. Back pressure means signalling to the peer that it should stop
sending data for a bit until your process can catch up. The specifics of back pressure
really depend on what transport protocol and I/O framework you are using. For example,
TCP has flow control capabilities, and most implementations will automatically apply
back pressure if you simply stop reading from the socket. Therefore, if you use TCP with
this library, you should be careful to read from the socket only when you are ready to
process another message. If you eagerly read from the socket into an unbounded user
space buffer (such as a queue), then your code will not benefit from TCP's flow control,
because the kernel will see an empty buffer and it will keep filling it up.

## Developing

The project uses MyPy for type checking and Black for code formatting. Poetry is used to
manage dependencies and to build releases.
