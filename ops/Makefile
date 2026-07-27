.PHONY: run run-converter down prune

.paperflow.local.toml:
	touch .paperflow.local.toml

run: .paperflow.local.toml
	docker compose run --build --rm matcher-or-converter --api=openai --todo=matcher-and-converter

run-converter: .paperflow.local.toml
	$(if $(strip $(chosen-venue)$(template-path)),,$(error exactly one of chosen-venue or template-path is required))
	$(if $(and $(strip $(chosen-venue)),$(strip $(template-path))),$(error exactly one of chosen-venue or template-path is required),)
	docker compose run --build --rm matcher-or-converter --api=openai --todo=converter $(if $(strip $(chosen-venue)),--chosen-venue="$(chosen-venue)",--template-path="$(template-path)")

down:
	docker compose down -v

prune:
	docker system prune -f -a --volumes && docker buildx history rm --all
