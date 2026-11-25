"""FastAPI dependencies for authentication: who is making this request?"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import DbSession
from app.errors import Unauthorized
from app.models import UserModel
from app.security import decode_access_token

# auto_error=False: we raise our own 401 with the usual {"detail", "code"} body. Also gives Swagger its Authorize button.
bearer = HTTPBearer(auto_error=False)


def get_current_user(db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> UserModel:
    if credentials is None:
        raise Unauthorized("not_authenticated", "Log in first: send 'Authorization: Bearer <token>'")
    # The token only proves the user id; the user and their role are read from the database on every request,
    # so a deleted or demoted user loses access immediately.
    user = db.get(UserModel, decode_access_token(credentials.credentials))
    if user is None:
        raise Unauthorized("invalid_token", "The access token is not valid")
    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]
