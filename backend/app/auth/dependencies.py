from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nepieciešama autentifikācija")
    try:
        user_id = decode_access_token(credentials.credentials)
    except (InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=401, detail="Nederīgs vai beidzies piekļuves marķieris")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Lietotāja konts nav aktīvs")
    return user


def require_roles(*roles: Role):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            if Role.ADMIN in roles and len(roles) == 1:
                detail = "Darbība atļauta tikai administratoram"
            else:
                detail = "Darbība nav atļauta šai lietotāja lomai"
            raise HTTPException(status_code=403, detail=detail)
        return user

    return dependency


require_operational = require_roles(Role.VADITAJS, Role.ADMIN)
require_admin = require_roles(Role.ADMIN)

