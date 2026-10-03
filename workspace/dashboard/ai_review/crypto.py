"""Seal platform credentials with the hub auth-secret. Never store API keys in plaintext."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from os_auth import _b64, _b64d, _secret


def seal(plaintext: str) -> str:
    raw = (plaintext or "").encode("utf-8")
    nonce = secrets.token_bytes(16)
    key = hashlib.sha256(_secret() + nonce).digest()
    stream = (key * ((len(raw) // len(key)) + 1))[: len(raw)]
    cipher = bytes(a ^ b for a, b in zip(raw, stream))
    mac = hmac.new(_secret(), nonce + cipher, hashlib.sha256).digest()
    return _b64(nonce + mac + cipher)


def unseal(token: str) -> str:
    if not token:
        return ""
    blob = _b64d(token)
    nonce, mac, cipher = blob[:16], blob[16:48], blob[48:]
    expect = hmac.new(_secret(), nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expect):
        raise ValueError("credential_mac_mismatch")
    key = hashlib.sha256(_secret() + nonce).digest()
    stream = (key * ((len(cipher) // len(key)) + 1))[: len(cipher)]
    return bytes(a ^ b for a, b in zip(cipher, stream)).decode("utf-8")
