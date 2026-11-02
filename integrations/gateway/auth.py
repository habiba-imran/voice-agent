"""Verify a short server-to-server assertion. Browser requests cannot choose their principal."""

import hashlib
import hmac
import time

import jwt


class Unauthenticated(Exception):
    pass


def authenticate(authorization, secret):
    try:
        if not authorization.startswith("Bearer ") or len(authorization) > 4096:
            raise ValueError
        payload = jwt.decode(
            authorization.removeprefix("Bearer "),
            secret,
            algorithms=["HS256"],
            audience="voice-gateway",
            issuer="voice-web",
            options={"require": ["exp", "iat", "nbf", "sub", "network"]},
        )
        if any(type(payload[key]) is not int for key in ("iat", "exp", "nbf")):
            raise ValueError
        if not 0 < payload["exp"] - payload["iat"] <= 60 or payload["iat"] < time.time() - 60:
            raise ValueError
        for key in ("sub", "network"):
            if not isinstance(payload[key], str) or not 1 <= len(payload[key]) <= 256:
                raise ValueError
        return tuple(
            hmac.new(secret.encode(), f"{key}:{payload[key]}".encode(), hashlib.sha256).hexdigest()
            for key in ("sub", "network")
        )
    except (ValueError, TypeError, jwt.PyJWTError):
        raise Unauthenticated from None
