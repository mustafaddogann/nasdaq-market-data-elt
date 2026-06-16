.PHONY: test lint up down db-shell

test:
	pytest

lint:
	ruff check .

up:
	docker compose up airflow-webserver airflow-scheduler

down:
	docker compose down

db-shell:
	@echo "This project uses Snowflake as the warehouse. Use Snowsight or SnowSQL."
