"""
GoatRaw - User Routes (Auth)
POST /users/register
POST /users/login
GET  /users/me
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
import bcrypt
import jwt
import uuid
import secrets
from datetime import datetime, timedelta
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, PlanTier
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    plan: str
    api_key: str


def create_token(user_id: str, email: str, plan: str) -> str:
    payload = {
        "id": user_id,
        "email": email,
        "plan": plan,
        "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user with PostgreSQL persistence."""
    # Check for existing user
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user_id = uuid.uuid4()
    api_key = secrets.token_urlsafe(32)
    workspace_id = str(uuid.uuid4())
    plan = PlanTier.FREE

    new_user = User(
        id=user_id,
        email=body.email,
        hashed_password=hashed,
        full_name=body.full_name,
        api_key=api_key,
        workspace_id=workspace_id,
        plan=plan,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_token(str(new_user.id), new_user.email, new_user.plan)
    return TokenResponse(
        access_token=token,
        user_id=str(new_user.id),
        plan=new_user.plan,
        api_key=new_user.api_key,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login and verify against PostgreSQL."""
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not bcrypt.checkpw(body.password.encode(), user.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_token(str(user.id), user.email, user.plan)
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        plan=user.plan,
        api_key=user.api_key,
    )


from app.api.deps import get_current_user

@router.get("/me")
async def get_me(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get current user info from DB."""
    user_id = user.get("id")
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    return {
        "id": str(db_user.id),
        "email": db_user.email,
        "full_name": db_user.full_name,
        "plan": db_user.plan,
        "workspace_id": db_user.workspace_id,
        "created_at": db_user.created_at,
    }
