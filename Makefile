.PHONY: build run validate clean

# Host dirs Docker will bind-mount. Created here so Docker doesn't make
# them root-owned directories on first run. .paperflow.local.toml must
# exist as a *file* (empty = no extras) so Docker doesn't mount a dir
# in its place.
papers results:
	mkdir -p $@
.paperflow.local.toml:
	touch .paperflow.local.toml

prep: papers results .paperflow.local.toml

build: prep
	docker compose build

# Resolve and validate the skill set; exit without launching any agent.
# Useful after editing .paperflow.local.toml.
validate: build
	docker compose run --rm matcher validate-skills

run: build
	docker compose run --rm matcher

clean:
	rm -rf results/ .claude/
