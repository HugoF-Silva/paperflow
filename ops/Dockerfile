FROM python:3.12-slim

# The Python SDK shells out to the Claude Code CLI binary (needs Node).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl libcairo2 libgraphite2-3 nodejs npm \
 && curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.16.9/tectonic-0.16.9-x86_64-unknown-linux-gnu.tar.gz" -o /tmp/tectonic.tar.gz \
 && echo "f3c825128095dc3399ea11c08c18035b33050a216930c295c79e8eb11bd21de4  /tmp/tectonic.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
 && chmod +x /usr/local/bin/tectonic \
 && tectonic --version \
 && npm install -g @anthropic-ai/claude-code@latest \
 && rm -f /tmp/tectonic.tar.gz \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install --no-cache-dir -e /app

ENV PYTHONUNBUFFERED=1 OUTPUT_DIR=/app/src/results PYTHONPATH=/app/src
WORKDIR /app/src
