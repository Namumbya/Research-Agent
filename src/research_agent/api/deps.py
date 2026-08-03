from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from research_agent.core.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)


def require_api_key(
    api_key_header: str | None = Security(_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    settings = get_settings()
    candidate: str | None = None

    if api_key_header:
        candidate = api_key_header.strip()
    elif bearer and bearer.credentials:
        candidate = bearer.credentials.strip()

    if not candidate or candidate not in settings.api_key_set:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "unauthorized",
                    "message": "Invalid or missing API key",
                    "details": {},
                }
            },
        )
    return candidate
