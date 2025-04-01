# auth/router.py
from datetime import timedelta, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from auth.database import get_async_session, User
from auth.security import (
    create_access_token,
    authenticate_user,
    CurrentUser,
    Token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    pwd_context,
)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        session: AsyncSession = Depends(get_async_session)
):
    user = await authenticate_user(form_data.username, form_data.password, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register")
async def register(
        username: str,
        email: str,
        password: str,
        session: AsyncSession = Depends(get_async_session)
):
    existing_user = await session.execute(
        select(User).where((User.username == username) | (User.email == email))
    )
    if existing_user.scalar():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    hashed_password = pwd_context.hash(password)
    new_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        registered_at=datetime.utcnow(),
        is_active=True,
        is_superuser=False,
        is_verified=False
    )

    session.add(new_user)
    await session.commit()
    return {"message": "User created successfully"}


@router.get("/me")
async def read_users_me(current_user: CurrentUser):
    return {
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser
    }