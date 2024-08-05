"""Retrieving a token."""

import json
import logging
from time import time
from typing import cast
from uuid import uuid4

from aries_askar import Key, Store as AStore
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from noauth import jwt
from noauth.config import NoAuthConfig
from noauth.oidc import url_with_query
from noauth.templates import templates
from noauth.dependencies import config, default_token, store

router = APIRouter(prefix="/manual")
LOGGER = logging.getLogger("uvicorn.error." + __name__)


@router.get("/token", response_class=HTMLResponse)
async def manual_token(
    request: Request,
    default_token: dict = Depends(default_token),
):
    """Generate a token."""
    query = request.query_params
    claims = dict(query)
    return templates.TemplateResponse(
        request=request,
        name="token_entry.html",
        context={"default": {**default_token, **claims}},
    )


@router.post("/token")
async def post_manual_token_and_redirect(
    claims: str = Form(),
    valid_for: str = Form(),
    store: AStore = Depends(store),
    config: NoAuthConfig = Depends(config),
):
    """Submit token form and get signed token."""
    try:
        parsed_claims = json.loads(claims)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid claims")

    valid = int(valid_for)

    async with store.session() as session:
        key_entry = await session.fetch_key("jwt")
        if not key_entry:
            LOGGER.error("key missing")
            raise HTTPException(500)
        key = cast(Key, key_entry.key)

    now = int(time())

    token = jwt.sign(
        headers={
            "alg": "EdDSA",
            "kid": key.get_jwk_thumbprint(),
        },
        payload={
            "exp": now + valid,
            "iat": now,
            "jti": str(uuid4()),
            "iss": config.oidc.issuer,
            **parsed_claims,
        },
        key=key,
    )
    return RedirectResponse(
        url_with_query("/manual/token/complete", token=token, **parsed_claims),
        status_code=303,
    )


@router.get("/token/complete", response_class=HTMLResponse)
async def manual_token_complete(
    request: Request,
    token: str,
):
    """Display token."""
    query = request.query_params
    claims = dict(query)
    del claims["token"]

    enc_headers, enc_payload, sig = token.split(".")
    headers = json.loads(jwt.base64_urldecode_no_padding(enc_headers))
    payload = json.loads(jwt.base64_urldecode_no_padding(enc_payload))
    token_value = "\n.\n".join(
        [json.dumps(headers, indent=2), json.dumps(payload, indent=2), sig]
    )
    return templates.TemplateResponse(
        request=request,
        name="token_complete.html",
        context={
            "token": token,
            "token_value": token_value,
            "new": url_with_query("/manual/token", **claims),
        },
    )
