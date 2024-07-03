"""OpenID Connect."""

from dataclasses import asdict, dataclass
import json
import logging
from secrets import token_urlsafe
from time import time
from typing import List, Mapping, Optional, Union, cast
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

from aries_askar import Key, Store as AStore
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.datastructures import UploadFile

from noauth.dependencies import Store, get, default_user
from noauth.templates import templates
from noauth import jwt
from noauth.models import AuthUserAttributes


router = APIRouter()
LOGGER = logging.getLogger("uvicorn.error." + __name__)


def url_with_query(url: str, **params: str) -> str:
    """Add query parameters to url."""
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    query.update(params)
    query = urlencode(query)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


@dataclass
class OIDCRecord:
    """Record for an in progress OIDC flow."""

    id: str
    client_id: str
    redirect_uri: str
    scope: str
    state: str
    claims: Optional[dict] = None
    code: Optional[str] = None

    def serialize(self) -> dict:
        """Serialize record."""
        return asdict(self)

    @classmethod
    def deserialize(cls, value: dict) -> "OIDCRecord":
        """Deserialize record from dictionary."""
        return cls(**value)


def oidc_error(redirect_uri: str, msg: str) -> RedirectResponse:
    """Return an error to the relying party."""
    url = url_with_query(redirect_uri, error=msg)
    return RedirectResponse(url)


@dataclass
class OpenIDConfiguration:
    """OpenID Config."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    response_types_supported: List[str]
    subject_types_supported: List[str]
    id_token_signing_alg_values_supported: List[str]


@router.get("/.well-known/openid-configuration")
async def configuration():
    """Return openid-configuration."""
    return OpenIDConfiguration(
        issuer="http://noauth:8080",
        authorization_endpoint="http://noauth:8080/oidc/authorize",
        token_endpoint="http://noauth:8080/oidc/token",
        jwks_uri="http://noauth:8080/oidc/keys",
        response_types_supported=["code"],
        subject_types_supported=["public"],
        id_token_signing_alg_values_supported=["EdDSA"],
    )


@router.get("/oidc/keys")
async def keys(
    store: AStore = Depends(get(Store)),
):
    """Return keys."""
    async with store.session() as session:
        key_entry = await session.fetch_key("jwt")
        if not key_entry:
            raise HTTPException(500)
        key = cast(Key, key_entry.key)

    jwk = json.loads(key.get_jwk_public())
    jwk["kid"] = key.get_jwk_thumbprint()
    return {"keys": [jwk]}


@router.get("/oidc/authorize", response_class=HTMLResponse)
async def authorize(
    request: Request,
    response_type: str = Query(),
    client_id: str = Query(),
    redirect_uri: str = Query(),
    scope: str = Query(),
    state: str = Query(),
    store: AStore = Depends(get(Store)),
    default_user: dict = Depends(get(default_user)),
):
    """OIDC Authorize endpoint."""
    if response_type != "code":
        return oidc_error(redirect_uri, "Bad response_type")

    if "openid" not in scope:
        return oidc_error(redirect_uri, "openid missing from scope")

    if not state:
        return oidc_error(redirect_uri, "Bad state")

    code = token_urlsafe()
    oidc = OIDCRecord(
        id=str(uuid4()),
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
        code=code,
    )
    async with store.session() as session:
        await session.insert(
            category="oidc",
            name=oidc.id,
            value_json=oidc.serialize(),
        )

    print(default_user)
    return templates.TemplateResponse(
        request=request,
        name="id_entry.html",
        context={"id": oidc.id, "default": default_user},
    )


@router.post("/oidc/submit/{id}", response_class=RedirectResponse)
async def submit_and_redirect(
    request: Request,
    id: str,
    store: AStore = Depends(get(Store)),
):
    """Redirect back to the client."""
    form = await request.form()
    async with store.session() as session:
        oidc_entry = await session.fetch("oidc", id, for_update=True)

        if not oidc_entry:
            raise HTTPException(403, "Unknown exchange")

        oidc = OIDCRecord.deserialize(oidc_entry.value_json)
        assert oidc.code
        oidc.claims = dict(form)
        await session.replace(
            "oidc", id, value_json=oidc.serialize(), tags={"code": oidc.code}
        )

    return RedirectResponse(
        url_with_query(oidc.redirect_uri, state=oidc.state, code=oidc.code),
        status_code=307,
    )


@dataclass
class TokenForm:
    """Token form."""

    grant_type: str
    client_id: str
    client_secret: str
    redirect_uri: str
    code: str

    @classmethod
    def validate(cls, form: Mapping[str, Union[UploadFile, str]]) -> "TokenForm":  # noqa: C901
        """Validate and return."""
        # Basic Validation
        grant_type = form.get("grant_type")
        if not grant_type:
            raise HTTPException(400, "missing grant_type")
        if not isinstance(grant_type, str):
            raise HTTPException(400, "bad grant_type")

        client_id = form.get("client_id")
        if not client_id:
            raise HTTPException(400, "missing client_id")
        if not isinstance(client_id, str):
            raise HTTPException(400, "bad client_id")

        client_secret = form.get("client_secret")
        if not client_secret:
            raise HTTPException(400, "missing client_secret")
        if not isinstance(client_secret, str):
            raise HTTPException(400, "bad client_secret")

        redirect_uri = form.get("redirect_uri")
        if not redirect_uri:
            raise HTTPException(400, "missing redirect_uri")
        if not isinstance(redirect_uri, str):
            raise HTTPException(400, "bad redirect_uri")

        code = form.get("code")
        if not code:
            raise HTTPException(400, "missing code")

        if not isinstance(code, str):
            raise HTTPException(400, "bad code")

        return cls(grant_type, client_id, client_secret, redirect_uri, code)


@router.post("/oidc/token")
async def token(
    request: Request,
    store: AStore = Depends(get(Store)),
):
    """OIDC Token endpoint."""
    form = TokenForm.validate(await request.form())

    # More Validation
    # TODO Make sure redirect_uri matches
    # TODO Make sure client_id and secret match
    if form.grant_type != "authorization_code":
        raise HTTPException(400, "only authorization_code grant_type supported")

    async with store.session() as session:
        oidc_entries = await session.fetch_all("oidc", {"code": form.code}, limit=2)
        if len(oidc_entries) > 1:
            LOGGER.error("Duplicate code found: %s", form.code)
            raise HTTPException(500)

        oidc = OIDCRecord.deserialize(oidc_entries[0].value_json)
        key_entry = await session.fetch_key("jwt")
        if not key_entry:
            LOGGER.error("key missing")
            raise HTTPException(500)
        key = cast(Key, key_entry.key)

    assert oidc.claims
    user, extra = AuthUserAttributes.deserialize_with_extra(oidc.claims)

    now = int(time())

    token = jwt.sign(
        headers={
            "alg": "EdDSA",
            "kid": key.get_jwk_thumbprint(),
        },
        payload={
            "exp": now + 300,
            "iat": now,
            "auth_time": now,
            "jti": str(uuid4()),
            "iss": "http://noauth:8080",
            "aud": oidc.client_id,
            "typ": "ID",
            "azp": oidc.client_id,
            "sub": oidc.id,
            **user.to_claims(),
            **extra,
        },
        key=key,
    )

    return {
        "token_type": "Bearer",
        "expires_in": 300,
        "scope": oidc.scope,
        "id_token": token,
    }
