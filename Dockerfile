FROM python:3.12-slim

WORKDIR /app

# Install curl and system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples

# Install dependencies
RUN uv sync --frozen || uv sync

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

# Default entrypoint starts universal-mcp in SSE mode on port 8080
ENTRYPOINT ["universal-mcp"]
CMD ["serve", "--config", "examples/universal-mcp.yaml", "--transport", "sse", "--port", "8080"]
