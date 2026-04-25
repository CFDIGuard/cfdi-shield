from fastapi import Depends, HTTPException, status

from app.db.session import get_db
from app.models.user import User
from app.web_deps import get_current_user


def get_api_current_user(current_user: User | None = Depends(get_current_user)) -> User:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return current_user


__all__ = ["get_db", "get_api_current_user"]
