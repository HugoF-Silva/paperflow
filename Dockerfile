FROM python:3.12-slim

# Node.js is required by claude-agent-sdk because the Python SDK drives the
# Claude Code CLI binary under the hood, and that binary depends on a Node.js
# runtime when launched outside an environment that already bundles one.
RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs npm \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code@latest

WORKDIR /app

COPY pyproject.toml /app/
COPY batch_venue_matcher /app/batch_venue_matcher
RUN pip install --no-cache-dir -e /app

# Skill source files (canonical location). The runtime entrypoint copies
# the selected set into /app/.claude/skills/ before any worker fires.
COPY skills /app/skills

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "batch_venue_matcher.cli"]
CMD ["run"]
