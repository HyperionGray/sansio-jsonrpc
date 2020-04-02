check: mypy test

mypy:
	mypy sansio_jsonrpc/

test:
	pytest --cov=sansio_jsonrpc/ tests/
	coverage report -m
