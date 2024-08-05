"""NoAuth."""

import logging
from os import getenv

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from noauth.dependencies import setup

from noauth import oidc
from noauth import manual

ACAPY = getenv("ACAPY", "http://localhost:3001")

logging.getLogger("uvicorn.error").setLevel(logging.DEBUG)


app = FastAPI(lifespan=setup)

app.include_router(oidc.router)
app.include_router(manual.router)
app.mount("/", StaticFiles(directory="static"), name="static")
