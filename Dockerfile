FROM python:3.11-slim-bookworm as base
WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y curl && apt-get clean
ENV PDM_VERSION=2.15.4
ENV PDM_HOME=/opt/pdm
RUN curl -sSL https://pdm-project.org/install-pdm.py | python3 -


FROM python:3.11-slim-bookworm
WORKDIR /usr/src/app
COPY --from=base /opt/pdm /opt/pdm

ENV PATH="/opt/pdm/bin:$PATH"

# Setup project
COPY pyproject.toml pdm.lock README.md ./
COPY default.noauth.toml ./noauth.toml
RUN mkdir noauth && touch noauth/__init__.py
RUN pdm install

COPY healthcheck.py ./
COPY noauth ./noauth
COPY static ./static

ENTRYPOINT ["pdm", "run", "fastapi", "dev", "noauth/main.py"]
CMD ["--host", "0.0.0.0", "--port", "80"]
