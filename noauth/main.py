"""NoAuth."""

from contextlib import asynccontextmanager
import logging
from os import getenv
from pathlib import Path

from aries_askar import Key, KeyAlg, Store as AStore
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from noauth.config import NoAuthConfig
from noauth.dependencies import setup

from noauth import oidc
from noauth import manual

ACAPY = getenv("ACAPY", "http://localhost:3001")

logging.getLogger("uvicorn.error").setLevel(logging.DEBUG)


@asynccontextmanager
async def init_deps(app: FastAPI):
    """Test connectivity to ACA-Py."""
    config = NoAuthConfig.load("./noauth.toml")
    store_path = Path("/var/lib/noauth/store.db")
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store = await AStore.provision(
        f"sqlite://{store_path}", "kdf:argon2i", config.passphrase
    )

    async with store.session() as session:
        key_entry = await session.fetch_key("jwt")
        if not key_entry:
            key = Key.generate(KeyAlg.ED25519)
            await session.insert_key("jwt", key)

    setup(store, config, config.default, config.token or {})

    try:
        yield
    finally:
        await store.close()


app = FastAPI(lifespan=init_deps)

app.include_router(oidc.router)
app.include_router(manual.router)
app.mount("/", StaticFiles(directory="static"), name="static")
