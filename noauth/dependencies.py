"""Common dependencies."""

from contextvars import Context, ContextVar
from typing import Callable, TypeVar, cast
from aries_askar import Store as AStore

from noauth.models import OIDCConfig


Store: ContextVar[AStore] = ContextVar("Store")
default_user: ContextVar[dict] = ContextVar("default_user")
oidc_config: ContextVar[OIDCConfig] = ContextVar("oidc_config")

context = Context()

T = TypeVar("T")


def get(var: ContextVar[T]) -> Callable[[], T]:
    """Get a context var as a dependency."""

    def _get():
        return context.get(var)

    return cast(Callable[[], T], _get)


def setup(
    store: AStore,
    oidc: OIDCConfig,
    user: dict,
):
    """Setup context."""

    def _setup():
        Store.set(store)
        oidc_config.set(oidc)
        default_user.set(user)

    context.run(_setup)
