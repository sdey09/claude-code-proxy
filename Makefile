.PHONY: setup up down restart status logs clean proxy

setup:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env — edit UPSTREAM_BASE_URL before continuing"; else echo ".env already exists, skipping"; fi
	$(MAKE) up

proxy:
	docker compose up -d --build proxy

up:
	docker compose up -d --build
	@echo "Proxy:      http://localhost:8888"
	@echo "Dashboard:  http://localhost:8888/dashboard/requests"
	@echo "Postgres:   localhost:5432  (claude/claude, db=claude_proxy)"

down:
	docker compose down

restart:
	docker compose restart

status:
	docker compose ps

logs:
	docker compose logs -f

logs-%:
	docker compose logs -f $*

clean:
	docker compose down -v
	docker system prune -f
