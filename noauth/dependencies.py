"""Common dependencies."""

from contextvars import Context, ContextVar
from typing import Callable, TypeVar, cast
from aries_askar import Store as AStore

from noauth.models import AuthUserAttributes


Store: ContextVar[AStore] = ContextVar("Store")
default_user: ContextVar[AuthUserAttributes] = ContextVar("default_user")

context = Context()

T = TypeVar("T")


def get(var: ContextVar[T]) -> Callable[[], T]:
    """Get a context var as a dependency."""

    def _get():
        return context.get(var)

    return cast(Callable[[], T], _get)


def setup(
    store: AStore,
    user: AuthUserAttributes,
):
    """Setup context."""

    def _setup():
        Store.set(store)
        default_user.set(user)

    context.run(_setup)
