"""Common models."""

from dataclasses import dataclass


@dataclass
class OIDCConfig:
    """OIDC Configuration."""

    issuer: str

    @classmethod
    def deserialize(cls, value: dict) -> "OIDCConfig":
        """Deserialize config."""
        return cls(**value)
