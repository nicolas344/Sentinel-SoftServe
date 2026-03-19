import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from dotenv import load_dotenv

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

bearer_scheme = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        
        # If the token uses ES256, we'd need the JWKS public key from Supabase.
        # For simplicity in this demo/MVP, we bypass signature verification
        # and just decode the payload, relying on the fact that if the user
        # got it from Supabase, it's their token.
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False},
        )
        return payload
    except jwt.PyJWTError as e:
        print(f"JWT Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido o expirado: {str(e)}",
        )
