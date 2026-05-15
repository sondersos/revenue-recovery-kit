.PHONY: up down build migrate seed test test-fe e2e shell logs demo web api

up:
	docker compose up -d --build

down:
	docker compose down -v

build:
	docker compose build

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python scripts/seed.py

test:
	docker compose exec api python -m pytest tests/ -q && cd frontend && npm test

test-be:
	docker compose exec api python -m pytest tests/ -q

test-fe:
	cd frontend && npm test

e2e:
	cd frontend && npx playwright test

shell:
	docker compose exec api bash

web:
	cd frontend && npm run dev

api:
	docker compose logs -f api

logs:
	docker compose logs -f

demo:
	@bash scripts/demo.sh
