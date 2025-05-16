"""OpenID Connect."""

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import logging
from secrets import token_urlsafe
from time import time
from typing import List, Mapping, Optional, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

from aries_askar import Key
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.datastructures import UploadFile

from noauth.config import NoAuthConfig
from noauth.dependencies import config, default_user, key, store
from noauth.store import TemporalKVStore
from noauth.templates import templates
from noauth import jwt


router = APIRouter()
LOGGER = logging.getLogger(__name__)
TTL = 30


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
async def configuration(
    config: NoAuthConfig = Depends(config),
):
    """Return openid-configuration."""
    return OpenIDConfiguration(
        issuer=config.oidc.issuer,
        authorization_endpoint=f"{config.oidc.issuer}/oidc/authorize",
        token_endpoint=f"{config.oidc.issuer}/oidc/token",
        jwks_uri=f"{config.oidc.issuer}/.well-known/jwks.json",
        response_types_supported=["code"],
        subject_types_supported=["public"],
        id_token_signing_alg_values_supported=[
            config.client.id_token_signed_response_alg
        ],
    )


@router.get("/.well-known/jwks.json")
async def keys(
    key: Key = Depends(key),
):
    """Return keys."""
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
    store: TemporalKVStore = Depends(store),
    default_user: dict = Depends(default_user),
    config: NoAuthConfig = Depends(config),
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
    await store.set(key=f"oidc:{oidc.id}", value=oidc, ttl=30.0)
    claims = deepcopy(default_user)
    for scp in scope.split(" "):
        if scp == "openid":
            continue
        if config.scopes and scp in config.scopes:
            claims.update(config.scopes[scp])

    return templates.TemplateResponse(
        request=request,
        name="id_entry.html",
        context={"id": oidc.id, "claims": claims},
    )


@router.post("/oidc/submit/{id}", response_class=RedirectResponse)
async def submit_and_redirect(
    id: str,
    claims: str = Form(),
    store: TemporalKVStore = Depends(store),
):
    """Redirect back to the client."""
    try:
        parsed_claims = json.loads(claims)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid claims")

    oidc = await store.get("oidc:" + id)

    if oidc is None:
        raise HTTPException(403, "Unknown exchange")
    assert isinstance(oidc, OIDCRecord)

    assert oidc.code
    oidc.claims = parsed_claims
    await store.set(f"oidc:code:{oidc.code}", value=oidc, ttl=30.0)

    return RedirectResponse(
        url_with_query(oidc.redirect_uri, state=oidc.state, code=oidc.code),
        status_code=303,
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
    store: TemporalKVStore = Depends(store),
    key: Key = Depends(key),
    config: NoAuthConfig = Depends(config),
):
    """OIDC Token endpoint."""
    form = TokenForm.validate(await request.form())

    # More Validation
    # TODO Make sure redirect_uri matches
    # TODO Make sure client_id and secret match
    if form.grant_type != "authorization_code":
        raise HTTPException(400, "only authorization_code grant_type supported")

    oidc = await store.get(f"oidc:code:{form.code}")
    if oidc is None:
        raise HTTPException(404)
    assert isinstance(oidc, OIDCRecord)

    assert oidc.claims

    now = int(time())

    token = jwt.sign(
        headers={
            "alg": config.client.id_token_signed_response_alg,
            "kid": key.get_jwk_thumbprint(),
        },
        payload={
            "exp": now + 300,
            "iat": now,
            "auth_time": now,
            "jti": str(uuid4()),
            "iss": config.oidc.issuer,
            "aud": oidc.client_id,
            "typ": "ID",
            "azp": oidc.client_id,
            "sub": oidc.id,
            **oidc.claims,
        },
        key=key,
    )
    at = token_urlsafe()
    await store.set(f"oidc:token:{at}", None, ttl=300.0)

    response = {
        "token_type": "Bearer",
        "expires_in": 300,
        "scope": oidc.scope,
        "id_token": token,
        "access_token": token_urlsafe(),
    }
    LOGGER.debug("response: %s", response)
    return response
