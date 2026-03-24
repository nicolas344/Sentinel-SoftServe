import os
from functools import lru_cache

import jwt
import requests
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import ECAlgorithm

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

bearer_scheme = HTTPBearer()


@lru_cache(maxsize=1)
def _get_supabase_public_key():
    """Obtiene y cachea la clave pública de Supabase para verificar tokens ES256."""
    response = requests.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", timeout=5)
    response.raise_for_status()
    keys = response.json().get("keys", [])
    if not keys:
        raise ValueError("No se encontraron claves públicas en Supabase JWKS")
    return ECAlgorithm.from_jwk(keys[0])


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "HS256":
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        else:
            public_key = _get_supabase_public_key()
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                options={"verify_aud": False},
            )

        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
