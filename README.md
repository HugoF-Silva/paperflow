# Paperflow — Academia Perks

Paperflow packages **Academia Perks**, one academic-publishing plugin with two
agent skills:

- **venue-matcher** finds publication venues that fit a `.docx` paper, ranks
  them, separates currently open venues from those opening soon, and records a
  venue-specific LaTeX template URL when it can verify one.
- **converter** turns a `.docx` paper into a venue-oriented LaTeX submission,
  either after matching or from a supplied venue/template source.

The plugin lives at `src/plugins/academia-perks/`. It is a single shared
payload, with both Codex and Claude Code manifests; there are no longer
provider-specific `academia-perks-openai` or `academia-perks-claude` plugin
copies.

## Install the plugin

### Codex

The repository marketplace at `.agents/plugins/marketplace.json` exposes the
`academia-perks` plugin, whose Codex manifest is
`src/plugins/academia-perks/.codex-plugin/plugin.json`. Add this repository as
a marketplace in Codex, then install **Academia Perks** from that marketplace.

### Claude Code

Claude Code users can use the marketplace at
`.claude-plugin/marketplace.json`, which installs the same plugin through its
Claude manifest at `src/plugins/academia-perks/.claude-plugin/plugin.json`:

```bash
claude plugin marketplace add /path/to/paperflow
claude plugin install academia-perks@paperflow
```

For a hosted repository, replace the local path with the repository shorthand
or Git URL supported by Claude Code. See the [Claude Code marketplace
guide](https://code.claude.com/docs/en/plugin-marketplaces) for the supported
source forms.

## Use it

Ask the agent to find a venue for a paper, match venues in a folder, or convert
a paper using a selected venue or local LaTeX template. The skills accept only
`.docx` files placed directly in the selected input directory; nested papers
and other file types are ignored.

The bundled inner agents use the OpenAI Agents SDK. Therefore, regardless of
whether the outer agent is Codex or Claude Code, a run needs an
`OPENAI_API_KEY`. The skills also select an OpenAI-compatible inner-agent model
through `VENUE_MATCHER_MODEL` or `CONVERTER_MODEL`; normal plugin use handles
that for the agent. Long-running matching and conversion are best run from a
local agent environment rather than a browser-only chat session.

Matching creates a `results/` directory in the outer agent's working directory:

```text
results/
├── _execution.log       # detailed harness/agent execution stream
├── _progress.log        # matcher batch progress
└── <paper-stem>/
    └── ranking.md
```

Conversion writes its per-paper workspace beneath the same results root and
records batch progress in `_converter_progress.log`.

## Develop locally with Docker

The repository's Docker harness runs the shared plugin through an OpenAI outer
agent. Docker Desktop must be running.

```bash
cp ops/.env.example ops/.env
cp ops/.paperflow.local.toml.example ops/.paperflow.local.toml
# Add one or more .docx papers directly under src/papers/
make -C ops run
```

Set `OPENAI_API_KEY` in `ops/.env`. `OPENAI_MODEL` is optional and defaults to
`gpt-5.4-mini`. The Compose service mounts the repository's `src/` directory at
`/app/src`, so inputs come from `src/papers/` and results appear in
`src/results/` on the host. `make -C ops run` starts the matcher-and-converter
workflow with `--api=openai`.

For a standalone conversion, provide exactly one source:

```bash
make -C ops run-converter chosen-venue='Venue A template: https://venue.example/template'
make -C ops run-converter template-path='/app/src/templates/venue-a.zip'
```

`chosen-venue` must identify the venue and include its template URL or
supporting evidence. A `template-path` is a container path; place the template
under the repository's `src/` tree and refer to it as `/app/src/...`.

The harness exposes `MAX_PARALLEL` (default `auto`), `MAX_RALPH` (default `4`),
and `INNER_MAX_TURNS` (minimum/default `50`) as developer controls. Set them in
`ops/.env` only when you need to tune a local run. `make -C ops down` removes
the Compose containers and volumes; `make -C ops prune` additionally runs a
global Docker image/volume prune.

### Current provider boundary

`harness/cli.py` and `harness/outer_agent.py` still contain legacy Anthropic
branches, but this checkout no longer includes the old
`plugins/academia-perks-claude` payload those branches resolve. The supported
Docker harness path is consequently OpenAI-only. This does not affect the
Claude Code marketplace: it installs the shared `academia-perks` plugin above,
whose bundled work is performed with the OpenAI API key supplied for the run.

## How the workflows work

The outer agent starts one inner agent per paper. Each inner agent may run a
Ralph loop, carrying a compact recap into the next pass until it has a terminal
result. The matcher uses one geographic audience scope from the paper: its sole
stated scope, the first if several are stated, or **International** when none is
given. It ranks only venues whose primary audience fits that scope.

When conversion is requested after matching, the skills use completed
per-paper results rather than guessing from files. For a single completed
match, the agent asks the user to select from the ranked venues before it
converts. For a standalone conversion, the agent requires one explicit
`chosen-venue` source or one local `template-path` source. The converter uses
Pandoc to preserve document structure and verifies the generated submission
with Tectonic.
