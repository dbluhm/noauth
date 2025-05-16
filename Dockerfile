FROM python:3.11-slim-bookworm as base
WORKDIR /usr/src/app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Setup project
COPY pyproject.toml uv.lock README.md ./
COPY default.noauth.toml ./noauth.toml
RUN uv sync --locked --no-install-project

COPY healthcheck.py ./
COPY noauth ./noauth
COPY static ./static

RUN uv sync --locked

ENTRYPOINT ["uv", "run", "fastapi", "dev", "noauth/main.py"]
CMD ["--host", "0.0.0.0", "--port", "80"]
