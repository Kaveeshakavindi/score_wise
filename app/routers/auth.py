from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import CurrentUser, get_auth_service, rate_limit_per_ip
from app.schemas.auth import (
    ForgotPasswordRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    UserPublic,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_per_ip("auth_register", limit=5, window_s=60))],
)
async def register(body: RegisterRequest, auth_service: AuthServiceDep) -> UserPublic:
    """Create a user account. No auth required. 5 req/min per IP (§8, brute-force
    / enumeration protection)."""
    user = await auth_service.register(
        name=body.name, nickname=body.nickname, password=body.password, age=body.age, email=body.email
    )
    return UserPublic.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit_per_ip("auth_login", limit=5, window_s=60))],
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], auth_service: AuthServiceDep
) -> TokenPair:
    """Exchange nickname+password for tokens (OAuth2 Password Grant). No auth
    required — credentials are the body. 5 req/min per IP (§8)."""
    result = await auth_service.login(nickname=form.username, password=form.password)
    return TokenPair(
        access_token=result.access_token, refresh_token=result.refresh_token, expires_in=result.expires_in
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, auth_service: AuthServiceDep) -> TokenPair:
    """Rotate refresh token -> new access token. No auth required — the
    refresh token in the body is the credential."""
    result = await auth_service.refresh(refresh_token=body.refresh_token)
    return TokenPair(
        access_token=result.access_token, refresh_token=result.refresh_token, expires_in=result.expires_in
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, current_user: CurrentUser, auth_service: AuthServiceDep) -> Response:
    """Revoke the current refresh token. Requires a valid access token."""
    await auth_service.logout(refresh_token=body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserPublic)
async def me(current_user: CurrentUser) -> UserPublic:
    """Current user profile. Requires a valid access token."""
    return UserPublic.model_validate(current_user)


@router.post(
    "/forgot-password",
    dependencies=[Depends(rate_limit_per_ip("auth_forgot_password", limit=3, window_s=60))],
)
async def forgot_password(body: ForgotPasswordRequest, auth_service: AuthServiceDep) -> dict[str, str]:
    """Request a password reset email. No auth required. Always returns the
    same response whether or not the email has an account — anti-enumeration
    (AuthService.request_password_reset never raises for "not found", and
    catches email-send failures internally for the same reason). 3 req/min per
    IP — stricter than login/register since this triggers a real outbound
    email per call."""
    await auth_service.request_password_reset(email=body.email)
    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit_per_ip("auth_reset_password", limit=5, window_s=60))],
)
async def reset_password(body: ResetPasswordRequest, auth_service: AuthServiceDep) -> Response:
    """Complete a password reset. No auth required — the reset token in the
    body is the credential. Revokes every existing refresh token for the
    account on success (forces re-login everywhere)."""
    await auth_service.reset_password(token=body.token, new_password=body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
