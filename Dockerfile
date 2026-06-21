FROM python:3.12-slim

# The Python SDK shells out to the Claude Code CLI binary (needs Node).
RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs npm \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code@latest

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY harness /app/harness
COPY skills /app/skills
COPY .claude-plugin /app/.claude-plugin
RUN pip install --no-cache-dir -e /app

ENV PYTHONUNBUFFERED=1 OUTPUT_DIR=/work/results
ENTRYPOINT ["python", "-m", "harness.cli"]
