.PHONY: setup up down restart status logs clean proxy

setup:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env — edit UPSTREAM_BASE_URL before continuing"; else echo ".env already exists, skipping"; fi
	$(MAKE) up

proxy:
	docker compose up -d --build proxy

up:
	docker compose up -d --build
	@echo "Proxy:      http://localhost:8888"
	@echo "Grafana:    http://localhost:3000  (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Loki:       http://localhost:3100"

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
