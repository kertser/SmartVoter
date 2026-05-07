FROM python:3.13-slim

RUN pip install uv --no-cache-dir

WORKDIR /app

# Tell uv explicitly where the virtual environment lives so it never conflicts
# with any VIRTUAL_ENV value that might arrive from the host or an .env file.
ENV VIRTUAL_ENV=/app/.venv \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

