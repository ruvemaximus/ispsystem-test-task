from typing import Annotated

from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from .schemas import User

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(password: str):
    return f"123{password}123"


fake_users_db = {
    "user": {"username": "user", "password": hash_password("user")},
    "ivan": {"username": "ivan", "password": hash_password("krutoymuzhik")},
}


def auth_by_token(token: str) -> User:
    if token in fake_users_db:
        return User(**fake_users_db.get(token))


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    if user := auth_by_token(token):
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if (user := fake_users_db.get(form_data.username)) is None:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not hash_password(form_data.password) == user["password"]:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": user["username"], "token_type": "bearer"}


@router.get("/me")
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
