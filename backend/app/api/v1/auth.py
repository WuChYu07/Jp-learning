"""Site-wide login: one shared password, not per-user identity."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.site_auth import issue_token, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    if not verify_password(body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    return LoginResponse(token=issue_token())
