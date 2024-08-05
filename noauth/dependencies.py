"""Common dependencies."""

from contextlib import asynccontextmanager
from pathlib import Path
from aries_askar import Key, KeyAlg, Store as AStore
from fastapi import FastAPI

from noauth.config import NoAuthConfig


_store: AStore
_default_user: dict
_default_token: dict
_config: NoAuthConfig


def store() -> AStore:
    """Return store."""
    global _store
    return _store


def default_user() -> dict:
    """Return default_user."""
    global _default_user
    return _default_user


def default_token() -> dict:
    """Return default_token."""
    global _default_token
    return _default_token


def config() -> NoAuthConfig:
    """Return config."""
    global _config
    return _config


@asynccontextmanager
async def setup(app: FastAPI):
    """Setup context."""
    global _store
    global _default_user
    global _default_token
    global _config
    _config = NoAuthConfig.load("./noauth.toml")
    store_path = Path("/var/lib/noauth/store.db")
    store_path.parent.mkdir(parents=True, exist_ok=True)
    _store = await AStore.provision(
        f"sqlite://{store_path}", "kdf:argon2i", _config.passphrase
    )

    async with _store.session() as session:
        key_entry = await session.fetch_key("jwt")
        if not key_entry:
            key = Key.generate(KeyAlg.ED25519)
            await session.insert_key("jwt", key)

    _default_user = _config.default
    _default_token = _config.token or {}

    try:
        yield
    finally:
        await _store.close()
