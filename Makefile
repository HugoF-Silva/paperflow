.PHONY: run-openai run-anthropic down prune

.paperflow.local.toml:
	touch .paperflow.local.toml

run-openai: .paperflow.local.toml
	docker compose run --build --rm matcher --api openai

run-anthropic: .paperflow.local.toml
	docker compose run --build --rm matcher --api anthropic

down:
	docker compose down -v

prune:
	docker system prune -f -a --volumes && docker buildx history rm --all
