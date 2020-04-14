# The targets in this makefile should be executed inside Poetry, i.e. `poetry run make
# check`.

check: mypy test

coverage:
	codecov

mypy:
	mypy sansio_jsonrpc/

test:
	pytest --cov=sansio_jsonrpc/ tests/
	coverage report -m
