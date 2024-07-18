"""Configuration for NoAuth."""

from os import getenv
from pathlib import Path
import tomllib
from typing import Any, Dict, Union

from pydantic import BaseModel, ValidationError


class OIDCConfig(BaseModel):
    """OIDC Configuration parameters."""

    issuer: str


class NoAuthConfig(BaseModel):
    """NoAuth Service Config.

    Configuration can be loaded from either a file or the environment or both.
    If both, environment overrides file.

    Environment variables will be of the form:
        NOAUTH_<config option in screaming snake case>=<value>
    For example:
        NOAUTH_ISSUER=http://example.com
    """

    passphrase: str
    oidc: OIDCConfig
    default: Dict[str, Any]

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
            print(table)

            config.update(table.get("noauth", {}))

        env_to_config = {
            f"NOAUTH_{field.upper()}": field for field in cls.model_fields.keys()
        }
        for var in env_to_config.keys():
            value = getenv(var)
            if value:
                config[env_to_config[var]] = value

        try:
            return cls.model_validate(config)
        except ValidationError as err:
            raise ValueError("Failed to load config") from err
