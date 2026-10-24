import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, SessionDep
from app.models import User
from app.auth_schemas import Token, UserCreate, UserOut
from app.security import DUMMY_HASH, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: SessionDep):
    # bcrypt считает CPU-bound, поэтому уводим его из event loop
    hashed = await asyncio.to_thread(hash_password, data.password)
    user = User(email=data.email, hashed_password=hashed)
    session.add(user)
    try:
        # без предварительного SELECT: уникальность гарантирует индекс, гонок нет
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    return user


@router.post("/login", response_model=Token)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    email = form.username.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    # хеш проверяется всегда, даже если пользователя нет: время ответа не выдаёт существование email
    ok = await asyncio.to_thread(
        verify_password, form.password, user.hashed_password if user else DUMMY_HASH
    )
    if user is None or not ok:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user
