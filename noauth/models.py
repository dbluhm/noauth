"""Common models."""

from dataclasses import asdict, dataclass
from typing import Tuple


@dataclass
class OIDCConfig:
    """OIDC Configuration."""

    issuer: str

    @classmethod
    def deserialize(cls, value: dict) -> "OIDCConfig":
        """Deserialize config."""
        return cls(**value)


@dataclass
class AuthUserAttributes:
    """Attributes we gather about users to authenticate."""

    given_name: str
    family_name: str
    email: str
    preferred_username: str
    roles: str

    def serialize(self) -> dict:
        """Serialize."""
        return asdict(self)

    def to_claims(self) -> dict:
        """Serialize to claims."""
        return {
            "given_name": self.given_name,
            "family_name": self.family_name,
            "email": self.email,
            "preferred_username": self.preferred_username,
            "roles": self.roles.split(" "),
        }

    @classmethod
    def deserialize(cls, value: dict) -> "AuthUserAttributes":
        """Deserialize the record."""
        return cls(**value)

    @classmethod
    def deserialize_with_extra(cls, value: dict) -> Tuple["AuthUserAttributes", dict]:
        """Deserialize record and return tuple of record and unparsed values."""
        fields = (
            "given_name",
            "family_name",
            "email",
            "preferred_username",
            "roles",
        )
        known = {}
        unknown = {}
        for key in value.keys():
            if key in fields:
                known[key] = value[key]
            else:
                unknown[key] = value[key]

        return cls.deserialize(known), unknown
