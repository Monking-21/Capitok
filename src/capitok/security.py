from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from capitok.config import Settings, get_settings


@dataclass(frozen=True)
class IdentityContext:
    tenant_id: str
    principal_id: str
    scopes: list[str]


def require_identity(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> IdentityContext:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    entry = settings.api_key_map().get(x_api_key)
    if not entry:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    tenant_id = entry.get("tenant_id")
    principal_id = entry.get("principal_id")
    scopes = entry.get("scopes", [])

    if not tenant_id or not principal_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid auth map entry")

    return IdentityContext(tenant_id=tenant_id, principal_id=principal_id, scopes=scopes)


def require_scope(required_scope: str):
    def dependency(identity: IdentityContext = Depends(require_identity)) -> IdentityContext:
        if required_scope not in identity.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")
        return identity

    return dependency
