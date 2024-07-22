"""Common dependencies."""

from contextvars import Context, ContextVar
from typing import Callable, TypeVar, cast
from aries_askar import Store as AStore

from noauth.config import NoAuthConfig


Store: ContextVar[AStore] = ContextVar("Store")
default_user: ContextVar[dict] = ContextVar("default_user")
default_token: ContextVar[dict] = ContextVar("default_token")
Config: ContextVar[NoAuthConfig] = ContextVar("Config")

context = Context()

T = TypeVar("T")


def get(var: ContextVar[T]) -> Callable[[], T]:
    """Get a context var as a dependency."""

    def _get():
        return context.get(var)

    return cast(Callable[[], T], _get)


def setup(
    store: AStore,
    config: NoAuthConfig,
    user: dict,
    token: dict,
):
    """Setup context."""

    def _setup():
        Store.set(store)
        Config.set(config)
        default_user.set(user)
        default_token.set(token)

    context.run(_setup)
