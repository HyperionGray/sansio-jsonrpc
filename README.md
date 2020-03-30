# JSON-RPC Sans I/O

This project provides [a Sans I/O](https://sans-io.readthedocs.io/) implementation of
[JSON RPC v 2.0](https://www.jsonrpc.org/specification). This means that the library
handles all of the encoding, decoding, framing, and logic required by the protocol
specification, but it does not implement any I/O (input or output). In order to use this
library, you need to either to use a downstream project that wraps I/O around this
project or else write your own I/O wrapper.

## Client Example

This example illustrates what the library does and how it needs to be integrated into
an I/O framework of your choosing.

```python
>>> client = JsonRpcClient()
>>> cmd = client.command(method='open_vault_door', args={'employee': 'Mark', 'pin': 1234})
>>> bytes_to_send = cmd.to_bytes()
```

First, we instantiate the client. Then we create a new command and convert it into the
`bytes` representation that we will send to the server.

```python
>>> connection.send(bytes_to_send)
>>> received_bytes = connection.recv()
```

This block shows a hypothetical I/O framework being used to send the pending command
and receive the response as `bytes`. This can be any I/O framework of your choosing.

```python
response = client.parse(received_bytes)
print(response.is_success)
# True
print(response.result)
# {"vault_status": "open"}
```

Finally, we parse the `bytes` received from the server and the library converts it into
a response object that we can check for errors, response values, etc.

## Server Example

TBD

## Developing

The project uses MyPy for type checking and Black for code formatting. Poetry is used to
manage dependencies and to build releases.
