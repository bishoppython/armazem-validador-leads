.PHONY: setup test lint demo docker

setup:
	uv sync --all-extras

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

# Base sintética de 10 mil leads + validação offline (MX simulado), em ~2 s.
demo:
	uv run leads gerar --saida dados/leads_sujos.csv
	uv run leads validar dados/leads_sujos.csv -o dados/leads_validados.csv --relatorio dados/relatorio.json --mx simulado

docker:
	docker compose run --rm leads
