import base64
import json
from typing import Dict, Optional, List, Any
from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwk
from jose.utils import base64url_decode
from pydantic import BaseModel
from starlette.requests import Request
from starlette.status import HTTP_403_FORBIDDEN
from auth.user_auth import user_info_with_token

# Define the type for JWK
JWK = Dict[str, str]


# Model for the JSON Web Key Set (JWKS)
class JWKS(BaseModel):
    keys: List[JWK]


# Model for JWT authorization credentials
class JWTAuthorizationCredentials(BaseModel):
    jwt_token: str
    header: dict[str, str]
    claims: dict[str, Any]
    signature: str
    message: str


# Class to handle JWT authentication
class JWTBearer(HTTPBearer):
    def __init__(self, jwks: JWKS, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
        # Map KIDs to their corresponding JWKs
        self.kid_to_jwk = {jwk["kid"]: jwk for jwk in jwks.keys}

    def decode_jwt(self, token: str):
        """
        Decode a JWT token.

        :param token: JWT token to decode.
        :return: Decoded header and payload.
        """
        try:
            header, payload, _ = token.split(".")
            decoded_header = json.loads(
                base64.urlsafe_b64decode(header + "==").decode("utf-8")
            )
            decoded_payload = json.loads(
                base64.urlsafe_b64decode(payload + "==").decode("utf-8")
            )

            return decoded_header, decoded_payload
        except Exception:
            return None, None  # Return None on error

    def verify_jwk_token(self, jwt_credentials: JWTAuthorizationCredentials) -> bool:
        """
        Verify a JWT token using a JWK.

        :param jwt_credentials: JWTAuthorizationCredentials object.
        :return: True if the token is valid, otherwise False.
        """
        try:
            public_key = self.kid_to_jwk[jwt_credentials.header["kid"]]
        except KeyError:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="JWK public key not found"
            )

        # Construct the public key
        key = jwk.construct(public_key)
        # Decode the signature
        decoded_signature = base64url_decode(jwt_credentials.signature.encode())

        # Verify the token's signature
        return key.verify(jwt_credentials.message.encode(), decoded_signature)

    def verify_token_revoed(self, jwt_token: str):
        """
        Verify if the token is revoked.

        :param jwt_token: JWT token to verify.

        :raises HTTPException: If the token is revoked.
        """
        try:
            user_info_with_token(jwt_token)
        except ClientError as e:
            # Verifica se a exceção é 'NotAuthorizedException', ou seja, o token foi revogado
            if e.response["Error"]["Code"] == "NotAuthorizedException":
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail="Access token has been revoked",
                )
            else:
                raise  # Levanta outras exceções de boto3
        except Exception as e:
            # Qualquer outra exceção que precise ser tratada
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="An error occurred while validating the token",
            )

    async def __call__(self, request: Request) -> Optional[JWTAuthorizationCredentials]:
        """
        Call method to authenticate the request.

        :param request: Incoming request.
        :return: JWTAuthorizationCredentials object if valid, otherwise raise an HTTPException.

        :raises HTTPException: If the JWT is invalid.
        """
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if not credentials:
            return None

        # Check authentication method
        self.verify_authentication_scheme(credentials)

        jwt_token = credentials.credentials

        # Validate if token is revoked
        self.verify_token_revoed(jwt_token)

        self.validate_jwt_structure(jwt_token)

        try:
            decoded_header, claims = self.decode_jwt(jwt_token)
            jwt_credentials = self.create_jwt_credentials(
                jwt_token, decoded_header, claims
            )
        except ValueError:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Invalid JWT header"
            )

        # Verify if the token is valid
        if not self.verify_jwk_token(jwt_credentials):
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="JWK invalid")

        return jwt_credentials  # Return the JWT credentials if valid

    def verify_authentication_scheme(self, credentials: HTTPAuthorizationCredentials):
        """
        Verify that the authentication scheme is Bearer.

        :param credentials: HTTPAuthorizationCredentials object.

        :raises HTTPException: If the authentication scheme is not Bearer."""
        if credentials.scheme != "Bearer":
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Wrong authentication method"
            )

    def validate_jwt_structure(self, jwt_token: str):
        """
        Validate the structure of a JWT token.

        :param jwt_token: JWT token to validate.

        :raises HTTPException: If the JWT structure is invalid.
        """
        if len(jwt_token.split(".")) != 3:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Invalid JWT structure"
            )

    def create_jwt_credentials(
        self, jwt_token: str, decoded_header: dict, claims: dict
    ) -> JWTAuthorizationCredentials:
        """
        Create a JWTAuthorizationCredentials object.

        :param jwt_token: JWT token.
        :param decoded_header: Decoded JWT header.
        :param claims: Decoded JWT claims.
        :return: JWTAuthorizationCredentials object.
        """
        if claims is None:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Failed to decode claims"
            )

        # Remove unnecessary fields from claims
        claims.pop("version", None)

        # Convert timestamps to strings
        for claim in ["auth_time", "iat", "exp"]:
            if claim in claims:
                claims[claim] = str(claims[claim])

        return JWTAuthorizationCredentials(
            jwt_token=jwt_token,
            header=decoded_header,
            claims=claims,
            signature=jwt_token.rsplit(".", 1)[-1],
            message=jwt_token.rsplit(".", 1)[0],
        )