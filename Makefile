.PHONY: build run clean prep

papers results:
	mkdir -p $@
.paperflow.local.toml:
	touch .paperflow.local.toml
prep: papers results .paperflow.local.toml

build: prep
	docker compose build

run: build
	docker compose run --rm matcher

clean:
	rm -rf results/ .claude/
