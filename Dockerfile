FROM python:3.11-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /repo

# Copy repository root to include all sub-agent packages
COPY . .

WORKDIR /repo/agents/luncher_agent

# Install dependencies directly into system environment
RUN uv pip install --system -r pyproject.toml

EXPOSE 8080

CMD ["uvicorn", "main:a2a_app", "--host", "0.0.0.0", "--port", "8080"]
