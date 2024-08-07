"""Configuration for NoAuth."""

from os import getenv
from pathlib import Path
import tomllib
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, ValidationError


class OIDCConfig(BaseModel):
    """OIDC Configuration parameters."""

    issuer: str


class ClientConfig(BaseModel):
    """OIDC Client configuration."""

    client_id: str
    client_secret: str
    id_token_signed_response_alg: str


class NoAuthConfig(BaseModel):
    """NoAuth Service Config.

    Configuration must be loaded from a file.
    By default, noauth.toml or NOAUTH_CONFIG is read.
    """

    oidc: OIDCConfig
    client: ClientConfig
    default: Dict[str, Any]
    token: Optional[Dict[str, Any]] = None
    scopes: Optional[Dict[str, Any]] = None

    @classmethod
    def load(cls, path: Union[str, Path, None] = None) -> "NoAuthConfig":
        """Load config from a file."""
        config = {}
        path = path or getenv("NOAUTH_CONFIG")
        if not path:
            raise ValueError("config path missing")

        if isinstance(path, str):
            path = Path(path)

        if path.exists():
            with open(path, "rb") as f:
                table = tomllib.load(f)

            config.update(table.get("noauth", {}))

        try:
            return cls.model_validate(config)
        except ValidationError as err:
            raise ValueError("Failed to load config") from err
