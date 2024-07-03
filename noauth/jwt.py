"""JWT utilities."""

import base64
import json
from typing import Union
from aries_askar import Key


def base64_urlencode_no_padding(value: Union[str, bytes]) -> str:
    """b64urlsafe encoding without padding."""
    value = value.encode() if isinstance(value, str) else value
    return base64.urlsafe_b64encode(value).strip(b"=").decode()


def base64_urldecode_no_padding(value: str) -> str:
    """b64urlsafe decoding without padding."""
    # Ensure correct padding
    padding_needed = 4 - (len(value) % 4)
    if padding_needed != 4:
        value += "=" * padding_needed

    return base64.urlsafe_b64decode(value).decode()


def sign(headers: dict, payload: dict, key: Key) -> str:
    """Sign and format a JWT."""
    enc_headers = base64_urlencode_no_padding(json.dumps(headers, separators=(",", ":")))
    enc_payload = base64_urlencode_no_padding(json.dumps(payload, separators=(",", ":")))
    sig_payload = f"{enc_headers}.{enc_payload}"
    sig = base64_urlencode_no_padding(key.sign_message(sig_payload))
    return f"{enc_headers}.{enc_payload}.{sig}"
