FROM python:3.11-slim

# Install uv for extremely fast, robust dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy only the package configuration to cache dependency installation
COPY pyproject.toml .

# Install dependencies directly into the system python environment
RUN uv pip install --system -r pyproject.toml

# Copy the rest of the application code
COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:a2a_app", "--host", "0.0.0.0", "--port", "8080"]
