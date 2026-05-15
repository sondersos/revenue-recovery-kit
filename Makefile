.PHONY: up down build migrate seed test shell logs demo

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python scripts/seed.py

test:
	docker compose exec api python -m pytest tests/ -q

shell:
	docker compose exec api bash

logs:
	docker compose logs -f api

demo:
	@bash scripts/demo.sh
