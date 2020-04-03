check: mypy test

coverage:
	poetry run codecov

mypy:
	poetry run mypy sansio_jsonrpc/

test:
	poetry run pytest --cov=sansio_jsonrpc/ tests/
	poetry run coverage report -m
