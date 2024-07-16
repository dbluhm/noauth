"""NoAuth."""

from contextlib import asynccontextmanager
import logging
from os import getenv
import tomllib

from aries_askar import Key, KeyAlg, Store as AStore
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from noauth.dependencies import setup
from noauth.models import OIDCConfig

from . import oidc

ACAPY = getenv("ACAPY", "http://localhost:3001")

logging.getLogger("uvicorn.error").setLevel(logging.DEBUG)


@asynccontextmanager
async def init_deps(app: FastAPI):
    """Test connectivity to ACA-Py."""
    store_key = AStore.generate_raw_key()
    store = await AStore.provision("sqlite://:memory:", "raw", store_key)
    with open("noauth.toml", "rb") as f:
        config = tomllib.load(f)

    default_user = config["noauth"]["default"]
    if not isinstance(default_user, dict):
        raise ValueError("noauth.default must be a table")

    oidc = OIDCConfig.deserialize(config["noauth"]["oidc"])

    async with store.session() as session:
        key_entry = await session.fetch_key("jwt")
        if not key_entry:
            key = Key.generate(KeyAlg.ED25519)
            await session.insert_key("jwt", key)

    setup(store, oidc, default_user)

    try:
        yield
    finally:
        await store.close()


app = FastAPI(lifespan=init_deps)

app.include_router(oidc.router)
app.mount("/", StaticFiles(directory="static"), name="static")
