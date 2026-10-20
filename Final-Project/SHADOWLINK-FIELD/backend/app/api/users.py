from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db, utcnow
from app.core.security import require_role, UserRole, get_password_hash
from app.models.user import User
from app.schemas.auth import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _=Depends(require_role([UserRole.ADMIN])),
):
    users = db.query(User).all()
    return users


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role([UserRole.ADMIN])),
):
    existing = db.query(User).filter_by(username=user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")

    user = User(
        username=user_in.username,
        password_hash=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        role=user_in.role,
        enabled=True,
        created_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
