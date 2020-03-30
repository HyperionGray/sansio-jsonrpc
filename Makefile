check: mypy test

mypy:
	mypy jsonrpc/

test:
	pytest --cov=jsonrpc/ tests/
